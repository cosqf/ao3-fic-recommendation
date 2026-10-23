import re
import time
import queue
import traceback

import pandas as pd

from backend.web_utils import *
from backend.recommendation import *

from bs4 import BeautifulSoup
from config import WORK_DF_COL
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

# ----------------------------------------------------------------------------------
# everything the backend streams to the frontend
#
#   HEARTBEAT              -                        sent every few seconds while a job runs, so a
#                                                   client that left is noticed promptly (ignore it)
#   STATUS                 message                  free text
#   WARNING                message                  something went wrong but the run continues
#                                                   (page retry, empty page...)
#   LOGIN_SUCCESS / LOGIN_FAILED   message
#   <STAGE>_PROGRESS       data = progress dict     STAGE: HISTORY, MARKED_LATER, BOOKMARK, UNREAD
#   <STAGE>_DONE           data = None              stage finished (never carries records)
#   DONE                   data = records           the ONLY success event carrying data,
#                                                   used by /scrape AND /fetch_works
#   ERROR                  data = records | None    the best-known result at the moment of failure,
#                                                   in the same shape DONE would have used
# ----------------------------------------------------------------------------------

HEARTBEAT_SECONDS = 5


def make_event(event_type, message="", data=None):
    return {"type": event_type, "message": message, "data": data}


def _records(df):
    return None if df is None else df.to_dict(orient="records")


def _done_message(base, stats):
    skipped = stats["skipped"]
    if not skipped:
        return base
    return f"{base} {skipped} work{'s' if skipped != 1 else ''} skipped because they could not be parsed (details in the server console)."


#run job(page, progress_q) on the browser worker and relay its progress.
def run_stage(worker, job, stage, stats):
    progress_q = queue.Queue()
    cancel = getattr(worker, "cancel_event", None)
    try:
        holder, done = worker.submit(lambda page: job(page, progress_q, cancel))
    except RuntimeError as e:
        raise ScrapeError(str(e))

    def drain():
        while True:
            try:
                item = progress_q.get_nowait()
            except queue.Empty:
                return
            warning = item.pop("warning", None)
            stats["skipped"] += item.pop("skipped", 0)
            if warning:
                yield make_event("WARNING", message=warning)
            if item:
                yield make_event(f"{stage}_PROGRESS", data=item)

    last_beat = time.monotonic()
    while not done.wait(timeout=0.1):
        yield from drain()
        if not worker.is_alive():
            raise ScrapeError(f"browser worker stopped unexpectedly (startup error: {worker.startup_error})")
        if time.monotonic() - last_beat >= HEARTBEAT_SECONDS:
            last_beat = time.monotonic()
            yield make_event("HEARTBEAT")
    yield from drain()

    error = holder.get("error")
    if error is not None:
        if isinstance(error, ScrapeError):
            raise error
        raise ScrapeError(f"unexpected error: {error}") from error
    return holder["result"]



def logIn(worker, user, pwd, stats):
    print("logging in")
    yield make_event("STATUS", message="Logging in...")
    try:
        success, message = yield from run_stage(
            worker, lambda page, q, cancel: _login_job(page, user, pwd, q, cancel), "LOGIN", stats
        )
    except ScrapeCancelled:
        return False
    except ScrapeError as e:
        print(f"logIn failed: {e.message}")
        yield make_event("LOGIN_FAILED", message=e.message)
        return False

    if not success:
        print("Not logged in")
        yield make_event("LOGIN_FAILED", message=message)
        return False

    print("Logged in")
    yield make_event("LOGIN_SUCCESS", message=message)
    return True


def _login_job(page, user, pwd, progress_q, cancel=None):
    login_url = "https://archiveofourown.org/users/login"
    load_page(page, login_url, progress_q=progress_q, ready_selector="#user_login", cancel=cancel)
    check_cancelled(cancel)

    page.fill("#user_login", user)
    page.fill("#user_password", pwd)
    page.locator("#new_user > dl > dd.submit.actions > input").click()

    result_selector = ".flash.alert, .flash.error, #dashboard"
    try:
        page.wait_for_selector(result_selector, timeout=30000)
    except PlaywrightTimeoutError:
        print(f"Login timeout! URL: {page.url}")
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


def run_scrape_pipeline(worker, username, password, initial_df, ship=None):
    stats = {"skipped": 0}

    logged_in = yield from logIn(worker, username, password, stats)
    if not logged_in:
        return

    ledger = pd.DataFrame(columns=WORK_DF_COL) if initial_df is None else initial_df

    stages = [("history", gettingHistory)]
    if ship is None:  # fetching the full ledger
        stages += [("marked for later", removingMarkedLater), ("bookmarks", gettingBookmarks)]

    for name, stage in stages:
        try:
            ledger = yield from stage(worker, username, ledger, stats)
        except ScrapeCancelled:
            return
        except ScrapeError as e:
            best = e.partial if e.partial is not None else ledger
            yield make_event("ERROR", message=f"{name}: {e.message}", data=_records(best))
            return
        except Exception as e:
            yield make_event("ERROR", message=f"{name}: unexpected error: {e}", data=_records(ledger))
            return

    yield make_event("DONE", message=_done_message("ledger compilation complete!", stats), data=_records(ledger))


def _merge_history(old_df, new_df):
    if new_df is None or new_df.empty:
        return old_df.copy()
    return pd.concat([old_df, new_df], ignore_index=True).dropna(subset=["fic_id"])


def gettingHistory(worker, username, ledger, stats):
    print("getting history")
    link_base = f"https://archiveofourown.org/users/{username}/readings?page="

    def _job(page, progress_q, cancel):
        try:
            new_rows = scrape_works(
                page, link_base,
                pagination_selector=".pagination.actions.pagy",
                work_list_selector="#main > ol.reading.work.index.group",
                is_processing_history=True,
                history_df=ledger,
                progress_q=progress_q,
                cancel=cancel,
            )
        except ScrapeError as e:
            raise type(e)(e.message, partial=_merge_history(ledger, e.partial)) from e
        return _merge_history(ledger, new_rows)

    result = yield from run_stage(worker, _job, "HISTORY", stats)
    yield make_event("HISTORY_DONE", message="history scraping complete.")
    return result


def removingMarkedLater(worker, username, ledger, stats):
    print("reading marked later")
    link_base = f"https://archiveofourown.org/users/{username}/readings?show=to-read&page="

    def _without_marked(marked_df):
        if marked_df is None or marked_df.empty:
            return ledger.copy()
        kept = ledger[~ledger["fic_id"].isin(marked_df["fic_id"])]
        return kept.dropna(subset=["fic_id"]).reset_index(drop=True)

    def _job(page, progress_q, cancel):
        try:
            marked = scrape_works(
                page, link_base,
                pagination_selector=".pagination.actions.pagy",
                work_list_selector="#main > ol.reading.work.index.group",
                is_processing_history=True,
                history_df=pd.DataFrame(columns=WORK_DF_COL),
                progress_q=progress_q,
                cancel=cancel,
            )
        except ScrapeError as e:
            # partial = the ledger minus the marked works found before the failure
            raise type(e)(e.message, partial=_without_marked(e.partial)) from e
        return _without_marked(marked)

    result = yield from run_stage(worker, _job, "MARKED_LATER", stats)
    yield make_event("MARKED_LATER_DONE", message="removing marked for later complete.")
    return result


def gettingBookmarks(worker, username, ledger, stats):
    def _job(page, progress_q, cancel):
        return checkBookmarks(username, ledger, page, progress_q=progress_q, cancel=cancel)

    result = yield from run_stage(worker, _job, "BOOKMARK", stats)
    yield make_event("BOOKMARK_DONE", message="bookmark scraping complete.")
    return result


def fetchingUnreadWorks(worker, username, password, ship, history_records, inc_tags, exc_tags):
    stats = {"skipped": 0}
    
    if username and password:
        logged_in = yield from logIn(worker, username, password, stats)
        if not logged_in:
            return
 
    history_df = pd.DataFrame(history_records) if history_records else pd.DataFrame(columns=WORK_DF_COL)
 
    yield make_event("STATUS", message="Building your reading profile...")
    try:
        tag_ship_counts = select_search_tags(history_df, ship, exc_tags)
        user_profile_vector, fitted_model_components = create_user_profile_from_history(history_df)
    except ProfileError as e:
        yield make_event("ERROR", message=str(e))
        return
    except Exception as e:
        yield make_event("ERROR", message=f"unexpected error building profile: {e}")
        return
 
    def _job(page, progress_q, cancel):
        return scrap_unread_fics(page, history_df, tag_ship_counts, inc_tags, exc_tags, ship, progress_q=progress_q, cancel=cancel)
 
    def _score(df):
        return score_unread_fanfics(df, user_profile_vector, fitted_model_components)
 
    scrape_error = None
    df_unread = None
    try:
        df_unread = yield from run_stage(worker, _job, "UNREAD", stats)
        yield make_event("UNREAD_DONE", message="unread fic scrape complete.")
    except ScrapeCancelled:
        return
    except ScrapeError as e:
        scrape_error = e
        df_unread = e.partial
 
    if scrape_error is not None:
        # ERROR carries the same shape DONE would: scored records (None if nothing was collected)
        scored_records = None
        message = f"error while fetching unread works: {scrape_error.message}"
        if df_unread is not None and not df_unread.empty:
            yield make_event("STATUS", message="Scoring what was collected before the error...")
            try:
                scored_records = _records(_score(df_unread))
            except Exception as e:
                print(f"could not score partial unread fics: {e}")
                message += " (the fics collected before the error could not be scored)"
        yield make_event("ERROR", message=message, data=scored_records)
        return
 
    if df_unread is None or df_unread.empty:
        yield make_event("DONE", message="unread fic scan complete, but no new fics were found.", data=[])
        return
 
    yield make_event("STATUS", message="Scoring fics...")
    try:
        df_scored = _score(df_unread)
    except Exception as e:
        yield make_event("ERROR", message=f"unexpected error scoring fics: {e}")
        return
 
    yield make_event("DONE", message=_done_message("unread fic scan complete.", stats), data=_records(df_scored))
 

def _rows_to_df(rows):
    return pd.DataFrame(rows, columns=WORK_DF_COL)


def _work_ref(work):
    try:
        return work.get_attribute("id", timeout=2000) or "no id"
    except Exception:
        return "id unavailable"


def scrape_works(page, base_url_full_query, pagination_selector, work_list_selector, is_processing_history, history_df, get_summary=False, max_number_works=None, progress_q=None, progress_offset=0, cancel=None):
    rows = []
    known_ids = set(history_df['fic_id'].dropna().tolist())
    current_page = 1

    try:
        print(f"Navigating to the first page: {base_url_full_query}1")
        load_page(page, base_url_full_query + "1", progress_q=progress_q, ready_selector="h2.heading", cancel=cancel)

        last_page = get_number_of_pages_from_pagination(page, pagination_selector)
        print("total pages to read: ", last_page)

        for current_page in range(1, last_page + 1):
            check_cancelled(cancel)
            notify(progress_q, {"current_page": current_page, "total_pages": last_page, "valid_works": progress_offset + len(rows)})
            if current_page > 1:  # page 1 is already loaded
                load_page(page, base_url_full_query + str(current_page), progress_q=progress_q, ready_selector="h2.heading", cancel=cancel)

            work_list = page.locator("li[role='article']")
            work_count_on_page = work_list.count()
            if page.locator(work_list_selector).count() < 1 or work_count_on_page == 0:
                print(f"No works found on page {current_page}, skipping...")
                if current_page > 1:  # page 1 being empty just means no results
                    notify(progress_q, {"warning": f"Page {current_page} of {last_page} had no works and was skipped."})
                continue

            print(f"processing {work_count_on_page} works on page {current_page}")
            new_on_page = 0
            found_repeat_on_page = False

            for i in range(work_count_on_page):
                check_cancelled(cancel)  # outside the try: a cancel must not count as a parse failure
                work = work_list.nth(i)
                try:
                    processed_work = processWork(work, is_processing_history, get_summary)
                    if not processed_work:  # deleted / mystery / undated work
                        continue

                    notify(progress_q, {"title": processed_work[1]})

                    if processed_work[0] in known_ids:  # already saved
                        if is_processing_history:
                            found_repeat_on_page = True
                        continue

                    rows.append(processed_work)
                    new_on_page += 1
                    notify(progress_q, {"valid_works": progress_offset + len(rows)})
                except Exception:
                    notify(progress_q, {"skipped": 1})
                    print(f"[skipped work] page {current_page}, item {i + 1}/{work_count_on_page} ({_work_ref(work)}):\n{traceback.format_exc()}")

            if is_processing_history and found_repeat_on_page:
                if new_on_page == 0:
                    print(f"-- stopping early! entire page {current_page} was already in history")
                    break
                print(f"-- found {new_on_page} new works on page {current_page} alongside duplicates, continuing...")

            if max_number_works is not None and len(rows) >= max_number_works:
                break

    except ScrapeError as e:
        raise type(e)(e.message, partial=_rows_to_df(rows)) from e
    except Exception as e:
        raise ScrapeError(f"unexpected error on page {current_page}: {e}", partial=_rows_to_df(rows)) from e

    return _rows_to_df(rows)


def _combine_unread(existing, new):
    if new is None or new.empty:
        return existing
    new = new.drop_duplicates(subset=['fic_id'])
    new = new[~new['fic_id'].isin(existing['fic_id'])]
    if existing.empty:
        return new.reset_index(drop=True)
    return pd.concat([existing, new], ignore_index=True)


def _include_tags(tag_ship_counts, inc_tags, max_tags):
    if inc_tags and len(inc_tags) > 0:
        remaining_df = tag_ship_counts[~tag_ship_counts['tag'].isin(inc_tags)]
        
        inc_df = pd.DataFrame({'tag': inc_tags})
        inc_df = inc_df.merge(tag_ship_counts, on='tag', how='left')
        
        tag_ship_counts = pd.concat([inc_df, remaining_df], ignore_index=True)

        tag_ship_counts = tag_ship_counts.head(max_tags) 

    return tag_ship_counts

def scrap_unread_fics(page, history_df, tag_ship_c, inc_tags, exc_tags, ship_tag, progress_q=None, cancel=None):
    max_number_fics = 200
    max_tags = 5
    notify(progress_q, {"max_fics": max_number_fics})
    notify(progress_q, {"status": f"Will now fetch {max_number_fics} unread fanfics for scoring."})
    base_search_url = 'https://archiveofourown.org/works/search?'

    tag_ship_counts = _include_tags(tag_ship_c, inc_tags, max_tags)

    raw_tags = tag_ship_counts['tag'].head(max_tags).tolist()
    formatted_tags, formatted_ship_tag = format_unread_fic_tags(max_tags, tag_ship_counts, ship_tag)
    formatted_exc_tags = [quote_plus(t) for t in exc_tags]

    number_tags = len(formatted_tags)
    passes = 0

    unread_df = pd.DataFrame(columns=WORK_DF_COL)

# only includes, works as intended
#https://archiveofourown.org/works/search?work_search[relationship_names]=Jinu%2FRumi+(KPop+Demon+Hunters)&work_search[freeform_names]=%2CAngst%2CPost-Canon%2CHurt%2FComfort%2CRumi+Needs+a+Hug+(KPop+Demon+Hunters)%2CJinu+Lives+(KPop+Demon+Hunters)&work_search[sort_column]=kudos_count&commit=Search&page=1

# normal search with filter, one include and one exclude
#https://archiveofourown.org/works?work_search%5Bsort_column%5D=revised_at&include_work_search%5Bfreeform_ids%5D%5B%5D=176&work_search%5Bother_tag_names%5D=&exclude_work_search%5Bfreeform_ids%5D%5B%5D=110&work_search%5Bexcluded_tag_names%5D=&work_search%5Bcrossover%5D=&work_search%5Bcomplete%5D=&work_search%5Bwords_from%5D=&work_search%5Bwords_to%5D=&work_search%5Bdate_from%5D=&work_search%5Bdate_to%5D=&work_search%5Bquery%5D=&work_search%5Blanguage_id%5D=&commit=Sort+and+Filter&tag_id=KPop+Demon+Hunters+%282025%29

    try:
        while len(unread_df) < max_number_fics and number_tags >= 0:
            check_cancelled(cancel)
            current_url_query: str = f"work_search%5Brelationship_names%5D={formatted_ship_tag}&work_search%5Bfreeform_names%5D="
            for t in range(number_tags):
                current_url_query = f"{current_url_query}%2C{formatted_tags[t]}"

            if len(formatted_exc_tags) > 0:
                current_url_query += "&work_search%5Bquery%5D="
                for i in range(len(formatted_exc_tags)):
                    if i > 0:
                        current_url_query += "+"
                    current_url_query += f"-%22{formatted_exc_tags[i]}%22"

            current_url_query += "&work_search%5Bsort_column%5D=kudos_count&commit=Search&page="
            full_base_url = base_search_url + current_url_query

            passes += 1
            notify(progress_q, {
                "status": f"Searching with {number_tags} tags...",
                "current_tags": raw_tags[:number_tags]
            })

            number_works_to_read = max_number_fics - len(unread_df)

            try:
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
                    progress_offset=len(unread_df),
                    cancel=cancel,
                )
            except ScrapeError as e:
                raise type(e)(e.message, partial=_combine_unread(unread_df, e.partial)) from e

            unread_df = _combine_unread(unread_df, newly_scraped_fics)
            notify(progress_q, {
                "valid_works": len(unread_df),
                "status": f"Found {len(unread_df)} fics so far (tried {passes} tag sets)..."
            })
            number_tags -= 1
    except ScrapeError:
        raise
    except Exception as e:
        raise ScrapeError(f"unexpected error while searching for unread fics: {e}", partial=unread_df) from e

    notify(progress_q, {"status": f"Finished getting unread fics, with {len(unread_df)} fics"})
    return unread_df


def checkBookmarks(username, dataframe: pd.DataFrame, page, progress_q=None, cancel=None):
    print("checking bookmarks")
    ledger = dataframe.copy()
    found_ids = set()
    unreadable = 0
    notify(progress_q, {"status": "Checking bookmarks..."})
    base_url = f"https://archiveofourown.org/users/{username}/bookmarks?page="
    current_page = 1
 
    def _set_flags(reset):
        found = ledger["fic_id"].isin(found_ids)
        if reset:
            ledger["bookmarked"] = found
        else:
            ledger["bookmarked"] = ledger["bookmarked"].eq(True) | found
 
    try:
        load_page(page, base_url + "1", progress_q=progress_q, ready_selector="#main > h2", cancel=cancel)
        last_page = get_number_of_pages_from_pagination(page, "ol.pagination.actions")
        print("total bookmark pages to read: ", last_page)
 
        for current_page in range(1, last_page + 1):
            check_cancelled(cancel)
            if current_page > 1:  # page 1 is already loaded
                load_page(page, base_url + str(current_page), progress_q=progress_q, ready_selector="#main > h2", cancel=cancel)
            notify(progress_q, {"current_page": current_page, "total_pages": last_page})
 
            work_list = page.locator("li[role='article']")
            count = work_list.count()
 
            for i in range(count):
                check_cancelled(cancel)
                work = work_list.nth(i)
                try:
                    if "deleted" in (work.get_attribute("class") or ""):
                        continue
 
                    # series and external-work bookmarks have no /works/ link: not an error, just not a fic
                    work_links = work.locator("h4.heading a[href^='/works/']")
                    if work_links.count() == 0:
                        continue
                    work_link = work_links.first
 
                    match = re.match(r"/works/(\d+)", work_link.get_attribute("href", timeout=5000) or "")
                    if match is None:
                        continue
 
                    notify(progress_q, {"title": work_link.text_content()})
                    found_ids.add(int(match.group(1)))
                except Exception:
                    unreadable += 1
                    notify(progress_q, {"skipped": 1})
                    print(f"[skipped bookmark] page {current_page}, item {i + 1}/{count} ({_work_ref(work)}):\n{traceback.format_exc()}")
 
    except ScrapeError as e:
        _set_flags(reset=False)
        raise type(e)(e.message, partial=ledger) from e
    except Exception as e:
        _set_flags(reset=False)
        raise ScrapeError(f"unexpected error on bookmarks page {current_page}: {e}", partial=ledger) from e
 
    if unreadable:
        _set_flags(reset=False)
        notify(progress_q, {"warning": f"{unreadable} bookmark entries could not be read, so un-bookmarked fics were not cleared this time."})
    else:
        _set_flags(reset=True)
 
    notify(progress_q, {"status": "Finished checking bookmarks"})
    return ledger
 
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

# ----------------------------------------------------------------------------------
# NOTE: everything below is currently UNUSED and has not been migrated to load_page()/ScrapeError
# ----------------------------------------------------------------------------------

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
