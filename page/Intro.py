import streamlit as st
import json
import pandas as pd
import re
from config import WORK_DF_COL

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
        st.markdown("### Option 1: Upload JSON")
        st.markdown('<p class="serif-body" style="font-size: 1rem;">If you already have a saved history file, drop it here to open it instantly.</p>', unsafe_allow_html=True)
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
                match = re.match(r'(\w+)_history_data\.json', filename)
                if match:
                    username = match.group(1)
                    if username != "-1":
                        st.session_state.username = username
                        
                history_data = pd.read_json(uploaded_file)
                history_data['last_visited'] = pd.to_datetime(history_data['last_visited'], unit='ms', errors='coerce')

                print (history_data['last_visited'].max())
                st.session_state.df = history_data
                st.success("File uploaded successfully.")
                
                if find_read:
                    st.session_state.current_page = "get_history"
                else:
                    st.session_state.current_page = "wrapper"
                st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")

    with col2:
        st.markdown("### Option 2: Get Live History")
        st.markdown('<p class="serif-body" style="font-size: 1rem;">Log into your account to let the scraper scan and pull your history pages automatically.</p>', unsafe_allow_html=True)
        st.write("")         
        st.write("")
        st.write("")
        st.write("")
        
        if st.button("FETCH FROM AO3 →", use_container_width=True):
            st.session_state.df = pd.DataFrame(columns= WORK_DF_COL)
            st.session_state.current_page = "get_history"
            st.rerun()
