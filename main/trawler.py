import argparse
from time import sleep
import urllib2

from lxml.html.soupparser import fromstring, unescape
import requests
import simplejson
import xlsxwriter
import re


def setup(existing_session_id=None):
    s = requests.Session()

    # Make sure we're authenticated and have a session
    s.auth = ('ehraf12', 'Abda15')
    if existing_session_id:
        s.cookies['JSESSIONID'] = existing_session_id
    login_url = "http://ehrafworldcultures.yale.edu/ehrafe/"
    print "GET {}".format(login_url)
    login_response = s.get(login_url)
    assert login_response.status_code == 200

    sleep(0.2)

    # This call seems to be necessary for future ones to work. I think it gives us some tracking cookies
    get_cookies_url = "http://ehrafworldcultures.yale.edu/ehrafe/booleanSearchSetup.do?forward=booleanForm"
    print "GET {}".format(get_cookies_url)
    get_cookies_response = s.get(get_cookies_url)
    assert get_cookies_response.status_code == 200

    sleep(0.2)

    return s

def run_query(query, s):
    # We POST the query, but the response doesn't contain any results. The results are stored
    # against the session on the webserver (which is a little unusual)
    query_url = "http://ehrafworldcultures.yale.edu/ehrafe/booleanSearch.do?method=booleanSearch&searchType=advanced"
    data = {'pseudoQuery': query}
    query_response = s.post(query_url, data=data)
    assert query_response.status_code == 200

    sleep(0.2)

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

def get_paragraphs_for_culture(culture, s):
    # Each culture has a url, which we fetch to tell the site we want that culture next
    culture_path = urllib2.unquote(unescape(culture['href']))
    single_culture_result_url = "http://ehrafworldcultures.yale.edu/ehrafe/" + culture_path
    print "GET {}".format(single_culture_result_url)
    prod_server_result = s.get(single_culture_result_url)
    assert prod_server_result.status_code == 200
    sleep(0.2)

    culture_code = re.search("[&\?]owc=([A-Z0-9]*)&",
                             single_culture_result_url).groups()[0]

    # Now actually load the results for the culture
    load_results_url = 'http://ehrafworldcultures.yale.edu/ehrafe/pageHitsAjax.do?&howMany=99999999'
    print "GET {}".format(load_results_url)
    single_culture_result = s.get(load_results_url)
    assert single_culture_result.status_code == 200
    sleep(0.2)

    single_culture_result_doc = hack_single_culture_result(single_culture_result.content)

    single_culture_result_dom = fromstring(single_culture_result_doc)

    # The following XPaths extract various fields from the downloaded page. This is risky!
    # There is litle data on the pageto help identify the paragraphs, or anything else.
    paragraphs = []
    author = None
    document_title = None

    for row in single_culture_result_dom.xpath("/html/tbody/tr"):
        if row.get('class') == 'topAuthorRow':
            # A row about a new document
            author = "".join(row.xpath(".//span[@class='topAuthor']/text()")).strip()
            document_title = "".join(row.xpath(".//span[@class='topTitle']/text()")).strip()
            document_id = "".join(row.xpath(".//button/@id")).strip()
            permalink = "http://ehrafworldcultures.yale.edu/document?id={0}".format(document_id)

            publication_url_template = "http://ehrafworldcultures.yale.edu/ehrafe/citation.do?method=citation&forward=searchFullContext&docId={}"
            publication_url = publication_url_template.format(document_id)
            print "GET {}".format(publication_url)
            publication_response = s.get(publication_url)
            sleep(0.2)
            publication_dom = fromstring(publication_response.content)
            field_date = "".join(publication_dom.xpath("//field.date/text()")).strip()
            coverage_date = "".join(publication_dom.xpath("//date[@type='coverage']/text()")).strip()
            subjects = publication_dom.xpath("//p[./span/text()='Subjects: ']/span/a/text()")
            subjects = [subject.strip() for subject in subjects]
        else:
            # A row about a paragraph in the document
            text_nodes = row.xpath(".//div[contains(@id, 'longHit')]//span[@class='p']//text()")
            paragraph_text = "".join(text_nodes).strip().replace('\n', ' ')
            page_number = "".join(row.xpath(".//span[@class='pageNo']/text()")).strip()
            section = "".join(row.xpath(".//div[@class='secTitle']/span[@class='author']/text()")).strip()

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
                               "permalink": permalink
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
               ("permalink", "Permalink"))

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
