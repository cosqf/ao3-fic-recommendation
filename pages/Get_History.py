import streamlit as st 
from web import logIn, gettingHistory, checkBookmarks, scrap_unread_fics, printWorkInfo

def get_history():
    st.markdown('<div class="archive-sub">Reading AO3 // Fetching Ledger</div>', unsafe_allow_html=True)
    st.title("Getting AO3 History")

    from main import get_worker
    worker = get_worker()
    logging_in = st.session_state.username == ""

    # logging in
    if logging_in:
        st.markdown("""
            <p class="serif-body">
                To read your history, your AO3 username and password is needed.
            </p>
            <p class="serif-body" style="font-size: 0.9rem; color:#6e5f4b;">
                No one has access to your session but yourself.
            </p>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("Username", max_chars=40)
            password = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Access Archives")

        status = st.empty()

        if submit_button and username and password:
            success = logIn(worker, username, password, status)
            if success:
                st.session_state.username = username
                # Reset the scraping flag on a fresh login
                st.session_state.scrape_complete = False 
                status.success("Login successful!")
                status.empty()
                st.rerun()
        else:
            st.session_state.logged_in = False

    # scraping and results
    else: 
        if not st.session_state.get("scrape_complete", False):
            
            updated_df = gettingHistory(worker, st.session_state.username, st.session_state.df)
            
            st.session_state.df = updated_df
            st.session_state.scrape_complete = True
            st.rerun()
            
        else:
            # completion menu
            st.write("✨ Ledger compilation complete!")
            st.markdown(f"**{len(st.session_state.df)} total works** are now saved in your active session.")
            
            st.markdown("<br>", unsafe_allow_html=True) 
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    label="Download Backup (JSON)", 
                    data=st.session_state.df.to_json(),
                    file_name=f"{st.session_state.username}_history_data.json", 
                    mime="application/json",
                    icon="📩",
                    on_click="ignore",
                    use_container_width=True
                )
            with col2:
                if st.button("Enter the Archives (Go to Stats) →", type="primary", use_container_width=True):
                    st.session_state.current_page = "stats" 
                    st.rerun()
        
    st.markdown("---")
    if st.button("← Go back"):
        st.session_state.current_page = "intro"
        st.rerun()