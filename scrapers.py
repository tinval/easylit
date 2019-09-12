import requests
import bibtexparser
import feedparser
import scholarly
import hashlib, random
import pandas as pd
import re
import yaml
from bs4 import BeautifulSoup
import html

with open("config.yml", 'r') as ymlfile:
    cfg = yaml.load(ymlfile, Loader=yaml.FullLoader)

class Scraper:
    scrapers =['arxiv', 'springer', 'sciencedirect', 'nasa', 'gscholar', 'project euclid']
    def __init__(self, data, source=None):
        self.data = data
        self.page = 1
        self.total = 0
        self.source = source

    def search(self, source=None):
        if source:
            self.source = source
        if self.source == 'arxiv':
            return self.search_arxiv()
        if self.source == 'springer':
            return self.search_springer()
        if self.source == 'gscholar':
            return self.search_gscholar()
        if self.source == 'sciencedirect':
            return self.search_sciencedirect()
        if self.source == 'nasa':
            return self.search_nasa()
        if self.source == 'project euclid':
            return self.search_project_euclid()

    def search_arxiv(self):
        url = 'http://export.arxiv.org/api/query'
        query = dict(au=self.data['author'],
                     ti=self.data['title'],
                     abs=self.data['abstract'])
        params = dict(search_query=format_query(query, 'arxiv'),
                      start=(self.page-1)*10,
                      max_results=10)
        response = feedparser.parse(requests.get(url, params).text)
        self.total = int(response.get('feed').get('opensearch_totalresults'))
        raw_results = pd.DataFrame(response.get('entries'))
        if raw_results.empty:
            return pd.DataFrame()
        results = pd.DataFrame()
        results['title'] = raw_results['title']
        results['author'] = raw_results['authors'].apply(lambda x: get_metainfo(x, 'name', 'space'))
        results['date'] = raw_results['published'].apply(lambda x: x[:4])
        results['tags'] = raw_results['tags'].apply(lambda x: get_metainfo(x, 'term')) 
        results['abstract'] = raw_results['summary']
        results['link'] = raw_results['links'].apply(lambda x: extract_value(x, '/abs/', 'href'))
        results['document'] = raw_results['links'].apply(lambda x: extract_value(x, '/pdf/', 'href'))
        return results

    def search_springer(self):
        url = 'http://api.springernature.com/meta/v2/json'
        query = dict(name=self.data['author'],
                     title=self.data['title'],
                     subject='Mathematics'
                     )
        params = dict(q=format_query(query, 'springer'),
                     api_key=cfg['key_springer'],
                     p=10,
                     s=(self.page-1)*10+1)
        response = requests.get(url, params).json()
        self.total = int(response['result'][0]['total'])
        raw_results = pd.DataFrame(response['records'])
        if len(raw_results) == 0:
            return raw_results
        results = pd.DataFrame()
        results['title'] = raw_results['title'].str.replace(r'\n', '')
        results['author'] = raw_results['creators'].apply(lambda x: get_metainfo(x, 'creator', 'comma'))
        results['date'] = raw_results['publicationDate'].apply(lambda x: x[:4])
        results['abstract'] = raw_results['abstract'].apply(lambda x: '' if not isinstance(x, str) or len(x) < 7 else (x[9:] if x[8] == '.' else x[8:]))
        results['publisher'] = raw_results['publisher']
        results['volume'] = raw_results['volume']
        results['number'] = raw_results['number']
        if 'endingPage' not in raw_results.columns:
            raw_results['endingPage'] = ''
        results['pages'] = raw_results['startingPage'] + '--' + raw_results['endingPage']
        results['journal'] = raw_results['publicationName']
        results['form'] = raw_results['contentType']
        if 'doi' in raw_results.columns:
            results['doi'] = raw_results['doi']
        results['document'] = raw_results['url'].apply(lambda x: get_metainfo_if(x, ('format', 'pdf'), 'value'))
        return results

   
    def search_sciencedirect(self):
        url = 'https://api.elsevier.com/content/search/sciencedirect'
        query = dict(aut=self.data['author'],
                     ttl=self.data['title'],
                     abs=self.data['abstract']
                     )
        params = dict(query=format_query(query, 'sciencedirect'),
                     apiKey=cfg['key_elsevier'],
                     count=10,
                     start=(self.page-1)*10)
        response = requests.get(url, params).json()
        self.total = int(response['search-results']['opensearch:totalResults'])
        raw_results = pd.DataFrame(response['search-results']['entry'])
        if len(raw_results) == 0:
            return raw_results
        results = pd.DataFrame()
        if 'dc:title' in raw_results:
            results['title'] = raw_results['dc:title']
        if 'authors' in raw_results:
            results['author'] = raw_results['authors'].apply(extract_author_sciencedirect)
        if 'prism:coverDate' in raw_results:
            results['date'] = raw_results['prism:coverDate'].apply(lambda x: x[:4])
        if 'prism:startingPage' in raw_results:
            results['pages'] = raw_results['prism:startingPage'] + '--' + raw_results['prism:endingPage']
        if 'prism:publicationName' in raw_results:
            results['journal'] = raw_results['prism:publicationName']
        if 'prism:doi' in raw_results:
            results['doi'] = raw_results['prism:doi']
        if 'prism:url' in raw_results:
            pii = raw_results['prism:url'].apply(lambda x: re.search(r'pii\/(.*?)$', x).group(1))
            results['link'] = 'https://www.sciencedirect.com/science/article/pii/' + pii
            results['document'] = results['link'] + '/pdfft?isDTMRedir=true&download=true'
        return results


    def search_nasa(self):
        url = 'https://api.adsabs.harvard.edu/v1/search/query'
        query = dict(author=self.data['author'],
                     abs=self.data['title'] + ' ' + self.data['abstract']
                     )
        params = dict(q=format_query(query, 'nasa'),
                      rows=10,
                      start=(self.page-1)*10,
                      fl='bibcode,author,title,doi,year,abstract,bibcode'
                      )
        print(format_query(query, 'nasa'))
        headers = dict(Authorization='Bearer {}'.format(cfg['key_nasa']))
        response = requests.get(url, params, headers=headers).json()
        if not 'response' in response:
            return pd.DataFrame()
        self.total = int(response['response']['numFound'])
        raw_results = pd.DataFrame(response['response']['docs'])
        if len(raw_results) == 0:
            return raw_results
        results = pd.DataFrame()
        results['title'] = raw_results['title'].apply(lambda x: x[0])
        results['author'] = raw_results['author'].apply(lambda x: ', '.join([author.split(',')[0] for author in x]))
        results['date'] = raw_results['year']
        if 'doi' in raw_results:
            results['doi'] = raw_results['doi']
        results['link'] = 'https://ui.adsabs.harvard.edu/link_gateway/' + raw_results['bibcode'] + '/ESOURCE'
        results['abstract'] = raw_results['abstract']
        return results


    def search_project_euclid(self):
        url = 'https://projecteuclid.org/search_result'
        params = {'q.a.title':self.data['title'],
                  'q.a.author':self.data['author'],
                  'q.a.abstract':self.data['abstract'],
                  'type':all,
                  'rows':10,
                  'resultPage':self.page
                  }
        response = requests.get(url, params).content
        soup = BeautifulSoup(response, 'html.parser')
        results = pd.DataFrame()
        try:
            self.total = int(re.search(r'of (\d+) res', soup.find('p', 'query').text).group(1))
        except:
            self.total = 0
            return results            
        raw_results = soup.find_all('div', 'result')
        base_url = 'https://projecteuclid.org'
        for result in raw_results:
            record = {}
            record['title'] = result.find('h3').find('a').text
            record['author'] = ', '.join([author.text.split(',')[0] for author in result.find_all('a', 'trigger')])
            link = result.find('h3').find('a')['href']
            record['link'] = base_url + link
            record['document'] = base_url + '/download/pdf_1' + link
            regex_result = re.search(r'<br\/><a.*?>(.*?)<\/a> Volume (.*?), .*?<\/a> \(.*?(\d+)\), ([0-9\-]+).<\/p>', html.unescape(str(result)))
            if regex_result:
                record['journal'] = regex_result.group(1)
                record['volume'] = regex_result.group(2)
                record['date'] = regex_result.group(3)
                record['pages'] = regex_result.group(4)
            results = results.append(record, ignore_index=True)
        return results[['title', 'author', 'date', 'journal', 'document', 'link', 'volume', 'pages']]

    def search_gscholar(self, getbib=False):
        query = ' '.join(self.data.values())
        raw_results = scholarly.search_pubs_query(query)
        
        #headers from scholarly
        if getbib:
            _GOOGLEID = hashlib.md5(str(random.random()).encode('utf-8')).hexdigest()[:16]
            _COOKIES = {'GSP': 'ID={0}:CF=4'.format(_GOOGLEID)}
            _HEADERS = {
    'accept-language': 'en-US,en',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/41.0.2272.76 Chrome/41.0.2272.76 Safari/537.36',
    'accept': 'text/html,application/xhtml+xml,application/xml'
    }
        results = pd.DataFrame()
        count = 0
        while(count < 10):
            entry = next(raw_results)
            result = {'title': entry.bib.get('title'),
                'abstract': entry.bib.get('abstract'), 
                'link': entry.bib.get('url'),
                'document': entry.bib.get('eprint')}
            result['author'] = ', '.join(re.findall(r'([^ ]+)(?: and|$)', entry.bib.get('author').replace('… and','').replace('…','')))
            if getbib:
                urlBibfile = entry.get(url_scholarbib)
                response = requests.get(urlBibfile, headers=_HEADERS, cookies=_COOKIES)
                if response.status_code == 200:
                    bibDictionary = bibtexparser.loads(response.text).entries[0]
                    result['date'] = bibDictionary.get('year')
                    result['journal'] = bibDictionary.get('journal')
                    result['form'] = bibDictionary.get('ENTRYTYPE')
                    result['pages'] = bibDictionary.get('pages')
                    result['number'] = bibDictionary.get('number')
                    result['volume'] = bibDictionary.get('volume')
                    result['publisher'] = bibDictionary.get('publisher')
            results = results.append(result, ignore_index=True)
            count += 1
        total = 10
        return total, results

def format_query(query, style):
    if style == 'arxiv':
        return '(' + ' AND '.join([param + ':"' + query[param] + '"' for param in query if query[param] !='']) + ')'
    if style == 'springer':
        return '(' + ' AND '.join([param + ':' + query[param] + '' for param in query if query[param] !='']) + ')'
    if style == 'sciencedirect':
        return ' AND '.join([param + '(' + query[param] + ')' for param in query if query[param] !=''])
    if style == 'nasa':
        return ','.join([param + ':' + query[param] for param in query if query[param] !='' and query[param] !=' '])


def get_metainfo_if(datum, condition, key):
    """
    datum: list of dicts
    condition: tuple of strings where the first is a key of the dicts of datum 
    key: key of the dicts
    """
    for dat in datum:
        if dat.get(condition[0]) == condition[1]:
            return dat[key]
    return ''

def get_metainfo(datum, key, split=None):
    """
    datum: list of dictionaries
    key: key
    """
    if split == 'comma':
        return ', '.join([entry.get(key).split(',')[0] for entry in datum])
    elif split == 'space':
        return ', '.join([entry.get(key).split()[-1] for entry in datum])
    else:
        return ', '.join([entry.get(key) for entry in datum])

def extract_value(datum, value, key):
    """
    datum: list of dictionaries
    value: string
    target: key
   
    returns element[key] of list if value in element[key]  
    """
    for dat in datum:
        if value in dat[key]:
            return dat[key]
    return ''

def extract_author_sciencedirect(authors):
    if authors:
        authors = authors['author']
        if isinstance(authors, str):
            return authors.split()[-1]
        return ', '.join([author['$'].split()[-1] for author in authors])
    

if __name__=='__main__':
    data = dict(author='', title='lagrangian', abstract='')
    scraper = Scraper(data, 'springer')
    results = scraper.search()

    if not results.empty:
        for r, result in results.iterrows():
            print(result['title'])

