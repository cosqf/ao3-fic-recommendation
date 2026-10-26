# AO3 Stats & Fanfic Recommendations

This app reads your Archive of Our Own (AO3) reading history, shows statistics about it, and suggests unread fanfics for a ship you choose.

**Logging in to AO3 is required** for the history and recommendations features.

## Features

- **Fetch your AO3 history:** Collect every work you have read, with its metadata (title, tags, fandom, author...). The app can also check your bookmarks and remove works you have marked "Read later" from the list. The result can be downloaded as a JSON file.
- **Load a saved history:** Upload a JSON file from an earlier run to skip fetching. If you tick "Read history for newer fics", the app only fetches works that are newer than the ones already in the file.
- **Year in review:** A short, wrapped-style summary of the current year's reading, with your typical story length, your most-read fandom and ship, and your top author.
- **Reading history analysis:** Explore your history on several tabs:
  - **Summary:** totals, favorite authors, fandom and orientation breakdowns, rating distribution, and story length.
  - **Tropes & Ships:** most common ships, tags, and ship and tag combinations.
  - **Timeline & History:** works read per month, reading by day of the week, and your running word count over time.
  - **Bookmarks:** how your bookmarked works differ from the rest of your history in length, rating, tags and fandoms.
  - **Data Table:** the full list, searchable and sortable, with a sidebar to filter by fandom, ship, rating, orientation, word count and date.

- **Personalized recommendations:** Pick a ship and get up to 10 unread fanfics that match your past reading, with optional tags to include or exclude.

## How it works

**Getting your history.** The app logs in to AO3 with a real browser running in the background, then opens each page of your reading history. Your username and password are used only for this login.

**Building your reading profile.** Each work in your history is turned into a set of features: its fandoms, ships, tags, orientation, rating, and word count. Recent works count more than old ones, and bookmarked works count much more. These features are combined into a single profile that describes your taste.

**Recommending fanfics.** For the ship you choose, the app picks the tags that best describe your reading around that ship, with tags from your wider history used as a backup when the ship is new to you. It searches AO3 with those tags, sorted by kudos, and collects up to 200 unread fanfics. Each one is scored by how similar it is to your profile, and the top 10 are shown.

---

## Use the hosted version

https://ao3-fic-rec.streamlit.app/

---

## Local setup (one time)

1. **Install Python 3.11 to 3.14** from https://www.python.org/downloads/. On Windows, tick **"Add python.exe to PATH"** during install.
2. **Get the project.** Either download it from GitHub (**Code** → **Download ZIP**) and unzip it, or run `git clone https://github.com/cosqf/ao3-fic-recommendation`.
3. **Open a terminal in the project folder.**
   - **Windows:** click the address bar in File Explorer, type `cmd`, press Enter.
   - **macOS:** open Terminal, type `cd ` (with a space), drag the folder into the window, press Enter.
   - **Linux:** open a terminal and use `cd` to enter the folder.
4. **Run these commands**, one at a time, waiting for each to finish.

   **Windows:**
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -e ".[backend,frontend]"
   camoufox fetch
   ```

   **macOS / Linux:**
   ```
   python3 -m venv venv
   source venv/bin/activate
   pip install -e ".[backend,frontend]"
   camoufox fetch
   ```

   On Linux, `camoufox fetch` may fail with missing system libraries. If it does, run this once and then retry the `camoufox fetch` line:
   ```
   sudo apt install wget libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
   ```

---

## Run the app

You need two terminals open in the project folder. In each one, first run the activate command from step 4 (`(venv)` should appear at the start of the line).

- **Terminal 1:** `uvicorn backend.main:app --port 8080`
- **Terminal 2:** `streamlit run frontend/app.py`

Your browser opens at http://localhost:8501. To stop, press **Ctrl + C** in each terminal.

---

## Problems?

| What you see | What to do |
|---|---|
| `'python' is not recognized` (Windows) | Reinstall Python and tick **"Add python.exe to PATH"**. |
| `(venv)` is missing from the line | Run the activate command from step 4 again. |
| "Connection error" or "could not start the browser" | Check that Terminal 1 is still running. |
| "The server is busy" | Wait a few minutes and try again. The server handles only a few runs at a time. |

---

## Notes

- Your username and password are used only to log in to AO3 during a run.
- You can download your history as a JSON file and upload it next time instead of fetching again.
- Partly compatible with [Zaki's AO3 History Exporter](https://github.com/Zaki-1052/AO3-History-Exporter). It doesn't include bookmarks.
- Docker is also possible for the backend. See the developer notes below.

## Developer notes

- Backend: `uvicorn backend.main:app --port 8080 --reload`
- Frontend: `streamlit run frontend/app.py`
- Docker backend: `docker build -t ao3-backend .` then `docker run -p 8080:8080 ao3-backend`
- The frontend reads `BACKEND_URL` from Streamlit secrets if set, otherwise uses `http://localhost:8080`.
- The backend must run as a single instance, because active runs are tracked in memory.

## License

MIT. See `LICENSE`.