import argparse
import re
from time import sleep
import urllib2

from lxml.html.soupparser import fromstring, unescape
import requests
import simplejson
import xlsxwriter


def setup(existing_session_id=None):
    s = requests.Session()

    # Make sure we're authenticated and have a session
    s.auth = ('ehraf', 'Bemba49')
    if existing_session_id:
        s.cookies['JSESSIONID'] = existing_session_id
    login_url = "http://ehrafworldcultures.yale.edu/ehrafe/"
    print "GET {}".format(login_url)
    login_response = s.get(login_url)
    assert login_response.status_code == 200

    sleep(1)

    # This call seems to be necessary for future ones to work. I think it gives us some tracking cookies
    get_cookies_url = "http://ehrafworldcultures.yale.edu/ehrafe/booleanSearchSetup.do?forward=booleanForm"
    print "GET {}".format(get_cookies_url)
    get_cookies_response = s.get(get_cookies_url)
    assert get_cookies_response.status_code == 200

    sleep(1)

    return s

def run_query(query, s):
    # We POST the query, but the response doesn't contain any results. The results are stored
    # against the session on the webserver (which is a little unusual)
    query_url = "http://ehrafworldcultures.yale.edu/ehrafe/booleanSearch.do?method=booleanSearch&searchType=advanced"
    data = {'pseudoQuery': query}
    query_response = s.post(query_url, data=data)
    assert query_response.status_code == 200

    sleep(1)

    # This AJAX call returns the results from the previous POST, as a JSON object
    results_url = "http://ehrafworldcultures.yale.edu/ehrafe/cultureResultsAjax.do"
    print "GET {}".format(results_url)
    results_response = s.get(results_url)
    assert results_response.status_code == 200

    results = simplejson.loads(results_response.content)
    # Return the culture objects
    return results['owcs'].values()

def hack_single_culture_result(doc):
    # Some of the title spans have multiple classes,
    # which confuses beautiful soup
    return doc.replace('class="topTitle" class="italics"',
                       'class="topTitle"')

def get_culture_paragraphs_page(culture, s):
    # Each culture has a url, which we fetch to tell the site we want that culture next
    culture_path = urllib2.unquote(unescape(culture['href']))
    single_culture_result_url = "http://ehrafworldcultures.yale.edu/ehrafe/" + culture_path
    print "GET {}".format(single_culture_result_url)
    prod_server_result = s.get(single_culture_result_url)
    assert prod_server_result.status_code == 200
    sleep(1)

    culture_code = re.search("[&\?]owc=([A-Z0-9]*)&",
                             single_culture_result_url).groups()[0]

    # Now actually load the results for the culture. The site already knows the one we want
    load_results_url = 'http://ehrafworldcultures.yale.edu/ehrafe/pageHitsAjax.do?&howMany=99999999'
    print "GET {}".format(load_results_url)
    single_culture_result = s.get(load_results_url)
    assert single_culture_result.status_code == 200
    sleep(1)

    single_culture_result_doc = hack_single_culture_result(single_culture_result.content)

    print "PARSE {}".format(load_results_url)
    single_culture_result_dom = fromstring(single_culture_result_doc)
    print "PARSED"
    return single_culture_result_dom, culture_code

def get_document_row_info(row):
    # For a row in the results table about a document, extract various fields
    author = "".join(row.xpath(".//span[@class='topAuthor']/text()")).strip()
    document_title = "".join(row.xpath(".//span[@class='topTitle']/text()")).strip()
    document_id = "".join(row.xpath(".//button/@id")).strip()
    permalink = "http://ehrafworldcultures.yale.edu/document?id={0}".format(document_id)
    return author, document_title, document_id, permalink

def get_document_page_info(document_id, s):
    # For a document_id, downloads its page and extracts various fields
    publication_url_template = "http://ehrafworldcultures.yale.edu/ehrafe/citation.do?method=citation&forward=searchFullContext&docId={}"
    publication_url = publication_url_template.format(document_id)
    print "GET {}".format(publication_url)
    publication_response = s.get(publication_url)
    sleep(1)
    publication_dom = fromstring(publication_response.content)
    field_date = "".join(publication_dom.xpath("//field.date/text()")).strip()
    coverage_date = "".join(publication_dom.xpath("//date[@type='coverage']/text()")).strip()
    subjects = publication_dom.xpath("//p[./span/text()='Subjects: ']/span/a/text()")
    subjects = [subject.strip() for subject in subjects]
    return field_date, coverage_date, subjects

def get_citation(document_id, s):
    # For a particular document, downloads a citation
    citation_url_template = "http://162.220.241.148:3001/citation/{}/style/chicago-author-date"
    citation_url = citation_url_template.format(document_id, s)
    citation_response = s.get(citation_url)
    sleep(1)
    citation_json = simplejson.loads(citation_response.content)
    # Notice the typo
    citation_html = citation_json['bibligraphy'][1][0]
    citation_dom = fromstring(citation_html)
    return "".join(citation_dom.xpath(".//div[@class='csl-entry']//text()"))

def get_paragraph_row_info(row):
    # For a row in the results table representing a paragraph, extract various fields
    top_text_nodes = row.xpath(".//span[@pageeid]")
    if len(top_text_nodes) == 0:
        return None
    top_text_node = top_text_nodes[0]
    text_nodes = top_text_node.xpath("./text()|./span[@class='highlight']/text()")
    paragraph_text = "".join(text_nodes).strip().replace('\n', ' ')
    page_number = "".join(row.xpath(".//span[@class='pageNo']/text()")).strip()
    section = "".join(row.xpath(".//div[@class='secTitle']/span[@class='author']/text()")).strip()
    return paragraph_text, page_number, section


def get_paragraphs_for_culture(culture, s):
    single_culture_result_dom, culture_code = get_culture_paragraphs_page(culture, s)

    paragraphs = []
    author = None
    document_title = None

    for row in single_culture_result_dom.xpath("/html/tbody/tr"):
        if row.get('class') == 'topAuthorRow':
            # A row about a new document
            author, document_title, document_id, permalink = get_document_row_info(row)
            field_date, coverage_date, subjects = get_document_page_info(document_id, s)
            citation = get_citation(document_id, s)
        else:
            # A row about a paragraph in the document
            paragraph_info = get_paragraph_row_info(row)
            if paragraph_info is None:
                continue
            paragraph_text, page_number, section = paragraph_info

            new_paragraph = {
                               "text": paragraph_text,
                               "author": author,
                               "document_title": document_title,
                               "document_id": document_id,
                               "page_number": page_number,
                               "section": section,
                               "culture": culture["cultureName"],
                               "culture_code": culture_code,
                               "subjects": ", ".join(subjects),
                               "coverage_date": coverage_date,
                               "field_date": field_date,
                               "permalink": permalink,
                               "citation": citation
                               }
            print new_paragraph
            paragraphs.append(new_paragraph)

    return paragraphs

def output_results_to_xls(paragraphs):
    workbook = xlsxwriter.Workbook('results.xlsx')
    worksheet = workbook.add_worksheet()

    mapping = (("document_id", "HRAF Document ID"),
               ("page_number", "Page"),
               ("culture", "Culture"),
               ("culture_code", "Culture code"),
               ("text", "Text"),
               ("author", "Author"),
               ("document_title", "Document Title"),
               ("subjects", "Subjects"),
               ("coverage_date", "Coverage Date"),
               ("field_date", "Field Date"),
               ("permalink", "Permalink"),
               ("citation", "Citation"))

    for index, (_, human_readable) in enumerate(mapping):
        worksheet.write(0, index, human_readable)

    for paragraph_index, paragraph in enumerate(paragraphs):
        for variable_index, (key, _) in enumerate(mapping):
            worksheet.write(1 + paragraph_index,
                            variable_index,
                            paragraph[key])

    workbook.close()

def main(query, existing_session_id=None):
    s = setup(existing_session_id)

    paragraphs = []

    for culture in run_query(query, s):
        print "CULTURE {}".format(culture)
        paragraphs_for_culture = get_paragraphs_for_culture(culture, s)
        paragraphs.extend(paragraphs_for_culture)

    output_results_to_xls(paragraphs)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    args = parser.parse_args()
    main(args.query)
