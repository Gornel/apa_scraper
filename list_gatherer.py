import requests
from bs4 import BeautifulSoup
import re
import json
from deep_translator import GoogleTranslator
from datetime import timedelta, datetime
import logging
import asyncio
import aiohttp
from time import perf_counter

logging.basicConfig(filename="logfile.log", level=logging.INFO,format="%(asgctime)s %(levelname)s %(message)s")

# header that pretends to be a browser
headers = {"User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0"}

#the settings which will be used to search, they come with default valuesg
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

#extracts locations and ID's into 3 lists. every ID has a prefecture and sub area attached
def generate_location_lists():
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


#generate a list of urls for the dates we'd like to search
def generate_URL_batch(settings: dict):
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
        
#request html from one url and wait. when page arrives check it for vacancy
async def get_and_check_HTML(session: aiohttp.ClientSession, url: str):
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
         
#make a session template and use it to activate asynchronous functions that download each url in a list
async def main(mode: int):
    #use fake header because we arent a bot
    async with aiohttp.ClientSession(headers= headers) as session:
        if mode == 0:
            await asyncio.gather(*[get_and_check_HTML(session, url) for url in generate_URL_batch(querySettings)])
        if mode == 1:
            await asyncio.gather(*[get_and_check_HTML(session, url) for url in SEARCH_EVERYTHING(querySettings)])
            
if __name__ == "__main__":
    idList, prefList, subList, engList = generate_location_lists()
    asyncio.run(main(1))