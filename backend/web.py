import time
import queue
import threading
import math
import base64

import pandas as pd

from backend.web_utils import *
from backend.recommendation import *

from bs4 import BeautifulSoup
from config import WORK_DF_COL
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

def make_event(event_type, message="", data=None):
    return {"type": event_type, "message": message, "data": data}


def run_scrape_pipeline(worker, username, password, initial_df, ship=None):
    yield make_event("STATUS", message="Logging in...")

    try:
        success, message = logIn(worker, username, password)
    except Exception as e:
        yield make_event("ERROR", message=f"Unexpected error during login: {e}")
        return

    if not success:
        yield make_event("LOGIN_FAILED", message=message)
        return

    yield make_event("LOGIN_SUCCESS", message=message)

    history_df = pd.DataFrame(columns= WORK_DF_COL) if initial_df is None else initial_df
    final_records = None

    if ship is None: # fetching history
        try:
            for event in gettingHistory(worker, username, history_df):
                yield event
                if event["type"] == "HISTORY_DONE":
                    final_records = event["data"]
                elif event["type"] == "ERROR":
                    return
        except Exception as e:
            yield make_event(
                "ERROR",
                message=f"unexpected error while scraping history: {e}",
                data=history_df.to_dict(orient="records"),
            )
        try:
            for event in removingMarkedLater(worker, username, history_df):
                yield event
                if event["type"] == "MARKED_LATER_DONE":
                    final_records = event["data"]
                elif event["type"] == "ERROR":
                    return
        except Exception as e:
            yield make_event(
                "ERROR",
                message=f"unexpected error while reading marked for later: {e}",
                data=history_df.to_dict(orient="records"),
            )

        try:
            for event in gettingBookmarks(worker, username, pd.DataFrame(final_records)):
                yield event
                if event["type"] == "BOOKMARK_DONE":
                    final_records = event["data"]
                elif event["type"] == "ERROR":
                    return
        except Exception as e:
            yield make_event("ERROR", message=f"unexpected error while scraping bookmarks: {e}")
            return
    else:
        try:
            for event in gettingHistory(worker, username, history_df):
                yield event
                if event["type"] == "HISTORY_DONE":
                    final_records = event["data"]
                elif event["type"] == "ERROR":
                    return
        except Exception as e:
            yield make_event(
                "ERROR",
                message=f"unexpected error while scraping history: {e}",
                data=history_df.to_dict(orient="records"),
            )

    yield make_event("DONE", message="ledger compilation complete!", data=final_records)


def logIn(worker, user, pwd):

    def _login(page):
        login_url = "https://archiveofourown.org/users/login"
        safe_goto(page, login_url)

        if is_rate_limited(page):
            time.sleep(30)
            safe_goto(page, login_url)

        if is_cloudflare_blocked(page):
            return False, "blocked by Cloudflare, please try again shortly"
 
        page.fill("#user_login", user)
        page.fill("#user_password", pwd)
        page.locator("#new_user > dl > dd.submit.actions > input").click()
 
        result_selector = ".flash.alert, .flash.error, #dashboard"
        try:
            page.wait_for_selector(result_selector, timeout=30000)
        except PlaywrightTimeoutError:
            screenshot_b64 = base64.b64encode(page.screenshot()).decode("utf-8")
            print(f"Timeout! URL: {page.url}")
            print(f"Screenshot (base64, {len(screenshot_b64)} chars): {screenshot_b64}")
            return False, "Login timed out waiting for a response"
 
        error_alert = page.locator(".flash.alert")
        if error_alert.count() > 0 and error_alert.is_visible():
            return False, f"Login failed! {error_alert.inner_text()}"
 
        error_flash = page.locator(".flash.error")
        if error_flash.count() > 0 and error_flash.is_visible():
            return False, f"Login failed! {error_flash.inner_text()}"
 
        if page.locator("#dashboard").count() > 0:
            return True, "Login successful!"
 
        return False, "Login failed for an unknown reason"

    try:
        success, message = worker.execute(_login)
        print("Logged in") if success else print("Not logged in")
    except Exception as e:
        print(f"logIn failed: {e!r}")
        return False, f"error during login: {e}"

    return success, message


def gettingHistory(worker, username, old_df):
    link_base = f"https://archiveofourown.org/users/{username}/readings?page="
    progress_q = queue.Queue()

    def _scrape_job(page):
        return scrape_works(
            page, link_base,
            pagination_selector=".pagination.actions.pagy",
            work_list_selector="#main > ol.reading.work.index.group",
            is_processing_history=True,
            history_df=old_df,
            progress_q=progress_q,
        )

    holder = {}
    done = threading.Event()
    worker._queue.put((_scrape_job, holder, done))

    while not done.wait(timeout=0.1):
        while not progress_q.empty():
            yield make_event("HISTORY_PROGRESS", data=progress_q.get())

    while not progress_q.empty():
        yield make_event("HISTORY_PROGRESS", data=progress_q.get())

    if holder.get("error"):
        partial_records = None
        partial_result = holder.get("partial_result")
        if partial_result is not None:
            try:
                partial_df = pd.concat([old_df, partial_result], ignore_index=True)
                partial_df.dropna(subset=["fic_id"], inplace=True)
                partial_records = partial_df.to_dict(orient="records")
            except Exception:
                partial_records = None
 
        yield make_event(
            "ERROR",
            message=f"error during scraping: {holder['error']}",
            data=partial_records,
        )
        return

    new_df = pd.concat([old_df, holder["result"]], ignore_index=True)
    new_df.dropna(subset=["fic_id"], inplace=True)

    yield make_event(
        "HISTORY_DONE",
        message="history scraping complete.",
        data=new_df.to_dict(orient="records"),
    )

def gettingBookmarks(worker, username, dataFrame):
    progress_q = queue.Queue()
    
    def _bookmark_job(page):
        return checkBookmarks(username, dataFrame, page, progress_q=progress_q)
 
    holder = {}
    done = threading.Event()
    worker._queue.put((_bookmark_job, holder, done))
 
    while not done.wait(timeout=0.1):
        while not progress_q.empty():
            yield make_event("BOOKMARK_PROGRESS", data=progress_q.get())
 
    while not progress_q.empty():
        yield make_event("BOOKMARK_PROGRESS", data=progress_q.get())
 
    if holder.get("error"):
        partial_records = None
        partial_result = holder.get("partial_result")
        if partial_result is not None:
            try:
                partial_df = pd.concat([dataFrame, partial_result], ignore_index=True)
                partial_df.dropna(subset=["fic_id"], inplace=True)
                partial_records = partial_df.to_dict(orient="records")
            except Exception:
                partial_records = None
 
        yield make_event(
            "ERROR",
            message=f"error during scraping bookmarks: {holder['error']}",
            data=partial_records,
        )
        return
 
    new_df = pd.concat([dataFrame, holder["result"]], ignore_index=True)
    new_df.dropna(subset=["fic_id"], inplace=True)
 
    yield make_event(
        "BOOKMARK_DONE",
        message="bookmark scraping complete.",
        data=new_df.to_dict(orient="records"),
    )

def removingMarkedLater(worker, username, old_df):
    link_base = f"https://archiveofourown.org/users/{username}/readings?show=to-read&page="
    progress_q = queue.Queue()

    def _scrape_job(page):
        return scrape_works(
            page, link_base,
            pagination_selector=".pagination.actions.pagy",
            work_list_selector="#main > ol.reading.work.index.group",
            is_processing_history=True,
            history_df=pd.DataFrame(columns= WORK_DF_COL),
            progress_q=progress_q,
        )

    holder = {}
    done = threading.Event()
    worker._queue.put((_scrape_job, holder, done))

    while not done.wait(timeout=0.1):
        while not progress_q.empty():
            yield make_event("MARKED_LATER_PROGRESS", data=progress_q.get())

    while not progress_q.empty():
        yield make_event("MARKED_LATER_PROGRESS", data=progress_q.get())

    if holder.get("error"):
        partial_records = None
        partial_result = holder.get("partial_result")
        if partial_result is not None:
            try:
                partial_df = old_df[~old_df["fic_id"].isin(partial_result["fic_id"])]
                partial_df.dropna(subset=["fic_id"], inplace=True)
                partial_records = partial_df.to_dict(orient="records")
            except Exception:
                partial_records = None
 
        yield make_event(
            "ERROR",
            message=f"error during scraping: {holder['error']}",
            data=partial_records,
        )
        return

    markedLater = holder["result"]
    new_df = old_df[~old_df["fic_id"].isin(markedLater["fic_id"])]
    new_df.dropna(subset=["fic_id"], inplace=True)

    yield make_event(
        "MARKED_LATER_DONE",
        message="removing marked for later complete.",
        data=new_df.to_dict(orient="records"),)


def fetchingUnreadWorks(worker, username, password, ship, history_records):
    yield make_event("STATUS", message="Logging in...")
 
    try:
        success, message = logIn(worker, username, password)
    except Exception as e:
        yield make_event("ERROR", message=f"unexpected error during login: {e}")
        return
 
    if not success:
        yield make_event("LOGIN_FAILED", message=message)
        return
 
    yield make_event("LOGIN_SUCCESS", message=message)
 
    history_df = pd.DataFrame(history_records) if history_records else pd.DataFrame(columns=WORK_DF_COL)
 
    yield make_event("STATUS", message="Building your reading profile...")
 
    try:
        tag_ship_counts = generate_common_ship_tags(history_df, ship)
        user_profile_vector, fitted_model_components = create_user_profile_from_history(history_df)
    except Exception as e:
        yield make_event("ERROR", message=f"unexpected error building profile: {e}")
        return
 
    progress_q = queue.Queue()
 
    def _scrape_job(page):
        return scrap_unread_fics(page, history_df, tag_ship_counts, ship, progress_q=progress_q)
 
    holder = {}
    done = threading.Event()
    worker._queue.put((_scrape_job, holder, done))
 
    while not done.wait(timeout=0.1):
        while not progress_q.empty():
            yield make_event("UNREAD_PROGRESS", data=progress_q.get())
 
    while not progress_q.empty():
        yield make_event("UNREAD_PROGRESS", data=progress_q.get())
 
    if holder.get("error"):
        partial_records = None
        partial_result = holder.get("partial_result")
        if partial_result is not None:
            try:
                partial_records = partial_result.to_dict(orient="records")
            except Exception:
                partial_records = None
 
        yield make_event(
            "ERROR",
            message=f"error while fetching unread works: {holder['error']}",
            data=partial_records,
        )
        return
 
    df_unread = holder["result"]
 
    yield make_event("STATUS", message="Scoring fics...")
 
    try:
        df_scored = score_unread_fanfics(df_unread, user_profile_vector, fitted_model_components)
    except Exception as e:
        yield make_event("ERROR", message=f"unexpected error scoring fics: {e}")
        return
 
    yield make_event(
        "UNREAD_DONE",
        message="unread fic scan complete.",
        data=df_scored.to_dict(orient="records"),
    )

def scrape_works(page, base_url_full_query, pagination_selector, work_list_selector, is_processing_history, history_df, get_summary=False, max_number_works=None, progress_q=None):
    all_processed_rows = []
    stored_num_works = 0
    print(f"Navigating to the first page: {base_url_full_query}1")
    try:
        safe_goto(page, base_url_full_query + "1")
        page.wait_for_selector("h2.heading")

        last_page = get_number_of_pages_from_pagination(page, pagination_selector)

        keepGoing = True
        print("total pages to read: ", last_page)
        print("starting to read")
        for p in range(1, last_page + 1):
            if progress_q:
                progress_q.put({"current_page": p, "total_pages": last_page, "valid_works": stored_num_works})
            current_page_url = base_url_full_query + str(p)
            safe_goto(page, current_page_url)
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
            found_repeat_on_page = False

            for i in range(work_count_on_page):
                try:
                    work = work_list.nth(i)
                    processed_work = processWork(work, is_processing_history, get_summary)
                    if processed_work == []:
                        continue

                    if progress_q:
                        progress_q.put({"title": processed_work[1]})

                    if (history_df['fic_id'] == processed_work[0]).any(): # if is duplicate
                        if is_processing_history:
                            found_repeat_on_page = True
                            continue
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
            
            if is_processing_history and found_repeat_on_page:
                all_new_on_page = len(rows_on_page)
                if all_new_on_page == 0:
                    print(f"-- stopping early! entire page {p} was already in history")
                    break
                else:
                    print(f"-- found {all_new_on_page} new works on page {p} alongside duplicates, continuing...")
                    
            if max_number_works is not None and stored_num_works >= max_number_works:
                break
    except Exception as e:
        print (f"Error scraping works! {e}")

    if all_processed_rows:
        return pd.concat(all_processed_rows, ignore_index=True)
    else:
        return pd.DataFrame(columns=WORK_DF_COL)


def scrap_unread_fics(page, history_df, tag_ship_counts, ship_tag, progress_q=None):
    max_number_fics = 200
    if progress_q:
        progress_q.put({"max_fics": max_number_fics})
        progress_q.put({"status": f"Will now fetch {max_number_fics} unread fanfics for scoring."})
    base_search_url = 'https://archiveofourown.org/works/search?'
    number_tags = 5
 
    raw_tags = tag_ship_counts['tag'].head(number_tags).tolist()
    formatted_tags, formatted_ship_tag = format_unread_fic_tags(number_tags, tag_ship_counts, ship_tag)
 
    unread_df = pd.DataFrame(columns=WORK_DF_COL)
 
    while len(unread_df) < max_number_fics and number_tags >= 0:
        current_url_query = f"work_search%5Brelationship_names%5D={formatted_ship_tag}&work_search%5Bfreeform_names%5D="
        for t in range(number_tags):
            current_url_query = f"{current_url_query}%2C{formatted_tags[t]}"
 
        current_url_query += "&work_search%5Bsort_column%5D=kudos_count&commit=Search&page="
        full_base_url = base_search_url + current_url_query
 
        if progress_q:
            progress_q.put({
                "status": f"Searching with {number_tags} tags...",
                "current_tags": raw_tags[:number_tags]
            })
 
        number_works_to_read = max_number_fics - len(unread_df)
 
        newly_scraped_fics = scrape_works(
            page,
            full_base_url,
            pagination_selector="ol.pagination.actions",
            work_list_selector="#main > ol.work.index.group",
            is_processing_history=False,
            history_df=pd.concat([history_df, unread_df]),
            get_summary=True,
            max_number_works=100 if number_works_to_read > 100 else number_works_to_read,
            progress_q=progress_q,
        )
        newly_scraped_fics.drop_duplicates(subset=['fic_id'], inplace=True)
        existing_fic_ids = unread_df['fic_id'].unique()
        newly_scraped_fics = newly_scraped_fics[~newly_scraped_fics['fic_id'].isin(existing_fic_ids)]
 
        unread_df = pd.concat([unread_df, newly_scraped_fics], ignore_index=True)
        if progress_q:
            progress_q.put({
                "valid_works": len(unread_df),
                "status": f"Found {len(unread_df)} fics so far (tried {5 - number_tags + 1} tag sets)..."
            })
        number_tags -= 1
 
    if progress_q:
        progress_q.put({"status": f"Finished getting unread fics, with {len(unread_df)} fics"})
    return unread_df

            
def checkBookmarks(username, dataframe: pd.DataFrame, page, progress_q=None):
    print ("checking bookmarks")
    if progress_q: progress_q.put({"status": "Checking bookmarks..."})
    base_url = f"https://archiveofourown.org/users/{username}/bookmarks?page="
    pageNumber = 1
    total_pages = "?"
    
    while True:
        url = base_url + str(pageNumber)
        safe_goto(page, url)

        if is_rate_limited(page):
            if progress_q: progress_q.put({"status": "Rate limited — waiting 30s..."})
            time.sleep(30)
            safe_goto(page, full_url) 

        if is_cloudflare_blocked(page):
            if progress_q: progress_q.put({"status": "Cloudflare blocked — try again later :("})
            return
        
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


def fetch_work_summaries(page, work_ids, progress_q=None):
    base_url = "https://archiveofourown.org/works/"
    results = {}

    for i, work_id in enumerate(work_ids):
        full_url = f"{base_url}{work_id}"
        if progress_q:
            progress_q.put({"fetch_progress": i, "fetch_total": len(work_ids)})

        try:
            safe_goto(page, full_url)

            if is_rate_limited(page):
                if progress_q: progress_q.put({"status": "Rate limited — waiting 30s..."})
                time.sleep(30)
                safe_goto(page, full_url)
            
            if is_cloudflare_blocked(page):
                if progress_q: progress_q.put({"status": "Cloudflare blocked — try again later :("})
                return
                
            # private/restricted work
            if page.url == "https://archiveofourown.org/users/login?restricted=true":
                results[work_id] = None  # use df_scored fallback
                continue

            if check_for_nsfw_warning(page):
                title, author, summary = get_info_nsfw_work(page)
            else:
                title, author, summary = get_info_work(page)

            results[work_id] = {"title": title, "author": author, "summary": summary}

        except Exception as e:
            results[work_id] = {"error": str(e)}

    if progress_q:
        progress_q.put({"fetch_progress": len(work_ids), "fetch_total": len(work_ids)})

    return results

def printWorkInfo(work_id, page, i):
    base_url = "https://archiveofourown.org/works/"
    full_url = f"{base_url}{work_id}"
    print("\n------------------------")
    print(f"Suggestion {i}\n")
    safe_goto(page, full_url)

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

def processWork(work, is_history: bool, get_summary: bool):
    html = work.evaluate("el => el.outerHTML")
    root = BeautifulSoup(html, "html.parser").find("li")
 
    classes = root.get("class") or []
    if "deleted" in classes:
        print("- deleted work found, skipping...")
        return []
 
    if root.select_one("div.mystery.header.picture.module") is not None:
        print("- mystery work found, skipping...")
        return []
 
    id = int(root.get("id")[5:])
 
    title = ""
    author = []
 
    header = root.select_one("div.header.module, div.anonymous.header.module")
    heading = header.select_one("h4.heading")
 
    heading_links = heading.find_all("a")
    if heading_links:
        title = heading_links[0].get_text(strip=True)
 
    author_links = heading.select("a[rel='author']")
    if author_links:
        author = [a.get_text(strip=True) for a in author_links]
    else:
        heading_text = heading.get_text()
        if "by Anonymous" in heading_text:
            author = ["Anonymous"]
        else:
            author = ["Unknown"]
 
    all_ships = root.select("li.relationships")
    ships = [ship.select_one("a.tag").get_text(strip=True) for ship in all_ships]
 
    required_tags = root.select("ul.required-tags li")
    rating = required_tags[0].get_text(strip=True)
 
    orientations_text = required_tags[2].get_text(strip=True)
    orientations = [o.strip() for o in orientations_text.split(',') if o.strip()]
 
    all_tags = root.select("li.freeforms")
    tags = []
    for tag in all_tags:
        tag_link = tag.select_one("a.tag")
        if tag_link is not None:
            tags.append(tag_link.get_text(strip=True))
 
    fandoms = [f.get_text(strip=True) for f in root.select("h5.fandoms.heading a.tag")]
    fandoms.sort()
 
    words_tag = root.select_one("dd.words")
    words = int(words_tag.get_text(strip=True).replace(",", "") if words_tag is not None else "0")
 
    if is_history:
        last_visited = root.select_one("div.user.module.group h4.viewed.heading").get_text(strip=True)
        parsed_date = extract_and_parse_last_visited(last_visited)
        if parsed_date is None:
            return []
    else:
        parsed_date = None
 
    if get_summary:
        summary_blocks = root.select("blockquote.userstuff")
        summary_parts = [block.get_text() for block in summary_blocks]
        summary = "".join(summary_parts).strip()
    else:
        summary = None
 
    bookmark = False
    return [id, title, author, rating, orientations, fandoms, ships, tags, words, parsed_date, bookmark, summary]
