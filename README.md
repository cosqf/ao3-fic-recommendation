# ao3-fic-recommendation
A web scrapper that processes your Archive of Our Own (AO3) reading history, provides reading statistics, and recommends fanfiction based on a user-specified ship.

**Login to AO3 is required for history access.**

## Features

* **Fetches your AO3 history:** Obtain a JSON file with all your works read.
* **Reading History Analysis:** Generates statistics from your AO3 reading history.
* **Personalized Fanfic Recommendations:** Suggests new, unread fanfics based on your historical reading patterns.

## How it Works

The project constructs a user profile from your AO3 reading history.

For generating recommendations based on a user-provided ship:
1.  New, unread fanfics relevant to the specified ship are collected from AO3.
2.  A recommendation score for each unread fanfic is calculated.
3.  Fanfics are ranked by their recommendation score, and the top-scoring items are presented.

## How to Run

### Locally
1.  Clone the repository: `git clone https://github.com/cosqf/ao3-fic-recommendation`
2.  Set up a virtual environment (recommended): `python -m venv venv`
    * On Windows: `.\venv\Scripts\activate`
    * On macOS/Linux: `source venv/bin/activate`

3. Install dependencies:
   `pip install -r requirements.txt`

4. Install browser binaries:
   `playwright install chromium`

   **Linux only:** if you get missing dependency errors, run: 
    >`playwright install-deps chromium`

   **Windows only:** if `playwright` is not recognized after install,
   > try `python -m playwright install chromium`

5. Run the application:
   `streamlit run main.py`

### Known issues

Cloudflare may flag the activity as bot-like, and issue a captcha. You will notice that happening if the browser gets a timeout. If that happens, run instead with: `streamlit run main.py -- --no-headless`, and do the captcha.