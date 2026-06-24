import time
from web_utils import *
import pandas as pd
import queue
import threading
import streamlit as st
from config import WORK_DF_COL
import math

def logIn(worker, user, pwd, status_widget=None):
    report("logging in...", status_widget)

    def _login(page):
        login_url = "https://archiveofourown.org/users/login"
        page.goto(login_url)

        page.fill("#user_login", user)
        page.fill("#user_password", pwd)
        page.locator("#new_user > dl > dd.submit.actions > input").click()
       
        error_alert = page.locator(".flash.alert")
        if error_alert.count() > 0 and error_alert.is_visible():
            # Return tuple: (Success_Boolean, Message_String)
            return False, f"login failed! {error_alert.inner_text()}"
             
        error_flash = page.locator(".flash.error")
        if error_flash.count() > 0 and error_flash.is_visible():
            return False, f"login failed! {error_flash.inner_text()}"

        page.wait_for_selector("#dashboard") 
        return True, f"login successful!"

    try:
        success, message = worker.execute(_login)
    except Exception as e:
        report(f"Error: {e}", status_widget, is_error=True)
        return False

    if success:
        report(message, status_widget)
        return True
    else:
        report(message, status_widget, is_error=True)
        return False     


def gettingHistory(worker, username, oldDf):
    link_base = f"https://archiveofourown.org/users/{username}/readings?page="
    progress_q = queue.Queue()
    
    with st.container(border=True):
        st.markdown('<div class="archive-sub" style="margin-bottom: 10px;">Compiling Ledger...</div>', unsafe_allow_html=True)
        progress_bar = st.progress(0)
        
        st.write("")
        
        spacer_left, col1, col2, spacer_right = st.columns([1.7, 1, 1, 1.7])
        with col1:
            page_metric = st.empty()
            page_metric.metric("Page Progress", "1 / ?")
        with col2:
            works_metric = st.empty()
            works_metric.metric("Works Found", "0")
            
        st.divider()
        reading_status = st.empty()
        title_status = st.empty()

    def _scrape_job(page):
        return scrape_works(
            page, link_base,
            pagination_selector=".pagination.actions.pagy",
            work_list_selector="#main > ol.reading.work.index.group", 
            is_processing_history=True,
            history_df=oldDf,
            progress_q=progress_q 
        )

    holder = {}
    done = threading.Event()
    worker._queue.put((_scrape_job, holder, done))

    while not done.wait(timeout=0.1):
        while not progress_q.empty():
            msg = progress_q.get()
            
            if "total_pages" in msg and "current_page" in msg:
                pct = min(1.0, msg["current_page"] / msg["total_pages"])
                progress_bar.progress(pct)
                page_metric.metric("Page Progress", f"{msg['current_page']} / {msg['total_pages']}")
                
            if "valid_works" in msg:
                works_metric.metric("Works Found", str(msg['valid_works']))
                
            if "title" in msg:
                display_title = msg['title'][:55] + "..." if len(msg['title']) > 55 else msg['title']
                
                title_html = f"""
                <div style='text-align: center; line-height: 1.4;'>
                    <span style='color: gray; font-size: 0.9em;'>Currently Reading</span><br>
                    <span style='font-size: 1.1em;'><i>{display_title}</i></span>
                    <p></p>
                </div>
                """
                title_status.markdown(title_html, unsafe_allow_html=True)


    if holder.get("error"):
        st.error(f"Error during scraping: {holder['error']}")
        return oldDf

    dataFrame = pd.concat([oldDf, holder["result"]], ignore_index=True)
    dataFrame.dropna(subset=['fic_id'], inplace=True)
    
    st.balloons()
    progress_bar.progress(1.0)
    title_status.markdown("<p style='text-align: center; color: #8c2d19;'><b>Done!</b></p>", unsafe_allow_html=True)
    
    return dataFrame

def gettingBookmarks(worker, username, dataFrame):
    progress_q = queue.Queue()
    
    with st.container(border=True):
        st.markdown('<div class="archive-sub" style="margin-bottom: 10px;">Cross-referencing Bookmarks...</div>', unsafe_allow_html=True)
        progress_bar = st.progress(0)
        
        st.write("")
        spacer_left, col1, col2, spacer_right = st.columns([1.7, 1, 1, 1.7])
        with col1:
            page_metric = st.empty()
            page_metric.metric("Page Progress", "1 / ?")
        with col2:
            bookmarks_metric = st.empty()
            bookmarks_metric.metric("Checked", "0")
            
        st.divider()
        title_status = st.empty()

    def _bookmark_job(page):
        return checkBookmarks(username, dataFrame, page, progress_q=progress_q)

    holder = {}
    done = threading.Event()
    worker._queue.put((_bookmark_job, holder, done))

    bookmarks_tagged = 0

    while not done.wait(timeout=0.1):
        while not progress_q.empty():
            msg = progress_q.get()
            
            if "total_pages" in msg and "current_page" in msg:
                tot = msg["total_pages"] if isinstance(msg["total_pages"], int) else 1
                cur = msg["current_page"]
                pct = min(1.0, cur / tot)
                progress_bar.progress(pct)
                page_metric.metric("Page Progress", f"{cur} / {tot}")
                
            if "title" in msg:
                bookmarks_tagged += 1
                bookmarks_metric.metric("Checked", str(bookmarks_tagged))
                display_title = msg['title'][:55] + "..." if len(msg['title']) > 55 else msg['title']
                
                title_html = f"""
                <div style='text-align: center; line-height: 1.4;'>
                    <span style='color: gray; font-size: 0.9em;'>Validating Match</span><br>
                    <span style='font-size: 1.1em;'><i>{display_title}</i></span>
                    <p></p>
                </div>
                """
                title_status.markdown(title_html, unsafe_allow_html=True)

    if holder.get("error"):
        st.error(f"Error during bookmark scraping: {holder['error']}")
        return dataFrame

    progress_bar.progress(1.0)
    title_status.markdown("<p style='text-align: center; color: #8c2d19;'><b>Bookmarks Synchronized!</b></p>", unsafe_allow_html=True)
    
    return holder["result"]

def scrape_works(page, base_url_full_query, pagination_selector, work_list_selector, is_processing_history, history_df, max_number_works=None, progress_q=None):
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
        if progress_q:
            progress_q.put({"current_page": p, "total_pages": last_page, "valid_works": stored_num_works})
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

                if progress_q:
                    progress_q.put({"title": processed_work[1]})

                if (history_df['fic_id'] == processed_work[0]).any():
                    if is_processing_history:
                        print (f"-- stopping early! at work {i+1} on page {p}")
                        keepGoing = False
                        break # stop early if there's already saved history
                    else:
                        continue # logic for unread fics: ignore already saved works
                
                rows_on_page.append(processed_work)
                stored_num_works += 1
                if progress_q:
                     progress_q.put({"valid_works": stored_num_works})
            except Exception as e:
                print(f"Error processing work {i+1} on page {p}: {e}. Waiting and skipping...")
                time.sleep(15) 
                continue

        if keepGoing == False:
            break
        all_processed_rows.append(pd.DataFrame(rows_on_page, columns=WORK_DF_COL))
        
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

    title = ""
    author = []

    header = work.locator("div.header.module, div.anonymous.header.module")
    heading = header.locator("h4.heading")

    if heading.locator("a").count() > 0:
        title = heading.locator("a").first.inner_text().strip()

    author_links = heading.locator("a[rel='author']")
    if author_links.count() > 0:
        author = [a.inner_text().strip() for a in author_links.all()]
    else:
        heading_text = heading.inner_text()
        if "by Anonymous" in heading_text:
            author = ["Anonymous"]
        else:
            author = ["Unknown"]

    all_ships = work.locator("li.relationships").all()
    ships = [ship.locator("a.tag").inner_text().strip() for ship in all_ships]

    rating = work.locator("ul.required-tags li").nth(0).inner_text().strip()

    all_orientations = work.locator("ul.required-tags li").nth(2).inner_text().strip()
    orientations = [o.strip() for o in all_orientations.split(',') if o.strip()]

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
    return [id, title, author, rating, orientations, fandoms, ships, tags, words, parsed_date, bookmark]

def scrap_unread_fics(page, history_df, tag_ship_counts, ship_tag, progress_q=None):
    max_number_fics = 200
    if progress_q: progress_q.put({"status": f"Will now fetch {max_number_fics} unread fanfics for scoring."})
    
    base_search_url = 'https://archiveofourown.org/works/search?'
    number_tags = 5

    formatted_tags, formatted_ship_tag = format_unread_fic_tags(number_tags, tag_ship_counts, ship_tag)

    unread_df = pd.DataFrame(columns=WORK_DF_COL)

    while len(unread_df) < max_number_fics and number_tags >= 0:
        current_url_query = f"work_search%5Brelationship_names%5D={formatted_ship_tag}&work_search%5Bfreeform_names%5D="
        
        for t in range(number_tags):
            current_url_query = f"{current_url_query}%2C{formatted_tags[t]}"

        current_url_query += "&work_search%5Bsort_column%5D=kudos_count&commit=Search&page="
        full_base_url = base_search_url + current_url_query

        if progress_q: progress_q.put({"status": f"Searching with {number_tags} tags..."})

        number_works_to_read = max_number_fics - len(unread_df)

        newly_scraped_fics = scrape_works(
            page,
            full_base_url,
            pagination_selector="ol.pagination.actions",
            work_list_selector="#main > ol.work.index.group",
            is_processing_history=False, 
            history_df=pd.concat([history_df, unread_df]),
            max_number_works=100 if number_works_to_read > 100 else number_works_to_read,
            progress_q=progress_q # We pass the queue deeper!
        )
        newly_scraped_fics.drop_duplicates(subset=['fic_id'], inplace=True)
        existing_fic_ids = unread_df['fic_id'].unique()
        newly_scraped_fics = newly_scraped_fics[~newly_scraped_fics['fic_id'].isin(existing_fic_ids)]

        unread_df = pd.concat([unread_df, newly_scraped_fics], ignore_index=True)
        
        if progress_q: progress_q.put({"valid_works": len(unread_df)})
        number_tags -= 1 

    if progress_q: progress_q.put({"status": f"Finished getting unread fics, with {len(unread_df)} fics"})
    return unread_df

            
def checkBookmarks(username, dataframe: pd.DataFrame, page, progress_q=None):
    print ("checking bookmarks")
    if progress_q: progress_q.put({"status": "Checking bookmarks..."})
    base_url = f"https://archiveofourown.org/users/{username}/bookmarks?page="
    pageNumber = 1
    total_pages = "?"
    
    while True:
        url = base_url + str(pageNumber)
        page.goto(url)
        
        numberUsersHeader = page.locator("#main > h2").text_content()
        if numberUsersHeader:
            if len(numberUsersHeader.split("-")) == 1: 
                total_pages = 1 
            else:
                numberKudos = numberUsersHeader.split("-")[1].split(" ")
                total_items = int(numberKudos[3].replace(",", ""))
                total_pages = math.ceil(total_items / 20) # 20 bookmarks per page
        else:
            if progress_q: progress_q.put({"error": "Error reading bookmarks page"})
            break

        if progress_q: 
            progress_q.put({"current_page": pageNumber, "total_pages": total_pages})
            
        work_list = page.locator("li[role='article']")
        count = work_list.count()
        
        for i in range (count):
            work = work_list.nth (i)
            try:
                if "deleted" in work.get_attribute("class"): 
                    continue

                work_link_locator = work.locator("h4.heading a[href^='/works/']")
                work_link_locator.wait_for(state="attached", timeout=15000)
                
                title = work_link_locator.text_content()
                if progress_q: progress_q.put({"title": title})

                id = int (work_link_locator.get_attribute("href", timeout=5000)[7:])
                dataframe.loc[dataframe["fic_id"] == id, "bookmarked"] = True
            except Exception as e:
                if progress_q: progress_q.put({"error": f"Error processing work {i+1} on page {pageNumber}. Skipping..."})
                time.sleep(30) 
                continue

        # Check if we reached the end
        if numberUsersHeader and len(numberUsersHeader.split("-")) > 1:
            if int(numberKudos[1].replace(",", "")) >= int(numberKudos[3].replace(",", "")): 
                break

        pageNumber += 1
        
    if progress_q: progress_q.put({"status": "Finished checking bookmarks"})
    return dataframe


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
