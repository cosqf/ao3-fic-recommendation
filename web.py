from imports import WebDriverWait, time, EC, By, uc, Options, BeautifulSoup

def settingUpBrowser ():
    options = Options()
    agent = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
    driver = uc.Chrome(options=options)
    return driver


def logIn(user, pwd, driver):
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
            exit()

        print(f"login successful! current url: {driver.current_url}")
        return driver  
                
    except Exception as e:
        print(f"Error: {e}")
        exit()

def gettingHistory (driver, username):
    link = "https://archiveofourown.org/users/" + username + "/readings?page="
    print("navigating to the history page")
    driver.get(link + str(1))

    wait = WebDriverWait(driver, 15)
    wait.until(EC.visibility_of_element_located((By.XPATH, '''//*[@id="main"]/h2'''))) # "history" header

    print ("getting ready to read the history...")

    #driver = open ("data/History.html", "r", encoding="utf-8") # debug

    soup = BeautifulSoup(driver.page_source, "html.parser")

    pag = soup.find(class_="pagination actions pagy").find_all("li")
    last_number =  len(pag) - 2
    last_page = int (pag[last_number].get_text(strip=True))

    if last_page == 0:
        print ("Error reading history page")
        exit()

    print ("total pages:", last_page)
    print ("starting to read")
    for page in range (1, last_page + 1):
        full_url = link + str(page)
        driver.get(full_url)

        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR,"#main > ol.reading.work.index.group"))) 
        
        # saving pages
        html = driver.page_source
        f = open ("data/" + username + "_page_"+ str (page) + ".html", "w", encoding="utf-8")
        f.write (html)

        print ("page " + str(page) + " read")
    print ("reading finished")
    return last_page