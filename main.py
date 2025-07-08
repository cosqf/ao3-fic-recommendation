from wrapped import giveUserInfo, askForDate, askForFandom, askForShip, askForExplicit
from web import settingUpBrowser, logIn, gettingHistory, checkBookmarks
import pandas as pd
import getpass
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import os

login = True

dataFrame = pd.DataFrame(columns= ["fic_id", "ships", "rating", "tags", "fandom", "word_count", "last_visited", "bookmarked"])

os.makedirs("data", exist_ok=True)

username = input ("User: ").lower().strip()
if login:
    with Stealth().use_sync(sync_playwright()) as pw:
        page = settingUpBrowser(pw)
        password = getpass.getpass('Password:')

        page = logIn (username, password, page)
        dataFrame = gettingHistory (page, username, dataFrame)
        checkBookmarks (username, dataFrame, page)
        page.close()
        
        dataFrame.to_json ("data/" + username + "_history_data.json")
else:
    dataFrame = pd.read_json ("data/" + username + "_history_data.json")

while True:
    dateFilter = askForDate()
    fandomFilter = askForFandom(dataFrame)
    shipFilter = askForShip (dataFrame)
    explicitFilter = askForExplicit ()

    giveUserInfo (dataFrame, dateFilter, fandomFilter, shipFilter, explicitFilter)
    filterAgain = ""
    while filterAgain not in ["Y", "N"]:
        filterAgain = input ("Choose different filters? (Y/N): ").strip().upper()
    if filterAgain == "N":
        break