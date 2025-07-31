# ao3-fic-recommendation
A web scrapper that processes your Archive of Our Own (AO3) reading history, provides reading statistics, and recommends fanfiction based on a user-specified ship.

**Login to AO3 is required for history access.**

## Features

* **Reading History Analysis:** Generates statistics from your AO3 reading history.
* **Personalized Fanfic Recommendations:** Suggests new, unread fanfics based on your historical reading patterns.

## How it Works

The project constructs a user profile from your AO3 reading history. This profile incorporates features derived from:

* **Content Descriptors:** Descriptors such as fandoms, ships and tags are converted into numerical vectors using **TF-IDF**.
* **Numerical Attributes:** Fanfic word counts are normalized using **MinMaxScaler**.
* **Engagement Metrics:** Recency of historical reading activity and bookmark status are applied as weights. Bookmarked works and works read more recently contribute a higher weight to the user profile.

For generating recommendations based on a user-provided ship:
1.  New, unread fanfics relevant to the specified ship are collected from AO3.
2.  A recommendation score for each unread fanfic is calculated.
3.  Fanfics are ranked by their recommendation score, and the top-scoring items are presented.

## How to Run

### Using Google Collab
Access and run the project online via this [link](https://colab.research.google.com/drive/1fIdHS0ceLlHEKqSwpPvVoWh7-quhbq3x).

### Locally
1.  Clone the repository: `git clone https://github.com/cosqf/ao3-fic-recommendation`
2.  Set up a virtual environment (recommended): `python -m venv venv`
    * On Windows: `.\venv\Scripts\activate`
    * On macOS/Linux: `source venv/bin/activate`
4.  Install dependencies:
    `pip install -r requirements.txt`
    `playwright install`
5.  Run the application:
    `python main.py`

