import streamlit as st
import json


def intro():
    # Header & Meta Info
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
        find_unread = st.checkbox("Find unread fics besides these", value=False)

        uploaded_file = st.file_uploader(
            "Upload your history JSON file", 
            type=["json"], 
            label_visibility="collapsed"
        )
        
        if uploaded_file is not None:
            try:
                history_data = json.load(uploaded_file)
                st.session_state.df = history_data
                st.success("File uploaded successfully.")
                
                if find_unread:
                    st.session_state.current_page = "progress"
                else:
                    st.session_state.current_page = "stats"
                st.rerun()
            except Exception as e:
                st.error(f"Error reading file: {e}")

    with col2:
        st.markdown("### Option 2: Get Live History")
        st.markdown('<p class="serif-body" style="font-size: 1rem;">Log into your account to let the scraper scan and pull your history pages automatically.</p>', unsafe_allow_html=True)
        st.write("")         
        st.write("") 
        st.write("")
        
        if st.button("FETCH FROM AO3 →", use_container_width=True):
            st.session_state.current_page = "progress"
            st.rerun()

# --- App Initialization & Routing Test Block ---
if __name__ == "__main__":
    # Initialize basic routing defaults if testing this file directly
    if "current_page" not in st.session_state:
        st.session_state.current_page = "intro"
    if "df" not in st.session_state:
        st.session_state.df = None

    if st.session_state.current_page == "intro":
        intro()
    elif st.session_state.current_page == "progress":
        st.title("Transitioning to Live Scraper Screen...")
        if st.button("← Back to Archive Document"):
            st.session_state.current_page = "intro"
            st.rerun()
    elif st.session_state.current_page == "stats":
        st.title("📊 Your Stats Dashboard Layout")
        if st.button("← Reset Dossier"):
            st.session_state.current_page = "intro"
            st.session_state.df = None
            st.rerun()

