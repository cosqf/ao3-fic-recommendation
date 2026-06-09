import streamlit as st 

def get_history():
    st.title ("Get history")
    username = st.text_input("Username", max_chars=40)
    st.session_state.username = username
    if st.button ("Intro"):
        st.session_state.current_page = "intro"
        st.rerun()