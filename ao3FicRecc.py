import pandas, time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

def log_in(user, pwd):
    login_url = "https://archiveofourown.org/users/login"
    chrome_options = Options()
    chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")
    #chrome_options.add_argument("--headless") 
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        print ("getting on the website")
        driver.get(login_url)
        
        print ("finding input fields")
        username_field = driver.find_element(By.CSS_SELECTOR, "#user_login")
        password_field = driver.find_element(By.CSS_SELECTOR, "#user_password")
        
        print ("entering credentials")
        username_field.send_keys(user)
        password_field.send_keys(pwd)
        
        print ("submitting the forms")
        login_form = driver.find_element(By.ID, "new_user")
        login_form.submit()
        
        if "login" in driver.current_url.lower():
            print("login failed! Check credentials.")
            time.sleep(3)
            driver.quit()
            return None

        else:
            print (driver.current_url)
            print ("login successful!")
            return driver
            
    except Exception as e:
        print(f"Error: {e}")
        return None


def gettingHistory (link, driver, dataFrame):
    print("navigating to the history page...")
    driver.get(link)

    print ("getting ready to read the page...")
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    pages = soup.find("ol", attrs={"role":"navigation"}).findAll("a")
    page_numbers = [int(a.text.strip()) for a in pages if a.text.strip().isdigit()]

    last_page = max (page_numbers) if page_numbers else 1

    for page in range (1, last_page+1):
        full_url = link + page
        print (full_url)
        driver.get(full_url)

        soup = BeautifulSoup(driver, 'html.parser')
        processBasic (soup, full_url, dataFrame)
        print ("read page " + page)



def processBasic (content, url, dataFrame):
    work_list = content.findAll ("li", {"role" : "article"})
    rows = []

    for current_work in work_list:

        id      = int (current_work.find ("h4", {"class" : "heading"}).find ("a").get ("href")[7:])
        tags    = [t.text.strip() for t in current_work.find_all  ("a", attrs={"class": "freeforms"})]
        ships   = [s.text.strip() for s in current_work.find_all  ("a", attrs={"class": "relationships"})]
        rating  = [r.text.strip() for r in current_work.find      ("span", attrs = {"class" : "help symbol question modal"})]
        fandoms = [f.text.strip() for f in current_work.find_all  ("a", attrs={"class": "tag"})]
        
        # rounds word count to the nearest 500 multiple 
        words_tag = current_work.find("dd", attrs={"class": "words"})
        words = int(words_tag.text.replace(",", "")) if words_tag else 0
        words = round(words / 500) * 500

        rows.append (id, tags, ships, rating, fandoms, words)
        
    new_rows = pandas.DataFrame(rows, columns = ["fic_id", "tags", "ships", "rating", "fandom", "word_count"])
    dataFrame = pandas.concat ([dataFrame, new_rows], ignore_index = True)

    return dataFrame
        




username = input ("user?\n")
password = input("password?\n")
linkLogin = "https://archiveofourown.org/users/login"
linkReadings = "https://archiveofourown.org/users/" + username + "/readings?page="

driver = log_in (username, password)

if driver == None:
    exit()

dataFrame = pandas.DataFrame(columns= ["fic_id", "tags", "ships", "rating", "fandom", "word_count"])

readingData = gettingHistory (linkReadings, driver, dataFrame)
driver.quit()
