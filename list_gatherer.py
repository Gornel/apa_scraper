"""
There is a hotel in Japan that will give the insanely low price of $40 per night if you book a 30 day chunk all at once.
The site only lets you search a single location and day at a time, this script will scrape as many locations and days as needed,
and translate the locations to english. Unfortunately, I think they have discontinued the offer... so this script is now just for posterity.
Youtube of the first time I ran it:  https://www.youtube.com/watch?v=cGUOLdaKBuE
"""
import requests
from bs4 import BeautifulSoup
import re
import json
from deep_translator import GoogleTranslator
from datetime import timedelta, datetime
import logging
import asyncio
import aiohttp

logging.basicConfig(filename="logfile.log", level=logging.INFO,format="%(asgctime)s %(levelname)s %(message)s")

# header that pretends to be a browser
headers = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0"}

#the settings which will be used to search, they come with default values
querySettings = {
  "subNumber": 25,
  "firstDay": 26,
  "firstMonth": 10,
  "firstYear": 2023,
  "lastDay": 28,
  "lastMonth": 10,
  "lastYear": 2023,
  "numberPeople": 1,
  "numberRooms": 1,
  "smokingRoom": 0
}        

def generate_location_lists():
    """Extracts website locations and ID's into 3 lists. Every ID has an equivalent prefecture and sub area."""
    #download webpage
    page = requests.get('https://www.apahotel.com/articles/monthly/', headers=headers, allow_redirects=False)
    #find the list of current locations in website html by turning it into a beautifulsoup to isolate the easy way
    soup = BeautifulSoup(page.text, features="lxml")
    #grab the locations section and take ids and subs out of it
    areaIndex = str(soup.find("select", class_="areasub"))
    idList = re.findall(r'\d+', areaIndex)
    subList = re.findall(r'data-val=".*</option>', areaIndex)
    
    #clean the sublist of junk chars
    for i in range(len(subList)):
        subList[i] = subList[i].replace('data-val=', '')
        subList[i] = subList[i].replace('</option>', '')
        subList[i] = subList[i].replace('"', '')
        subList[i] = re.sub(r'value=\d+', '', subList[i])
        subList[i] = subList[i].replace(' ', '')
        
    #create a list of prefectures from sublist for assembling the URL later, as it must be in japanese
    prefList = subList[:]
    for i in range(len(prefList)):
        prefList[i] = prefList[i][:prefList[i].index(">")]

    #Translate the japanese sublist into english for users
    jsonString = json.dumps(subList, ensure_ascii=False)
    engJson = GoogleTranslator(source='ja', target='en').translate(jsonString)
    #clean the translation response and organize it into a new english list
    engJson = re.sub(r'(\[|\]|\(|\))', '', engJson)
    engList = re.split(r'", "|" , "', engJson)
    engList = [s.replace('"', '').strip() for s in engList]
    
    return idList, prefList, subList, engList


def generate_URL_batch(settings: dict):
    """Creates a URL list for the dates given at a select location.
    
    Parameters
    -
    settings: The location and period of time you would like to search"""
    date = datetime(settings['firstYear'], settings['firstMonth'], settings['firstDay'])
    endDate = datetime(settings['lastYear'], settings['lastMonth'], settings['lastDay'])
    total = (endDate - date)+ timedelta(days=1) 
    url = ['']*total.days
    testListt = ["https://python.org", "https://python.org", "https://python.org"]
    for i in range(total.days):
        #subNumber has a -1 due to the offset of lists
        url[i] = (f"https://www.apahotel.com/monthly_search/?book-plan-category=11&book-no-night=30&prefsub={prefList[settings['subNumber']-1]}"
        f"&areasub={idList[settings['subNumber']-1]}&book-checkin={date}&book-no-people={settings['numberPeople']}&book-no-room={settings['numberRooms']}&book-no-children1"
        f"=&book-no-children2=&book-no-children3=&book-no-children4=&book-no-children5=&book-no-children6=&book-smoking={settings['smokingRoom']}&is_midnight=0")
        date += timedelta(days=1)
        with open(f'generatorlog.log', 'a') as f:
                f.write(f'{url[i]}\n\n')
                print(f'{url[i]}\n')
    return url

def SEARCH_EVERYTHING(settings: dict):
    """Creates a URL list of all valid dates at all locations
    
    Parameters
    -
    settings: Most settings will be overwritten by this function"""
    settings["lastDay"] = 31
    settings["lastMonth"] = 10
    settings["lastYear"] = 2023
    settings["firstDay"] = int(datetime.now().strftime("%d"))
    settings["firstMonth"] = int(datetime.now().strftime("%m"))
    settings["firstYear"] = int(datetime.now().strftime("%Y"))
    urlList = generate_URL_batch(settings)
    for i in range(len(idList)):
        #subs start at one, not zero
        settings["subNumber"] = i + 1
        urlList = urlList + generate_URL_batch(settings)
    return urlList
        

async def get_and_check_HTML(session: aiohttp.ClientSession, url: str):
    """Requests html from one url and waits. When the page arrives it is checked for vacancy
    and if found, creates a file in the current directory containing its link
    
    Parameters
    -
    session: the aiohttp session that is being used to send web requests.
    url: website url that needs to be checked.
    """
    async with session.get(url) as response:
        dump = await response.text()
        logging.info(f"searched: {url}")
        #when HTML is received, search it for availabilities and log the result
        bookings = re.search((r'<span class="big-font">[^0]</span>'), dump)
        if (bookings != None):
            bookings = re.search(r'\d+', bookings.group())
            print("FOUND ONE ON THIS DAY, NUMBER AVAIL: ", bookings.group())
            logging.warning("match found")
            #write the url with bookings to hard drive
            with open(f'targetpage__{datetime.now()}.html', 'w') as f:
                f.write(url)
         
async def main(mode: int):
    """Creates a web session and uses asynchronous functions to download requested urls.
    
    Parameters
    -
    mode: toggles the scope of the search.
    
    0 - Search a single location, 1 - Search all locations during all dates
    """
    #use fake header because we arent a bot
    async with aiohttp.ClientSession(headers=headers) as session:
        #option for searching a single location or all of them
        if mode == 0:
            queryType = generate_URL_batch(querySettings)
        if mode == 1:
            queryType = SEARCH_EVERYTHING(querySettings)
        await asyncio.gather(*[get_and_check_HTML(session, url) for url in queryType])
            
if __name__ == "__main__":
    idList, prefList, subList, engList = generate_location_lists()
    asyncio.run(main(1))