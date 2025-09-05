import time
from web_utils import *
import pandas as pd
from config import WORK_DF_COL

def logIn(user, pwd, page):
    login_url = "https://archiveofourown.org/users/login"
    try:
        page.goto(login_url)

        page.fill("#user_login", user)
        page.fill("#user_password", pwd)

        print ("logging in...")

        page.locator ("#new_user > dl > dd.submit.actions > input").click()
       
        error_alert = page.locator(".flash.alert")
        if error_alert.count() > 0 and error_alert.is_visible():
            print("login failed!", error_alert.inner_text())
            page.close()
            exit()
             
        error_flash = page.locator(".flash.error")
        if error_flash.count() > 0 and error_flash.is_visible():
            print("login failed!", error_flash.inner_text())
            page.close()
            exit()

        page.wait_for_selector("#dashboard") 

        print(f"login successful! current url: {page.url}")
        return page  
                
    except Exception as e:
        print(f"Error: {e}")
        exit()


def gettingHistory(page, username, oldDf):
    link_base = f"https://archiveofourown.org/users/{username}/readings?page="
    
    print("Getting ready to read the history...")

    scraped_history_fics = scrape_works(
        page,
        link_base,
        pagination_selector=".pagination.actions.pagy",
        work_list_selector="#main > ol.reading.work.index.group", 
        is_processing_history=True,
        history_df=oldDf
    )

    dataFrame = pd.concat([oldDf, scraped_history_fics], ignore_index=True)
    dataFrame.dropna(subset=['fic_id'], inplace=True)
    print("finished reading history")
    return dataFrame


def scrape_works(page, base_url_full_query, pagination_selector, work_list_selector, is_processing_history, history_df, max_number_works = None):
    all_processed_rows = []
    stored_num_works = 0
    print(f"Navigating to the first page: {base_url_full_query}1")
    page.goto(base_url_full_query + "1")
    page.wait_for_selector("h2.heading")

    last_page = get_number_of_pages_from_pagination(page, pagination_selector)

    keepGoing = True
    print("total pages to read: ", last_page)
    print("starting to read")
    for p in range(1, last_page + 1):
        current_page_url = base_url_full_query + str(p)
        page.goto(current_page_url)
        try:
            page.wait_for_selector("h2.heading")

            works_main_container = page.locator(work_list_selector)
            if works_main_container.count() < 1:
                print(f"No works found on page {p}, skipping...")
                continue # page might be empty or error

            work_list = page.locator("li[role='article']") 
            work_count_on_page = work_list.count()
            if work_count_on_page == 0:
                print(f"No works found on page {p}, skipping...")
                continue # filter too intense or no results
            
        except Exception as e:
            print (f"Error loading page {p}, waiting and skipping... {e}")
            time.sleep(30) 
            continue

        print(f"processing {work_count_on_page} works on page {p}")
        rows_on_page = []
        for i in range(work_count_on_page):
            try:
                work = work_list.nth(i)
                processed_work = processWork(work, is_processing_history)

                if processed_work == []:
                    continue
                if (history_df['fic_id'] == processed_work[0]).any():
                    if is_processing_history:
                        print (f"-- stopping early! at work {i+1} on page {p}")
                        keepGoing = False
                        break # stop early if there's already saved history
                    else:
                        continue # logic for unread fics: ignore already saved works
                
                rows_on_page.append(processed_work)
                stored_num_works += 1
            except Exception as e:
                print(f"Error processing work {i+1} on page {p}: {e}. Waiting and skipping...")
                time.sleep(15) 
                continue

        if keepGoing == False:
            break
        all_processed_rows.append(pd.DataFrame(rows_on_page, columns=["fic_id", "rating", "orientations", "fandom", "ships", "tags", "word_count", "last_visited", "bookmarked"]))
        
        if max_number_works is not None and stored_num_works >= max_number_works:
            break
    if all_processed_rows:
        return pd.concat(all_processed_rows, ignore_index=True)
    else:
        return pd.DataFrame(columns=WORK_DF_COL)


def processWork(work, is_history : bool):
    if "deleted" in work.get_attribute("class"):
        print ("- deleted work found, skipping...")
        return []

    if work.locator("div.mystery.header.picture.module").count() > 0:
        print("- mystery work found, skipping...")
        return []
    
    id = int (work.get_attribute("id")[5:])

    all_ships = work.locator("li.relationships").all()
    ships = [ship.locator("a.tag").inner_text().strip() for ship in all_ships]

    rating = work.locator("ul.required-tags li").nth(0).inner_text().strip()

    orientations = [o.inner_text().strip() for o in work.locator("ul.required-tags li").nth(2).all()]

    all_tags = work.locator("li.freeforms").all()
    tags = []
    for tag in all_tags:
        if tag.locator("a.tag").count() > 0:
            tags.append(tag.locator("a.tag").inner_text(timeout=2000).strip())


    fandoms = [f.inner_text().strip() for f in work.locator("h5.fandoms.heading a.tag").all()]
    fandoms.sort()
    
    words_tag = work.locator("dd.words")
    words = int (words_tag.inner_text().replace(",", "") if words_tag.count() > 0 else "0")
 
    if is_history:
        last_visited = work.locator("div.user.module.group h4.viewed.heading").inner_text()
        parsed_date = extract_and_parse_last_visited (last_visited)
        if parsed_date is None:
            return []
    else:
        parsed_date = None

    bookmark = False
    return [id, rating, orientations, fandoms, ships, tags, words, parsed_date, bookmark]


def scrap_unread_fics(page, history_df, tag_ship_counts, ship_tag):
    max_number_fics = 200
    print (f"\nWill now fetch {max_number_fics} unread fanfics for scoring.")
    base_search_url = 'https://archiveofourown.org/works/search?'
    number_tags = 5

    formatted_tags, formatted_ship_tag = format_unread_fic_tags (number_tags, tag_ship_counts, ship_tag)

    unread_df = pd.DataFrame(columns=WORK_DF_COL)

    while len (unread_df) < max_number_fics and number_tags >= 0:
        current_url_query = f"work_search%5Brelationship_names%5D={formatted_ship_tag}&work_search%5Bfreeform_names%5D="
        
        for t in range(number_tags):
            current_url_query = f"{current_url_query}%2C{formatted_tags[t]}"

        current_url_query += "&work_search%5Bsort_column%5D=kudos_count&commit=Search&page="
        full_base_url = base_search_url + current_url_query

        print(f"searching with {number_tags} tags")

        number_works_to_read = max_number_fics - len (unread_df)

        newly_scraped_fics = scrape_works(
            page,
            full_base_url,
            pagination_selector = "ol.pagination.actions",
            work_list_selector = "#main > ol.work.index.group",
            is_processing_history = False, 
            history_df = pd.concat([history_df, unread_df]),
            max_number_works = 100 if number_works_to_read > 100 else number_works_to_read
        )
        newly_scraped_fics.drop_duplicates(subset=['fic_id'], inplace=True)
        existing_fic_ids = unread_df['fic_id'].unique()
        newly_scraped_fics = newly_scraped_fics[~newly_scraped_fics['fic_id'].isin(existing_fic_ids)]

        unread_df = pd.concat([unread_df, newly_scraped_fics], ignore_index=True)
        print(f"currently have {len (unread_df)} unread fics stored\n")

        number_tags -= 1 

    print(f"Finished getting unread fics, with {len (unread_df)} fics")
    return unread_df

            
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
            try:
                if "deleted" in work.get_attribute("class"): 
                    continue

                work_link_locator = work.locator("h4.heading a[href^='/works/']")
                work_link_locator.wait_for(state="attached", timeout=15000)

                id = int (work_link_locator.get_attribute("href", timeout=5000)[7:])
                dataframe.loc[dataframe["fic_id"] == id, "bookmarked"] = True
            except Exception as e:
                print(f"Error processing work {i+1} on page {pageNumber}: {e}. Waiting and skipping...")
                time.sleep(30) 
                continue
        print(f"page {pageNumber} of bookmarks read")

        # check if has seen all pages 
        numberUsersHeader = page.locator("#main > h2").text_content()
        if numberUsersHeader:
            if len(numberUsersHeader.split("-")) == 1: #only one page to check
                break
            numberKudos = numberUsersHeader.split("-")[1].split(" ")
        else:
            print ("error reading page")
            break
        
        if (int (numberKudos[1].replace(",", "")) >= int (numberKudos[3].replace(",", ""))): # reached the end
            break

        pageNumber +=1
    print ("finished checking bookmarks")


def printWorkInfo(work_id, page, i):
    base_url = "https://archiveofourown.org/works/"
    full_url = f"{base_url}{work_id}"
    print("\n------------------------")
    print(f"Suggestion {i}\n")
    page.goto(full_url)

    if page.url == "https://archiveofourown.org/users/login?restricted=true": # work is only available for logged in users
        print ("Work is private, details hidden! Check it out:")
        print (full_url)
    else:
        try:
            if check_for_nsfw_warning(page):
                title, author, summary = get_info_nsfw_work (page)
            else:
                title, author, summary = get_info_work (page)
        except Exception as e:
            print(f"Failed to fetch work in: {full_url}\n{e}")
            return

        print(f"Title: '{title}' by {', '.join(author)}")
        print(f"Summary:\n-- {summary} --\n")
        print(full_url)


def check_for_nsfw_warning(page):
    try:
        nsfw_heading = page.locator("p.caution.notice")
        nsfw_heading.wait_for(state="visible", timeout=3000)
        return True
    except Exception:
        return False
    
def get_info_nsfw_work (page):
    work_locator = page.locator ("ol.work.index.group")
    work_locator.wait_for(state="attached", timeout=10000)

    title = work_locator.locator("h4.heading > a:nth-of-type(1)").inner_text().strip()

    author_locator = work_locator.locator("h4.heading > a[rel='author']")
    author = author_locator.all_text_contents()
    if not author:
        author = [work_locator.locator('h4.heading').inner_text()]
        author = [a.replace('by ', '').strip() for a in author] 

    all_summary_blocks = work_locator.locator("blockquote.userstuff.summary").all()
    summary_parts = [block.inner_text() for block in all_summary_blocks]
    summary = "".join(summary_parts).strip()

    return title, author, summary


def get_info_work (page):
    preface_locator = page.locator("#workskin > div.preface.group:first-of-type")
    preface_locator.wait_for(state="attached", timeout=10000)

    title = preface_locator.locator("h2.title.heading").inner_text().strip()
    
    author_locator = preface_locator.locator('h3.byline.heading a[rel="author"]')
    author = author_locator.all_text_contents()
    if not author:
        author = [preface_locator.locator('h3.byline.heading').inner_text()]
        author = [a.replace('by ', '').strip() for a in author] 

    all_summary_blocks = preface_locator.locator("div.summary.module blockquote.userstuff").all()
    summary_parts = [block.inner_text() for block in all_summary_blocks]
    summary = "".join(summary_parts).strip()

    return title, author, summary
