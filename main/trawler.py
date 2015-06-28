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
    login_response = s.get(login_url)
    assert login_response.status_code == 200

    sleep(1)

    # This call seems to be necessary for future ones to work. I think it gives us some tracking cookies
    get_cookies_url = "http://ehrafworldcultures.yale.edu/ehrafe/booleanSearchSetup.do?forward=booleanForm"
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
    # Each culture has a url for a page containing the paragraphs from the search
    culture_path = urllib2.unquote(unescape(culture['href']))
    single_culture_result_url = "http://ehrafworldcultures.yale.edu/ehrafe/" + culture_path
    single_culture_result = s.get(single_culture_result_url)
    sleep(1)

    culture_code = re.search("[&\?]owc=([A-Z0-9]*)&",
                             single_culture_result_url).groups()[0]

    single_culture_result_doc = hack_single_culture_result(single_culture_result.content)

    single_culture_result_dom = fromstring(single_culture_result_doc)

    # The following XPaths extract various fields from the downloaded page. This is risky!
    # There is litle data on the pageto help identify the paragraphs, or anything else.
    paragraphs = []
    author = None
    document_title = None

    table = single_culture_result_dom.xpath("//table[@id='para']")[0]

    for row in table.xpath("tbody/tr"):
        if row.get('class') == 'topAuthorRow':
            author = "".join(row.xpath(".//span[@class='topAuthor']/text()")).strip()
            document_title = "".join(row.xpath(".//span[@class='topTitle']/text()")).strip()
            document_id = "".join(row.xpath(".//button/@id")).strip()
        else:
            text_nodes = row.xpath(".//span[@pageeid]//text()")
            paragraph_text = "".join(text_nodes).strip()
            page_number = "".join(row.xpath(".//span[@class='pageNo']/text()")).strip()
            section = "".join(row.xpath(".//div[@class='secTitle']/span[@class='author']/text()")).strip()

            paragraphs.append({
                               'text': paragraph_text,
                               'author': author,
                               'document_title': document_title,
                               'document_id': document_id,
                               'page_number': page_number,
                               'section': section,
                               'culture': culture['cultureName'],
                               'culture_code': culture_code
                               })
    return paragraphs

def output_results_to_xls(paragraphs):
    workbook = xlsxwriter.Workbook('results.xlsx')
    worksheet = workbook.add_worksheet()

    first_col = 0
    first_row = 1

    worksheet.write(0, first_col, 'HRAF Document ID')
    worksheet.write(0, first_col + 1, 'Page')
    worksheet.write(0, first_col + 2, 'Culture')
    worksheet.write(0, first_col + 3, 'Culture code')
    worksheet.write(0, first_col + 4, 'Text')
    worksheet.write(0, first_col + 5, 'Author')
    worksheet.write(0, first_col + 6, 'Document title')

    for index, paragraph in enumerate(paragraphs):
        worksheet.write(first_row + index, first_col, paragraph['document_id'])
        worksheet.write(first_row + index, first_col + 1, paragraph['page_number'])
        worksheet.write(first_row + index, first_col + 2, paragraph['culture'])
        worksheet.write(first_row + index, first_col + 3, paragraph['culture_code'])
        worksheet.write(first_row + index, first_col + 4, paragraph['text'])
        worksheet.write(first_row + index, first_col + 5, paragraph['author'])
        worksheet.write(first_row + index, first_col + 6, paragraph['document_title'])

    workbook.close()

def main(query, existing_session_id=None):
    s = setup(existing_session_id)

    paragraphs = []

    for culture in run_query(query, s):
        print "CULTURE {}".format(culture['cultureName'])
        paragraphs_for_culture = get_paragraphs_for_culture(culture, s)
        paragraphs.extend(paragraphs_for_culture)

    output_results_to_xls(paragraphs)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    args = parser.parse_args()
    main(args.query)
