from wrapped import askForShip, giveWrapped, generate_common_ship_tags
from web import logIn, gettingHistory, checkBookmarks, scrap_unread_fics, printWorkInfo
from web_utils import settingUpBrowser
from recommendation import create_user_profile_from_history, score_unread_fanfics
import pandas as pd
import getpass, os, warnings
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from config import WORK_DF_COL

warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries is deprecated.",
    category=FutureWarning
)
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

os.makedirs("data", exist_ok=True)

username = input ("User: ").lower().strip()

with Stealth().use_sync(sync_playwright()) as pw:
    page = settingUpBrowser(pw)
    password = getpass.getpass('Password:')

    try:
        oldDf = pd.read_json ("data/" + username + "_history_data.json")
        oldDf['last_visited'] = pd.to_datetime(oldDf['last_visited'], errors='coerce')
        print (f"history saved locally found with {len(oldDf)} works, fetching more...")
    except FileNotFoundError:
        print ("no history saved locally, fetching it all...")
        oldDf = pd.DataFrame(columns= WORK_DF_COL)

    page = logIn (username, password, page)
    dataFrame = gettingHistory (page, username, oldDf)
    checkBookmarks (username, dataFrame, page)
    dataFrame['bookmarked'] = dataFrame['bookmarked'].astype(bool)
    dataFrame.to_json ("data/" + username + "_history_data.json",  date_format='iso')


    giveWrapped (dataFrame)

    user_profile_vector, fitted_model_components = create_user_profile_from_history(dataFrame)
    #print("User Profile Vector (top 10 features):")
    #print(user_profile_vector.sort_values(ascending=False).head(10))

    print ("Let's start the recommendation part now, you'll need to insert the ship you want to get fics recommended for.")
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

        df_unread_fics = scrap_unread_fics (page, dataFrame, tag_ship_counts, ship_tag)
        df_scored_unread_fics = score_unread_fanfics (df_unread_fics, user_profile_vector, fitted_model_components)

        numberTopWorks = len(df_scored_unread_fics)
        if numberTopWorks == 0:
            print("No unread fics scored.")
            exit()
        
        topx = numberTopWorks if numberTopWorks < 10 else 10
        topx_work_ids = df_scored_unread_fics['fic_id'].head(topx)

        for i in range (topx):
            printWorkInfo (topx_work_ids.iloc[i], page, i+1)

        filterAgain = ""
        while filterAgain not in ["Y", "N"]:
            filterAgain = input ("Choose a different ship? (Y/N): ").strip().upper()
        if filterAgain == "N":
            break
    page.close()

print ("closing program!")
