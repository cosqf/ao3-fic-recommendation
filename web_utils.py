from playwright.sync_api import Playwright
import re
from urllib.parse import quote_plus
import pandas as pd

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
            return parsed_date
        except ValueError:
            print(f"Warning: Could not parse date '{last_visited_str}' from text: {full_text}")
            return None 
    else:
        print(f"Warning: No date found in text: {full_text}")
        return None

def format_unread_fic_tags (number_tags, tag_ship_counts, ship_tag):
    tags = tag_ship_counts['tag'].head(number_tags).tolist()
    formatted_tags = [quote_plus(t) for t in tags]
    
    formatted_ship_tag = re.sub(r"\[^]*\)", "", ship_tag).strip()
    formatted_ship_tag = quote_plus(formatted_ship_tag)
    return formatted_tags, formatted_ship_tag

def is_rate_limited(page):
    return (
        "Retry later" in page.title() or
        page.query_selector("div#main p") is not None and
        "unusual traffic" in (page.query_selector("div#main p").inner_text() or "").lower()
)

def is_cloudflare_blocked(page):
    return (
        "Shields are up" in page.content() or
        "cf-challenge" in page.content() or
        page.query_selector("input#challenge-stage") is not None
    )

def safe_goto(page, url, timeout=30000):
    try:
        page.goto(url, wait_until="networkidle", timeout=timeout)
    except Exception:
        page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        page.wait_for_load_state("networkidle", timeout=15000)
    