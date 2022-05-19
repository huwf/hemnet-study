import os
import sys
from collections import deque
from datetime import datetime
import time
import html
import json
import logging
import re
from urllib.robotparser import RobotFileParser
import urllib.request
from bs4 import BeautifulSoup
import requests

from database import db, Building, Apartment, Sale, Url

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

MONTHS = {
    'januari': 'January',
    'februari': 'February',
    'mars': 'March',
    'april': 'April',
    'maj': 'May',
    'juni': 'June',
    'juli': 'July',
    'augusti': 'August',
    'september': 'September',
    'oktober': 'October',
    'november': 'November',
    'december': 'December'
}


def scrape_results(path):
    soup = get_soup(path)
    results = soup.find(id='search-results')
    result_urls = []
    for result in results.find_all('li'):
        a = result.find('a')
        if a:
            logger.debug(a['href'])
            result_urls.append(a['href'])
    next_page = soup.find('a', attrs={'class': 'next_page'})
    if next_page:
        next_page = next_page['href']
    else:
        next_page = ''
    return {
        'results': result_urls,
        'next_page': next_page
    }


USER_AGENT = 'Mozilla/5.0 (platform; rv:geckoversion) Gecko/geckotrail Firefox/90.0.2 (64-bit)'

def get_soup(path):
    if path.startswith('http'):
        check_robots(path)
        soup = BeautifulSoup(requests.get(path, headers={'User-agent': USER_AGENT}).content, features='html.parser')
    else:
        with open(path) as f:
            soup = BeautifulSoup(f.read(), 'html')
    return soup

def scrape_sale_page(path):
    def clean(text):
        return text.replace('\n', ' ').strip()
    if isinstance(path, Url):
        path = path.url
    soup = get_soup(path)
    map_data = soup.find('div', id='map')['data-initial-data']
    map_data = html.unescape(map_data)
    metadata = json.loads(map_data)

    data_lists = soup.find_all('dl')
    # metadata = {}
    # metadata['address'] = soup.find('h1').text.replace('Slutpris', '').strip('\n').strip(' ')

    prop = soup.find('p', attrs={'class': 'sold-property__metadata qa-sold-property-metadata'})
    prop_text = clean(prop.text)
    prop_split = prop_text.split('-')
    # metadata['property_type'] = prop_split[0]
    location = prop_split[1]

    locations = [s.strip() for s in location.split(',')]
    metadata['listing']['locations'] = locations
    # metadata['sold_date'] = datetime.strptime(sold_date, '%d %B %Y')
    INTERESTING_FIELDS = ['driftskostnad', 'byggår', 'våning']
    for dl in data_lists:
        dl = dl.find_all()
        for i in range(0, len(dl) - 1, 2):
            dt = dl[i]
            # print(dt.text)
            if dt.text.lower() in INTERESTING_FIELDS:
                j = i + 1
                dd = dl[j]
                # print(f'{dt.text}\t{dd.text}')
                metadata['listing'][clean(dt.text.lower())] = clean(dd.text)
    metadata = process_metadata(metadata)
    logger.debug(f'Found metadata {metadata} for {path}')
    return metadata


def process_metadata(metadata):
    """Processes the data from the results page to be able to put into the database"""
    def change_listing_key(old, new):
        tmp = listing[old]
        del listing[old]
        listing[new] = tmp

    def get_listing_property_number(key):
        try:
            stringy = listing[key] or ''
            stringy = stringy.replace('\xc2', '').replace('\xa0', '')
        except KeyError:
            stringy = ''
        val = re.search(r'[0-9]+', stringy or '')
        if val:
            val = int(val[0].replace(' ', ''))
        listing[key] = val
        return val

    # address = address
    listing = metadata['listing']
    change_listing_key('typeSummary', 'property_type')
    get_listing_property_number('rooms')
    get_listing_property_number('living_space')
    balcony = None
    lift = False
    for lab in metadata['listing'].get('labels', []):
        if lab['identifier'] == 'balcony':
            balcony = True
        if lab['identifier'] == 'elevator':
            lift = True
    listing['has_balcony'] = balcony
    listing['has_lift'] = lift

    get_listing_property_number('fee')  # avgift
    change_listing_key('fee', 'avgift')
    if listing.get('byggår'):
        try:
            built = datetime.strptime(listing['byggår'], '%Y')
        except ValueError:
            built = datetime.strptime('2100', '%Y')    
    else:
        built = datetime.strptime('2100', '%Y')
    listing['built'] = built
    get_listing_property_number('driftskostnad')
    if listing.get('våning'):
        floors = listing['våning'].split(' ')
        total_floors = None
        floor = int(floors[0].replace(',', ''))
        if 'av' in listing['våning'] and len(floors) > 3:
            total_floors = int(floors[2].replace(',', ''))
    else:
        floor = None
        total_floors = None
    listing['floor'] = floor
    listing['total_floors'] = total_floors

    listing['sale_date'] = datetime.strptime(listing['sale_date'].replace('Såld ', ''), '%Y-%m-%d')
    if listing.get('asked_price'):
        get_listing_property_number('asked_price')
    get_listing_property_number('formatted_price')
    change_listing_key('formatted_price', 'sold_price')

    listing['map_url'] = metadata['map_url']
    listing['lat'] = listing['coordinate'][0]
    listing['lng'] = listing['coordinate'][1]
    return listing


def recover():
    urls = db.query(Url).filter(Url.processed == False).all()
    return deque(urls), get_saved_next_url()


def get_saved_next_url():
    next_url = None
    if os.path.exists('next_url.txt'):
        with open('next_url.txt', encoding='utf-8') as f:
            next_url = f.read().strip()
        os.remove('next_url.txt')
    return next_url

def check_robots(url):
    # See https://stackoverflow.com/questions/37934316/change-user-agent-used-with-robotparser-in-python
    # Cloudflare blocks non-browser user-agents, but there is nothing in robots against them
    # So parse it manually

    with urllib.request.urlopen(urllib.request.Request('https://www.hemnet.se/robots.txt',
                                                    headers={'User-Agent': USER_AGENT})) as response:
        parser = RobotFileParser()
        parser.parse(response.read().decode("utf-8").splitlines())

    if not parser.can_fetch(USER_AGENT, url):
        raise PermissionError(f'Robots does not allow us to access {url}')
    logger.info(f'About to process {url} so sleeping for 2 seconds')
    time.sleep(2)


def main(start_url=None, recover=False):
    logger.info(f'Getting results from {start_url}')
    def get_url_objects(results):
        stored_urls = Url.all_urls()
        urls = [Url(url=u) for u in results['results']]

        for u in set(urls):
            if u in stored_urls:
                urls.remove(u)
        logger.info(f'{len(urls)} new URLs found')
        return deque(urls)
    
    urls = deque([])
    if not recover:
        for i in range(1, 51):
        #    next_page = get_saved_next_url()
            next_page = f'{start_url}&page={i}'
            if next_page.startswith('/'):
                next_page = f'https://www.hemnet.se{next_page}'
            try:
                results = scrape_results(next_page)
            except Exception as e:
                logger.exception('Exception occurred on %s', next_page)
                break
            urls = get_url_objects(results)
            for u in urls:
                db.add(u)
            # We should do this now, in case we get errors for the next page
            db.commit()
    else:
        urls += deque([u for u in Url.all_unprocessed_urls()])

    while True:
        if len(urls) == 0:
            logger.info('No more URLs left to process, so cleanly exiting')
            break
        url = urls.popleft()
        try:
            out = scrape_sale_page(url)
        except Exception as e:
            logger.exception(e)
            continue

        b = Building.from_json(out)

        b = b.existing or b
        b.add_tags(out['locations'])
        db.add(b)

        a = Apartment.from_json(out)
        a.building = b
        a = a.existing or a

        s = Sale.from_json(out)
        s.apartment = a
        s.url = url
        db.add(s)
        url.processed = True
        db.add(url)
        db.commit()
        # break


if __name__ == '__main__':
    # Mölndals kommun
    # main('https://www.hemnet.se/salda/bostader?item_types%5B%5D=bostadsratt&location_ids%5B%5D=17997')
    # Göteborgs kommun
    #main('https://www.hemnet.se/salda/bostader?location_ids%5B%5D=17920&item_types%5B%5D=bostadsratt')

    urls = [
        # Mölndals kommun
#        'https://www.hemnet.se/salda/bostader?item_types%5B%5D=bostadsratt&location_ids%5B%5D=17997'
        # Göteborgs kommun
        "https://www.hemnet.se/salda/bostader?location_ids%5B%5D=17920&item_types%5B%5D=bostadsratt"
        # Johanneberg
        #"https://www.hemnet.se/salda/bostader?location_ids%5B%5D=474325&item_types%5B%5D=bostadsratt",
        # Krokslätt (Mölndal and Göteborg)
        #"https://www.hemnet.se/salda/bostader?location_ids%5B%5D=474341&location_ids%5B%5D=951331&item_types%5B%5D=bostadsratt",
        #Majorna
        #"https://www.hemnet.se/salda/bostader?location_ids%5B%5D=474311&item_types%5B%5D=bostadsratt",
        # Västra Frolunda
        #"https://www.hemnet.se/salda/bostader?location_ids%5B%5D=474361&item_types%5B%5D=bostadsratt",
        
    ]

    for u in urls:
        main(u, recover=True)

    # scrape_results('results_molndal.html')
    # out = scrape_sale_page('sold_home.html')
    # print(out)
    # #
    # b = Building.from_json(out)
    #
    # b = b.existing or b
    # b.add_tags(out['locations'])
    # db.add(b)
    #
    # a = Apartment.from_json(out)
    # a.building = b
    # a = a.existing or a
    # #
    # s = Sale.from_json(out)
    # s.apartment = a
    # db.add(s)
    # db.commit()
    # print(b, a, s)

