from wrapped import askForShip, giveWrapped, generate_common_ship_tags
from web import logIn, gettingHistory, checkBookmarks, scrap_unread_fics, printWorkInfo
from web_utils import settingUpBrowser
from recommendation import create_user_profile_from_history, score_unread_fanfics
import pandas as pd
import getpass, os, warnings
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth
from config import WORK_DF_COL
import streamlit as st 
from pages.Intro import intro
from pages.Get_History import get_history

def main():
    # setup
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
        dataFrame['last_visited'] = pd.to_datetime(dataFrame['last_visited'], errors='coerce')


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
            
            loggedOutpage = settingUpBrowser(pw)
            for i in range (topx):
                printWorkInfo (topx_work_ids.iloc[i], loggedOutpage, i+1)
            loggedOutpage.close()

            filterAgain = ""
            while filterAgain not in ["Y", "N"]:
                filterAgain = input ("Choose a different ship? (Y/N): ").strip().upper()
            if filterAgain == "N":
                break
        page.close()

    print ("closing program!")

THEMES = {
    "light": {
        "--c-dot":       "#f4edd2",
        "--c-container": "#fffdf9",
        "--c-border":    "#dcd1b4",
        "--c-shadow":    "rgba(43,38,31,0.05)",
        "--c-accent":    "#8c2d19",
        "--c-heading":   "#4a150b",
        "--c-body":      "#3d352a",
        "--c-muted":     "#8c7e6b",
        "--c-btn-bg":    "#4a150b",
        "--c-btn-text":  "#fcf8f2",
    },
    "dark": {
        "--c-dot":       "#1e1a12",
        "--c-container": "#1c1710",
        "--c-border":    "#3a2f1e",
        "--c-shadow":    "rgba(0,0,0,0.45)",
        "--c-accent":    "#a33520",
        "--c-heading":   "#c9a87a",
        "--c-body":      "#c2b59e",
        "--c-muted":     "#6b5c42",
        "--c-btn-bg":    "#a33520",
        "--c-btn-text":  "#f0e6d3",
    },
}

def main2():
    st.set_page_config(page_title="AO3 Stats", layout="centered")
    
    # defaults
    if "username" not in st.session_state:
        st.session_state.username = ""
    if "df" not in st.session_state:
        st.session_state.df = None
    if "current_page" not in st.session_state:
        st.session_state.current_page = "intro"
    if "theme" not in st.session_state:
        st.session_state.theme = "light"

    # theme
    theme = st.context.theme.type          # "light" or "dark"
    with open(f"styles/{theme}.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # routing
    print (st.session_state.current_page)
    routes = {
        "intro":    intro,
        "progress": get_history,
    }

    page = st.session_state.current_page
    if page in routes:
        routes[page]()
    else:
        st.error(f"Unknown page: {page}")
    


if __name__ == "__main__":
    main2()