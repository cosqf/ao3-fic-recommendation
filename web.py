import time
from playwright.sync_api import Playwright
import pandas as pd

def settingUpBrowser (pw: Playwright):
        agent = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
        browser = pw.chromium.launch(headless=True).new_context(user_agent=agent)
        return browser.new_page()

def logIn(user, pwd, page):
    login_url = "https://archiveofourown.org/users/login"
    try:
        print ("getting on the website")
        page.goto(login_url)

        page.fill("#user_login", user)
        page.fill("#user_password", pwd)

        print ("logging in...")

        page.locator ("#new_user > dl > dd.submit.actions > input").click()
       
        error_alert = page.locator(".flash.alert")
        if error_alert.count() > 0 and error_alert.is_visible():
            print("login failed!", error_alert.inner_text())
            time.sleep(5)
            page.close()
            exit()
             
        error_flash = page.locator(".flash.error")
        if error_flash.count() > 0 and error_flash.is_visible():
            print("login failed!", error_flash.inner_text())
            time.sleep(5)
            page.close()
            exit()

        page.wait_for_selector("#dashboard") 

        print(f"login successful! current url: {page.url}")
        return page  
                
    except Exception as e:
        print(f"Error: {e}")
        exit()


def gettingHistory (page, username, dataFrame):
    link_base = f"https://archiveofourown.org/users/{username}/readings?page="
    print("Navigating to the history page...")
    page.goto(link_base + "1")

    print("Getting ready to read the history...")

    page.wait_for_selector(".pagination.actions.pagy")

    pagination_items = page.locator(".pagination.actions.pagy li")
    count = pagination_items.count()
    if count < 3:
        print("error reading history page")
        exit()

    last_page = int (pagination_items.nth(count - 2).inner_text())
    print("total pages:", last_page)
    print("starting to read")

    for p in range(1, last_page + 1):
        full_url = link_base + str(p)
        # time.sleep(random.uniform(5, 10)) 
        page.goto(full_url)

        page.wait_for_selector("#main > ol.reading.work.index.group")
        work_list = page.locator("li[role='article']")
        count = work_list.count()
        if count == 0:
            print (f"error loading page {p}, skipping...")
            continue
        rows = []
        for i in range (count):
            work = work_list.nth (i)
            try:
                processWork (work, rows)
            except Exception as e:
                print (f"Error processing work {i} of page {p}: {e}. Waiting and skipping...\n")
                time.sleep (30)
                continue

        new_rows = pd.DataFrame(rows, columns = ["fic_id", "rating", "orientations" ,"fandom", "ships", "tags",  "word_count", "last_visited", "bookmarked"])
        dataFrame = pd.concat ([dataFrame, new_rows], ignore_index = True)

        print(f"Page {p} read")

    print("reading finished")
    return dataFrame


def processWork(work, rows):
    if "deleted" in work.get_attribute("class"): 
        return
    
    work_link_locator = work.locator("h4.heading a[href^='/works/']")
    work_link_locator.wait_for(state="attached", timeout=15000)

    id = int (work_link_locator.get_attribute("href", timeout=5000)[7:])

    all_ships = work.locator("li.relationships").all()
    ships = [ship.locator("a.tag").inner_text().strip() for ship in all_ships]

    rating = work.locator("ul.required-tags li").nth(0).inner_text().strip()

    orientations = [o.inner_text().strip() for o in work.locator("ul.required-tags li").nth(2).all()]

    all_tags = work.locator("li.freeforms").all()
    tags = [tag.locator("a.tag").inner_text().strip() for tag in all_tags]

    fandoms = [f.inner_text().strip() for f in work.locator("h5.fandoms.heading a.tag").all()]
    fandoms.sort()
    
    # rounds word count to the nearest 1000 multiple 
    words_tag = work.locator("dd.words")
    words_text = words_tag.inner_text().replace(",", "") if words_tag.count() > 0 else "0"
    words = int(words_text)
    words = round(words / 1000) * 1000 if (words > 1000) else 1000

    last_visited = work.locator ("div.user.module.group h4.viewed.heading").inner_text().split(" ")[2:5]
    last_visited = ' '.join (last_visited)
    parsed_date = pd.to_datetime(last_visited, format="%d %b %Y")
    
    bookmark = False
    rows.append([id, rating, orientations, fandoms, ships, tags, words, parsed_date, bookmark])


def checkBookmarks (username, dataframe : pd.DataFrame, page):
    print ("checking bookmarks")
    base_url = f"https://archiveofourown.org/users/{username}/bookmarks?page="
    pageNumber = 1
    while True:
        url = base_url + str(pageNumber)
        page.goto(url)
        
        work_list = page.locator("li[role='article']")
        count = work_list.count()
        
        for i in range (count):
            work = work_list.nth (i)
            if "deleted" in work.get_attribute("class"): 
                continue
            id = int(work.locator("h4.heading a[href^='/works/']").get_attribute("href")[7:])
            dataframe.loc[dataframe["fic_id"] == id, "bookmarked"] = True

        # check if has seen all pages 
        numberUsersHeader = page.locator("#main > h2").text_content()
        if numberUsersHeader:
            if len(numberUsersHeader.split("-")) == 1: #only one page to check
                page.close()
                break
            numberKudos = numberUsersHeader.split("-")[1].split(" ")
        else:
            print ("error reading page")
            break
        
        if (int (numberKudos[1].replace(",", "")) >= int (numberKudos[3].replace(",", ""))): # reached the end
            page.close()
            break

        print(f"Page {pageNumber} of bookmarks read")
        pageNumber +=1
