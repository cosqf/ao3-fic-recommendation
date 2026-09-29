from pathlib import Path

WORK_DF_COL = ["fic_id", "title", "author", "rating", "orientations" ,"fandom", "ships", "tags",  "word_count", "last_visited", "bookmarked", "summary"]

API_PORT = 8080

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_DIR = ROOT_DIR / "backend"