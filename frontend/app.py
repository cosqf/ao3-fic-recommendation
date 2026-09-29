import streamlit as st
import sys
import call_api
from page.Intro import intro
from page.Get_History import get_history
from page.Stats import stats
from page.Wrapper import wrapper
from page.Recommend import recommend
from config import FRONTEND_DIR

def main():
    st.set_page_config(page_title="AO3 Stats", layout="centered")
    
    # defaults
    if "username" not in st.session_state:     st.session_state.username = ""
    if "df" not in st.session_state:           st.session_state.df = None
    if "current_page" not in st.session_state: st.session_state.current_page = "intro"
    if "theme" not in st.session_state:        st.session_state.theme = "light"
    if "logged_in" not in st.session_state:    st.session_state.logged_in = False

    # theme
    theme = st.context.theme.type          # "light" or "dark"
    print (FRONTEND_DIR)
    with open(f"{FRONTEND_DIR}/styles/{theme}.css", "r") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    # routing
    print (f"- {st.session_state.current_page}")
    routes = {
        "intro": intro,
        "get_history": get_history,
        "wrapper": wrapper,
        "stats": stats,
        "rec": recommend
    }

    page = st.session_state.current_page
    if page in routes:
        routes[page]()
    else:
        st.error(f"Unknown page: {page}")
    
if __name__ == "__main__":
    main()