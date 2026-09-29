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
1. Clone the repository: `git clone https://github.com/cosqf/ao3-fic-recommendation
2.  Set up a virtual environment (recommended): `python -m venv venv`
    * On Windows: `.\venv\Scripts\activate`
    * On macOS/Linux: `source venv/bin/activate`
`

* There's two options to run the backend: fully local, or via Docker

#### Local backend

1. Install the project with both back and frontend dependencies:
   `pip install -e ".[backend,frontend]"`

2. Install the browser binary:
   `camoufox fetch`

   **Linux only:** if this fails with missing system library errors,
   install: `wget libglib2.0-0 libnss3 libatk1.0-0 libatk-bridge2.0-0
   libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3
   libxrandr2 libgbm1 libasound2`

3. Run it, from the repo root:
  * Backend:
   `uvicorn backend.main:app --port 8080 --reload`

#### Docker backend

1. Build the image, from the repo root:
   `docker build -t ao3-backend .`

2. Run it, mapping the container's port to your machine:
   `docker run -p 8080:8080 ao3-backend`

#### Frontend

1. Set up a virtual environment and install frontend dependencies (if you
   haven't already, from the steps above):
   `pip install -e ".[frontend]"`

2. Run it, from the repo root, in its own terminal:
   `streamlit run frontend/app.py`

   The frontend talks to the backend over HTTP at `http://localhost:8080` by default.
