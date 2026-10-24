from playwright.sync_api import Playwright
import re
import time
from urllib.parse import quote_plus
import pandas as pd
import random

PAGE_RETRIES = 2          # extra attempts after the first failed page load
PAGE_RETRY_WAIT = 30      # seconds between attempts
PAGE_DELAY = (0.5, 2)    # random pause before each page load
MAX_RETRY_AFTER = 120      # cap on how long we obey AO3's Retry-After header
CHALLENGE_WAIT = 25        # seconds to let a Cloudflare/"Shields are up" page resolve itself
TRANSIENT_RETRY_WAITS = (10, 20)   # waits between attempts when AO3/Cloudflare answers with a 5xx

class ScrapeError(Exception):
    def __init__(self, message, partial=None):
        super().__init__(message)
        self.message = message # reason shown to the user
        self.partial = partial # what the stage had when it failed

class AO3Unavailable(ScrapeError):
    """AO3 (or Cloudflare in front of it) kept answering with a 5xx. Not the user's fault."""

def settingUpBrowser (pw: Playwright):
        agent = "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
        browser = pw.chromium.launch(headless=True).new_context(user_agent=agent)
        return browser

def report(text, status_widget=None, is_error=False):
    print(text)
    if status_widget:
        if is_error:
            status_widget.error(text)
        else:
            status_widget.markdown(f'<p class="archive-sub">{text}</p>', unsafe_allow_html=True)

def get_number_of_pages_from_pagination (page, pagination_selector):
    pagination_locator = page.locator(pagination_selector)
    pagination_exists = pagination_locator.count() > 0

    last_page = 1 # default

    if pagination_exists:
        pagination_items = pagination_locator.locator("li")
        count = pagination_items.count()
        if count < 3:
            print("pagination items are less than 3, assuming 1 page")
        else:
            try:
                last_page = int(pagination_items.nth(count - 2).inner_text().strip())
            except ValueError:
                print("could not parse last page number, assuming 1 page")
    else:
        print("no pagination found, assuming 1 page.")

    return last_page


def extract_and_parse_last_visited(full_text):
    date_pattern = re.compile(r'(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})') 
    # regex pattern for 2 digits (day), 3 letters (month) and 4 digits (year)

    match = date_pattern.search(full_text)
    if match:
        day = match.group(1)
        month = match.group(2)
        year = match.group(3)
        
        last_visited_str = f"{day} {month} {year}"
        try:
            parsed_date = pd.to_datetime(last_visited_str, format="%d %b %Y")
            return parsed_date.isoformat()
        except ValueError:
            print(f"Warning: Could not parse date '{last_visited_str}' from text: {full_text}")
            return None 
    else:
        print(f"Warning: No date found in text: {full_text}")
        return None

def format_unread_fic_tags (number_tags, tag_ship_counts, ship_tag):
    tags = tag_ship_counts['tag'].head(number_tags).tolist()
    formatted_tags = [quote_plus(t) for t in tags]
    
    # TODO (later): check regex

    formatted_ship_tag = re.sub(r"\[^]*\)", "", ship_tag).strip()
    formatted_ship_tag = quote_plus(formatted_ship_tag)
    return formatted_tags, formatted_ship_tag

def is_rate_limited(page):
    try:
        if "retry later" in page.title().lower():
            return True
        text = " ".join(page.locator("body").inner_text(timeout=2000).split()).lower()
    except Exception:
        return False
    # length guard: a fic whose text happens to contain "retry later" must not match
    return len(text) < 300 and ("retry later" in text or "unusual traffic" in text)

def is_cloudflare_blocked(page):
    return (
        "Shields are up" in page.content() or
        "cf-challenge" in page.content() or
        page.query_selector("input#challenge-stage") is not None
    )

def safe_goto(page, url, timeout=30000):
    try:
        return page.goto(url, wait_until="networkidle", timeout=timeout)
    except Exception:
        response = page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        page.wait_for_load_state("networkidle", timeout=15000)
        return response

def describe_page(page, response=None):
    #snapshot of what the browser is actually looking at, for the server log
    try:
        status = response.status if response is not None else "?"
        body = " ".join(page.locator("body").inner_text(timeout=2000).split())[:200]
        return f"status={status} title={page.title()!r} url={page.url} body={body!r}"
    except Exception as e:
        return f"(could not inspect page: {_short(e)})"


def _retry_after_seconds(response):
    try:
        value = response.headers.get("retry-after") if response is not None else None
        return int(value) if value and value.strip().isdigit() else 0
    except Exception:
        return 0


def wait_out_challenge(page, cancel=None, max_seconds=CHALLENGE_WAIT):
    for _ in range(max_seconds):
        try:
            if "just a moment" not in page.title().lower() and not is_cloudflare_blocked(page):
                return True
        except Exception:
            pass  # page is mid-navigation, check again
        cancellable_sleep(cancel, 1)
    return False

def notify(progress_q, item):
    if progress_q is not None:
        progress_q.put(item)


def _short(e):
    lines = str(e).strip().splitlines()
    return f"{type(e).__name__}: {lines[0]}" if lines else type(e).__name__


class ScrapeCancelled(ScrapeError):
    """The run was cancelled (client went away, or the same session started a new run)."""
    def __init__(self, message="scrape cancelled", partial=None):
        super().__init__(message, partial)
 

def check_cancelled(cancel):
    if cancel is not None and cancel.is_set():
        raise ScrapeCancelled()
 
 
def cancellable_sleep(cancel, seconds):
    if cancel is None:
        time.sleep(seconds)
    elif cancel.wait(seconds):
        raise ScrapeCancelled()


def load_page(page, url, progress_q=None, ready_selector=None,
              retries=PAGE_RETRIES, wait_seconds=PAGE_RETRY_WAIT, cancel=None,
              selector_timeout=15000, pace=True):
    problem = ""
    server_error = None   # HTTP status of the most recent attempt if it was a 5xx, else None
    for attempt in range(retries + 1):
        check_cancelled(cancel)
        if pace and attempt == 0:
            cancellable_sleep(cancel, random.uniform(*PAGE_DELAY))

        response = None
        wait = wait_seconds
        server_error = None
        try:
            response = safe_goto(page, url)
            if response is not None and 500 <= response.status < 600:
                server_error = response.status
                problem = f"AO3 returned HTTP {server_error}"
                wait = TRANSIENT_RETRY_WAITS[min(attempt, len(TRANSIENT_RETRY_WAITS) - 1)]
                print(f"[load_page] {url} -> {describe_page(page, response)}")
            elif is_cloudflare_blocked(page) and not wait_out_challenge(page, cancel):
                raise ScrapeError("blocked by Cloudflare, please try again shortly")
            elif (response is not None and response.status == 429) or is_rate_limited(page):
                problem = "AO3 is rate limiting requests"
                wait = max(wait_seconds, min(_retry_after_seconds(response), MAX_RETRY_AFTER))
                print(f"[load_page] {url} -> {describe_page(page, response)}")
            else:
                if ready_selector:
                    page.wait_for_selector(ready_selector, state="attached", timeout=selector_timeout)
                return
        except ScrapeError:
            raise
        except Exception as e:
            problem = f"page failed to load ({_short(e)})"
            print(f"[load_page] {url} -> {describe_page(page, response)}")

        if attempt < retries:
            msg = f"{problem}. Retrying in {wait}s (attempt {attempt + 2} of {retries + 1})..."
            print(msg)
            notify(progress_q, {"warning": msg})
            cancellable_sleep(cancel, wait)

    if server_error is not None:
        raise AO3Unavailable(
            f"AO3 seems to be having problems right now (HTTP {server_error}). "
            f"This is on AO3's side, not your account. Please try again in a few minutes."
        )
    raise ScrapeError(f"{problem}; gave up after {retries + 1} attempts ({url})")