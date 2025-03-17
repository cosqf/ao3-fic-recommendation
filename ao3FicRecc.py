import pandas as pd, undetected_chromedriver as uc,  time, getpass, ast
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from collections import Counter
from itertools import product

def setting_up_browser ():
    chrome_options = Options()

    driver = uc.Chrome(options=chrome_options)

    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    return driver

def log_in(user, pwd, driver):
    login_url = "https://archiveofourown.org/users/login"
    try:
        print("getting on the website")
        driver.get(login_url)
        
        wait = WebDriverWait(driver, 10)
        username_field = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#user_login")))
        password_field = driver.find_element(By.CSS_SELECTOR, "#user_password")
        
        print("entering credentials")
        username_field.send_keys(user)
        password_field.send_keys(pwd)

        time.sleep(1) 
        
        print("submitting the form")
        password_field.send_keys(Keys.RETURN) 
        
        wait.until(EC.presence_of_element_located(By.CSS_SELECTOR, "#dashboard, .flash.error"))

        error_message = driver.find_elements(By.CSS_SELECTOR, ".flash.error")
        if error_message:
            print("login failed!")
            time.sleep(5)
            driver.quit()
            return None

        print(f"login successful! current URL: {driver.current_url}")
        return driver  
                
    except Exception as e:
        print(f"Error: {e}")
        return None


def log_in(user, pwd, driver):
    login_url = "https://archiveofourown.org/users/login"
    try:
        print ("getting on the website")
        driver.get(login_url)
        
        wait = WebDriverWait(driver, 10)
        username_field = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#user_login")))
        password_field = driver.find_element(By.CSS_SELECTOR, "#user_password")
        
        print ("entering credentials")
        username_field.send_keys(user)
        password_field.send_keys(pwd)
        
        print ("submitting the forms")

        login_form = driver.find_element(By.ID, "new_user")
        login_form.submit()
        
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#dashboard"))) 
 
        error_message = driver.find_elements(By.CSS_SELECTOR, ".flash.error") 
        if error_message:
            print("login failed!")
            time.sleep(5)
            driver.quit()
            return None

        print(f"login successful! current url: {driver.current_url}")
        return driver  
                
    except Exception as e:
        print(f"Error: {e}")
        return None


def gettingHistory (link, driver):
    print("navigating to the history page")
    driver.get(link + str(1))

    wait = WebDriverWait(driver, 15)
    wait.until(EC.visibility_of_element_located((By.XPATH, '''//*[@id="main"]/h2'''))) # "history" header

    print ("getting ready to read the history...")

    #driver = open ("saved_pages/History.html", "r", encoding="utf-8") # debug

    soup = BeautifulSoup(driver.page_source, "html.parser")

    pag = soup.find(class_="pagination actions pagy").find_all("li")
    last_number =  len(pag) - 2
    last_page = int (pag[last_number].get_text(strip=True))

    print ("total pages:", last_page)
    print ("starting to read")
    for page in range (1, last_page + 1):
        full_url = link + str(page)
        driver.get(full_url)

        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,"#main > ol.reading.work.index.group"))) 
        
        # saving pages
        html = driver.page_source
        f = open ("saved_pages/" + username + "_page_"+ str (page) + ".html", "w", encoding="utf-8")
        f.write (html)

        print ("page " + str(page) + " read")
    print ("reading finished")
    return last_page



def processWorks (html, dataFrame):
    content = BeautifulSoup(html, "html.parser")
    work_list = content.find_all ("li", {"role" : "article"})
    rows = []
    for current_work in work_list:
        if "deleted" in current_work.get("class", []):
            continue
        
        id        = int (current_work.find ("h4", {"class" : "heading"}).find ("a").get ("href")[7:])

        all_ships = current_work.find_all ("li", class_= "relationships")
        ships     = [ship.find ("a", class_ = "tag").text.strip() for ship in all_ships]

        rating    = current_work.find("a", class_="help symbol question modal modal-attached").find("span", class_="text").text.strip()

        all_tags  = current_work.find_all("li", class_="freeforms")
        tags      = [tag.find("a", class_="tag").text.strip() for tag in all_tags]

        fandoms   = [f.text.strip() for f in current_work.find("h5", class_="fandoms heading").find_all("a", class_="tag")]
        
        # rounds word count to the nearest 1000 multiple 
        words_tag = current_work.find("dd", attrs={"class": "words"})
        words = int(words_tag.text.replace(",", "")) if words_tag else 0
        words = round(words / 1000) * 1000 if (words > 1000) else 1000

        rows.append([id, ships, rating, tags, fandoms, words])

    new_rows = pd.DataFrame(rows, columns = ["fic_id", "ships", "rating", "tags", "fandom", "word_count"])
    dataFrame = pd.concat ([dataFrame, new_rows], ignore_index = True)
    return dataFrame
        
# checkpoints
login = True
read = True

if login:
    driver = setting_up_browser()
    username = input ("User: ")
    password = getpass.getpass('Password:')

    linkLogin = "https://archiveofourown.org/users/login"
    linkReadings = "https://archiveofourown.org/users/" + username + "/readings?page="

    driver = log_in (username, password, driver)

    if driver == None:
        exit()

    pagesTotal = gettingHistory (linkReadings, driver)
else:
    username = input ("User: ")
    pagesTotal = 41 # temporary number

dataFrame = pd.DataFrame(columns= ["fic_id", "ships", "rating", "tags", "fandom", "word_count"])


if read:
    for page in range(1, pagesTotal+1):
        with open ("saved_pages/" + username + "_page_"+ str (page) + ".html", "r", encoding="utf-8") as f:
            try:
                print ("beginning to read the page ", page)
                dataFrame = processWorks(f, dataFrame)

            except Exception as e:
                print(f"Error: {e}")
                pagesTotal = page
                break

    dataFrame.to_csv (username + "_history_data.csv")
else:
    dataFrame = pd.read_csv (username + "_history_data.csv")



#############

#converting strings into actual lists
for col in ["ships", "tags", "fandom"]:
    dataFrame[col] = dataFrame[col].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)


# counting the most common
tag_counts = Counter(tag.lower().strip() for tags in dataFrame["tags"] for tag in tags)
ship_counts = Counter(ship.lower().strip() for ships in dataFrame["ships"] for ship in ships)

print ("Top 10 most common tags:",  tag_counts.most_common(10))
print ("\nTop 10 most common ships:", ship_counts.most_common(10))

print ("\nAverage number of words read is", int (dataFrame["word_count"].mean()))

print ("And the total words read is", int (dataFrame["word_count"].sum()))



print ("\nThe fandom percentage is:")
all_fandoms = [f for fandoms in dataFrame["fandom"] for f in fandoms]

fandom_counts = pd.Series(all_fandoms).value_counts()

fandom_percentages =  round((fandom_counts / len(dataFrame)) * 100)

print(fandom_percentages.head(10))


print ("\nThe most common ship-tag combos are:")

tag_ship_pairs = []
for _, row in dataFrame.iterrows():
    tags = row["tags"]
    ships = row["ships"]
    if tags and ships:
        tag_ship_pairs.extend(list(product(tags, ships)))

pairs = pd.DataFrame(tag_ship_pairs, columns=["tag", "ship"])
tag_ship_counts = pairs.value_counts().reset_index(name="count")

print(tag_ship_counts.head(10))

#driver.quit()

