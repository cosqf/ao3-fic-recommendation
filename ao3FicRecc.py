import pandas as pd, time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import getpass
from collections import Counter

def setting_up_browser ():
    chrome_options = Options()
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")
    chrome_options.page_load_strategy = 'none' # for faster loading
    #chrome_options.add_argument("--headless") 
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")  # Avoid detection
    service = Service("/usr/bin/chromedriver")  
    driver = webdriver.Chrome(service=service, options=chrome_options)

    return driver

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

        error_message = driver.find_elements(By.CSS_SELECTOR, ".flash.error")  # AO3 shows login errors with this class
        if error_message:
            print("login failed!")
            time.sleep(5)
            driver.quit()
            return None

        print(f"login successful! current url: {driver.current_url}")
        return driver  # Return the driver if login was successful
                
    except Exception as e:
        print(f"Error: {e}")
        return None


def gettingHistory (link, driver):
    print("navigating to the history page")
    driver.get(link + str(1))

    wait = WebDriverWait(driver, 15)
    wait.until(EC.visibility_of_element_located((By.XPATH, '''//*[@id="main"]/h2'''))) # "history" header

    print ("getting ready to read the page...")

    #driver = open ("saved_pages/History.html", "r", encoding="utf-8") # debug

    soup = BeautifulSoup(driver.page_source, "html.parser")
    last_page = int (soup.find(class_="pagination actions pagy").find_all("li")[9].a.get_text(strip=True))

    print (f"total pages: {last_page}")
    print ("starting to read")
    for page in range (1, last_page + 1):
        full_url = link + str(page)
        driver.get(full_url)

        wait.until(EC.url_contains(str(page)))

        time.sleep(3)
        # saving pages
        html = driver.page_source
        f = open ("saved_pages/page_"+ str (page) + ".html", "w", encoding="utf-8")
        f.write (html)

        print ("page " + str(page) + " read")
    print ("reading finished")
    return last_page



def processWorks (html, dataFrame):
    content = BeautifulSoup(html, "html.parser")
    print ("beginning to read the page")
    work_list = content.find_all ("li", {"role" : "article"})
    rows = []
    count = 1
    #print (str(len (work_list)) + " works in this page")
    for current_work in work_list:
        if "deleted" in current_work.get("class", []):
            continue
        
        id        = int (current_work.find ("h4", {"class" : "heading"}).find ("a").get ("href")[7:])

        all_tags  = current_work.find_all("li", class_="freeforms")
        tags      = [tag.find("a", class_="tag").text.strip() for tag in all_tags]

        all_ships = current_work.find_all ("li", class_= "relationships")
        ships     = [ship.find ("a", class_ = "tag").text.strip() for ship in all_ships]

        rating    = current_work.find("a", class_="help symbol question modal modal-attached").find("span", class_="text").text.strip()
        fandoms   = [f.text.strip() for f in current_work.find("h5", class_="fandoms heading").find_all("a", class_="tag")]
        
        # rounds word count to the nearest 1000 multiple 
        words_tag = current_work.find("dd", attrs={"class": "words"})
        words = int(words_tag.text.replace(",", "")) if words_tag else 0
        words = round(words / 1000) * 1000 if (words > 1000) else 1000

        rows.append([id, tags, ships, rating, fandoms, words])
        count += 1
    #print (rows)
    new_rows = pd.DataFrame(rows, columns = ["fic_id", "tags", "ships", "rating", "fandom", "word_count"])
    dataFrame = pd.concat ([dataFrame, new_rows], ignore_index = True)
    return dataFrame
        
# checkpoints
login = False
read = False
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
    pagesTotal = 41

dataFrame = pd.DataFrame(columns= ["fic_id", "tags", "ships", "rating", "fandom", "word_count"])
if read:
    for page in range(1, pagesTotal):
        with open ("saved_pages/page_"+ str (page) + ".html", "r", encoding="utf-8") as f:
            dataFrame = processWorks(f, dataFrame)

    dataFrame.to_csv ("history_data.csv")
else:
    dataFrame = pd.read_csv ("history_data.csv")



#############

dataFrame["tags"] = dataFrame["tags"].str.replace(r"[\'\"\[\]]", "", regex=True)  # Remove quotes and brackets

all_tags = [tag.strip().lower() for sublist in dataFrame["tags"].dropna().str.split(", ") for tag in sublist if tag.strip()]

tag_counts = Counter(all_tags)

top_10_tags = tag_counts.most_common(10)
print("Top 10 most common tags:", top_10_tags)

sum = 0
counter = 0
for w in dataFrame["word_count"]:
    counter += 1
    sum += w
average_words = sum/counter

print ("\nAverage number of words read is "+ str(int (average_words)))

#driver.quit()

