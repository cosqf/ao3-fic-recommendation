from wrapped import giveUserInfo
from web import settingUpBrowser, logIn, gettingHistory
from userData import processWorks
from imports import pd,getpass

login = False
read = False

username = input ("User: ")
if login:
    driver = settingUpBrowser()
    password = getpass.getpass('Password:')

    driver = logIn (username, password, driver)
    pagesTotal = gettingHistory (driver, username)

    driver.quit()
else:
    pagesTotal = 41 # test number


dataFrame = pd.DataFrame(columns= ["fic_id", "ships", "rating", "tags", "fandom", "word_count"])


if read:
    for page in range(1, pagesTotal+1):
        with open ("data/" + username + "_page_"+ str (page) + ".html", "r", encoding="utf-8") as f:
            try:
                print ("beginning to read the page ", page)
                dataFrame = processWorks(f, dataFrame)

            except Exception as e:
                print(f"Error: {e}")
                pagesTotal = page
                break

    dataFrame.to_csv ("data/" + username + "_history_data.csv")
else:
    dataFrame = pd.read_csv ("data/" + username + "_history_data.csv")


giveUserInfo (dataFrame)