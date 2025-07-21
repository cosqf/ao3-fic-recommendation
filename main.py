from wrapped import askForShip, giveWrapped, generate_common_ship_tags
from web import settingUpBrowser, logIn, gettingHistory, checkBookmarks, scrap_unread_fics
from recommendation import create_user_profile_from_history, score_unread_fanfics
import pandas as pd
import getpass
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
import os
import warnings

warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.",
    category=FutureWarning
)

login = True
wrapped = True

dataFrame = pd.DataFrame(columns= ["fic_id", "rating", "orientations" ,"fandom", "ships", "tags",  "word_count", "last_visited", "bookmarked"])

os.makedirs("data", exist_ok=True)

username = input ("User: ").lower().strip()
if login:
    with Stealth().use_sync(sync_playwright()) as pw:
        page = settingUpBrowser(pw)
        password = getpass.getpass('Password:')

        page = logIn (username, password, page)
        dataFrame = gettingHistory (page, username, dataFrame)
        checkBookmarks (username, dataFrame, page)
        dataFrame['bookmarked'] = dataFrame['bookmarked'].astype(bool)
        page.close()
        
        dataFrame.to_json ("data/" + username + "_history_data.json",  date_format='iso')
else:
    dataFrame = pd.read_json ("data/" + username + "_history_data.json")
    dataFrame['last_visited'] = pd.to_datetime(dataFrame['last_visited'], errors='coerce')

if wrapped:
    giveWrapped (dataFrame)

user_profile_vector, fitted_model_components = create_user_profile_from_history(dataFrame)

#print("User Profile Vector (top 10 features):")
#print(user_profile_vector.sort_values(ascending=False).head(10))

print ("Let's start the recommendation part now, insert the ship you want to get fics recommended for.")
while True:
    ship_mask, ship_tag = askForShip (dataFrame, False)
    tag_ship_counts = generate_common_ship_tags(dataFrame, ship_tag)

    if tag_ship_counts.empty:
        print ("Ship doesn't exist")
        tryAgain = ''
        while tryAgain not in ['Y', 'N']:
            print ("Try again? (Y/N) ")
            tryAgain = input().strip().upper()
        if tryAgain == 'Y':
            continue
        elif tryAgain == 'N':
            break
    else:
        break

with Stealth().use_sync(sync_playwright()) as pw:
    df_unread_fics = scrap_unread_fics (settingUpBrowser(pw), dataFrame, tag_ship_counts, ship_tag)
    
    dataFrame['last_visited'] = pd.to_datetime(dataFrame['last_visited'], errors='coerce')
    df_scored_unread_fics = score_unread_fanfics (df_unread_fics, user_profile_vector, fitted_model_components)

    print (df_scored_unread_fics.head(10))
