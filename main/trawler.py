from time import sleep
import urllib2

from lxml.html.soupparser import fromstring, unescape
import requests
import simplejson

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

def get_paragraphs_for_culture(culture, s):
    # Each culture has a url for a page containing the paragraphs from the search
    culture_path = urllib2.unquote(unescape(culture['href']))
    single_culture_result_url = "http://ehrafworldcultures.yale.edu/ehrafe/" + culture_path
    single_culture_result = s.get(single_culture_result_url)
    single_culture_result_dom = fromstring(single_culture_result.content)
    sleep(1)
    # The XPATH extracts the paragraph from the downloaded page. This bit is a bit risky! The page contains
    # very little metadata to help identify the paragraph.
    return [paragraph.encode('utf-8')
            for paragraph
            in single_culture_result_dom.xpath("//div[contains(@class, 'longHit')]/span/text()")]


def main(query, existing_session_id=None):
    s = setup(existing_session_id)

    for culture in run_query(query, s):
        print "CULTURE {}".format(culture['cultureName'])
        for paragraph in get_paragraphs_for_culture(culture, s):
            print paragraph


if __name__ == '__main__':
    main("(( Cultures = ('MP05' OR 'FK13' OR 'FK11' OR 'FN31' OR 'FN04' OR 'FK07' OR 'FL10' OR 'FL08' OR 'MP14' OR 'FL11' OR 'FL12' OR 'FJ22' OR 'FN17' OR 'FL20' OR 'FJ23' OR 'MO04' OR 'FL17') ) AND ( ( ( Subjects = ( Any Subject ) ) AND ( Text = (Any Text ) ) ) ) ) ) )")
