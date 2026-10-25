import streamlit as st
import json
import pandas as pd
import re
from config import WORK_DF_COL

def convert_external(records):
    rows = []
    for r in records:
        try:
            visited = pd.to_datetime(r["userStats"]["lastVisited"], format="%d %b %Y", errors="coerce")
            if not r["fandoms"] or pd.isna(visited):   # mystery works have no fandoms
                continue
            rows.append([
                int(r["id"]),
                r["title"],
                [r["author"]],
                r["rating"],
                [c.strip() for c in r["category"].split(",") if c.strip()],
                sorted(f["name"] for f in r["fandoms"]),
                [t["name"] for t in r["tags"]["relationships"]],
                [t["name"] for t in r["tags"]["freeforms"]],
                int(r["stats"]["wordCount"]),
                visited,
                False,
                r["summary"],
            ])
        except (KeyError, TypeError, ValueError):
            continue
    df = pd.DataFrame(rows, columns=WORK_DF_COL)
    return df.sort_values("last_visited", ascending=False).drop_duplicates("fic_id").reset_index(drop=True)

def intro():
    st.markdown('<div class="archive-sub">AO3 Stats // Reading Ledger</div>', unsafe_allow_html=True)
    st.title("AO3 History Dashboard")
    
    st.markdown("""
    <p class="serif-body">
        Welcome to your AO3 reading dashboard. This app helps you analyze your reading habits, 
        map out your favorite tropes and relationships, and find unread fic recommendations based on your history.
    </p>
    <p class="serif-body">
        To get started, please select how you want to load your data below.
    </p>
    <div class="flourish">𓆝 𓆟 𓆞 𓆝 𓆟</div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("### Option 1: Get Live History")
        st.markdown('<p class="serif-body" style="font-size: 1rem;">Log into your account to let the scraper scan and pull your history pages automatically.</p>', unsafe_allow_html=True)
        st.write("")
        st.write("")         
        st.write("")
        st.write("")
        st.write("")
        
        if st.button("FETCH FROM AO3 →", use_container_width=True):
            st.session_state.df = pd.DataFrame(columns= WORK_DF_COL)
            st.session_state.current_page = "get_history"
            st.session_state.logging_in = True
            st.rerun()

    with col2:
        st.markdown("### Option 2: Upload JSON")
        st.markdown('<p class="serif-body" style="font-size: 1rem;">If you already have a saved history file, drop it here to open it instantly.</p>', unsafe_allow_html=True)
        st.text("About compatibility.", help="Currently, only JSONs obtained via this website are fully compatible. Zaki (https://ao3-history.nazalibhai.com/) will work, but it does not support bookmarks.")
        find_read = st.checkbox("Read history for newer fics", value=False, help="If selected, your history will be pulled until a fic that has already been saved is found.")

        uploaded_file = st.file_uploader(
            "Upload your history JSON file", 
            type=["json"], 
            label_visibility="collapsed",
            max_upload_size = 10
        )
        
        if uploaded_file is not None:
            try:
                filename = uploaded_file.name
                match = re.match(r'(\w+)_history_data(\(\d*\))?\.json', filename)
                if match:
                    username = match.group(1)
                    if username != "-1":
                        st.session_state.username = username
                        
                data = json.loads(uploaded_file.getvalue())

                if isinstance(data, list):
                    history_data = convert_external(data)
                    if history_data.empty:
                        raise ValueError("no usable works found in this file")
                    print(f"[upload] external format: {len(history_data)} of {len(data)} entries kept")
                else:
                    print ("internal json")
                    history_data = pd.read_json(uploaded_file)

                history_data['last_visited'] = pd.to_datetime(history_data['last_visited'], unit='ms', errors='coerce')

                print (history_data['last_visited'].max())
                st.session_state.df = history_data
                st.success("File uploaded successfully.")
                
                if find_read:
                    st.session_state.logging_in = True
                    st.session_state.current_page = "get_history"
                else:
                    st.session_state.current_page = "wrapper"
                st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")