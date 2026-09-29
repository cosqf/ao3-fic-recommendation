import streamlit as st 
from call_api import stream_backend
import pandas as pd
import numpy as np

def get_history():
    st.markdown('<div class="archive-sub">Reading AO3 // Fetching Ledger</div>', unsafe_allow_html=True)
    st.title("Getting AO3 History")

    if st.session_state.logging_in:
        render_login_and_scrape()
    else:
        render_results()

    st.markdown("---")
    if st.button("← Go back"):
        st.session_state.current_page = "intro"
        st.rerun()

def render_login_and_scrape():
    error_state = st.session_state.get("scrape_error")
    if error_state:
        render_error_recovery(error_state)
        return

    form_placeholder = st.empty()
 
    with form_placeholder.container():
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
 
    if not submit_button:
        return
 
    if not (username and password):
        status.warning("Please provide both username and password.")
        return
 
    final_records = None
    payload = {
        "username": username,
        "password": password,
        "df": st.session_state.df.to_dict(orient="records"),
    }

    starting_later = True
    starting_bookmarks = True
        
    for event_type, message, data in stream_backend("scrape", payload):
 
        if event_type == "STATUS":
            status.markdown(f'<p class="archive-sub">{message}</p>', unsafe_allow_html=True)

        elif event_type == "LOGIN_FAILED":
            status.error(message)
            st.session_state.logged_in = False
            return
 
        elif event_type == "LOGIN_SUCCESS":
            form_placeholder.empty()
            status.empty()
            st.toast(message)
            st.session_state.username = username
            st.session_state.password = password
            st.session_state.logged_in = True
 
            with st.container(border=True):
                main_title_placeholder = st.empty()
                main_title_placeholder.markdown('<div class="archive-sub" style="margin-bottom: 10px;">Compiling Ledger...</div>', unsafe_allow_html=True)
                progress_bar = st.progress(0)
                st.write("")
                spacer_left, col1, col2, spacer_right = st.columns([1.7, 1, 1, 1.7])
                with col1:
                    page_metric = st.empty()
                    page_metric.metric("Page Progress", "1 / ?")
                with col2:
                    works_metric = st.empty()
                    works_metric.metric("Works found", "0")
                st.divider()
                title_status = st.empty()
 
        elif event_type == "HISTORY_PROGRESS" and data:
            if "total_pages" in data and "current_page" in data:
                pct = min(1.0, data["current_page"] / data["total_pages"])
                progress_bar.progress(pct)
                page_metric.metric("Page Progress", f"{data['current_page']} / {data['total_pages']}")
            if "valid_works" in data:
                works_metric.metric("Works Found", str(data["valid_works"]))
            if "title" in data:
                display_title = data["title"][:55] + "..." if len(data["title"]) > 55 else data["title"]
                title_status.markdown(f"""
                    <div style='text-align: center; line-height: 1.4;'>
                        <span style='color: gray; font-size: 0.9em;'>Currently Reading</span><br>
                        <span style='font-size: 1.1em;'><i>{display_title}</i></span>
                        <p></p>
                    </div>
                """, unsafe_allow_html=True)

        elif event_type == "HISTORY_DONE":
            progress_bar.progress(1.0)
            st.balloons()
            title_status.markdown("<p style='text-align: center; color: #8c2d19;'><b>History Done!</b></p>", unsafe_allow_html=True)
            
            
 
        elif event_type == "MARKED_LATER_PROGRESS" and data:
            if starting_later:
                main_title_placeholder.markdown('<div class="archive-sub" style="margin-bottom: 10px;">Removing unread from the pile...</div>', unsafe_allow_html=True)
                progress_bar.progress(0)
                starting_later = False 
            
            if "total_pages" in data and "current_page" in data:
                pct = min(1.0, data["current_page"] / data["total_pages"])
                progress_bar.progress(pct)
                page_metric.metric("Page Progress", f"{data['current_page']} / {data['total_pages']}")
            if "valid_works" in data:
                works_metric.metric("To read later", str(data["valid_works"]))
            if "title" in data:
                display_title = data["title"][:55] + "..." if len(data["title"]) > 55 else data["title"]
                title_status.markdown(f"""
                    <div style='text-align: center; line-height: 1.4;'>
                        <span style='color: gray; font-size: 0.9em;'>Currently Reading</span><br>
                        <span style='font-size: 1.1em;'><i>{display_title}</i></span>
                        <p></p>
                    </div>
                """, unsafe_allow_html=True)

        elif event_type == "MARKED_LATER_DONE":
            progress_bar.progress(1.0)
            st.balloons()
            title_status.markdown("<p style='text-align: center; color: #8c2d19;'><b>Removed Marked for Later!</b></p>", unsafe_allow_html=True)
 
        elif event_type == "BOOKMARK_PROGRESS" and data:
            if starting_bookmarks:
                bookmarks_tagged = 0
                main_title_placeholder.markdown('<div class="archive-sub" style="margin-bottom: 10px;">Cross-referencing bookmarks...</div>', unsafe_allow_html=True)
                progress_bar.progress(0)
                starting_bookmarks = False 

            if "total_pages" in data and "current_page" in data:
                tot = data["total_pages"] if isinstance(data["total_pages"], int) else 1
                cur = data["current_page"]
                pct = min(1.0, cur / tot)
                progress_bar.progress(pct)
                page_metric.metric("Page Progress", f"{cur} / {tot}")
                
            if "title" in data:
                bookmarks_tagged += 1
                works_metric.metric("Bookmarks checked", str(bookmarks_tagged))
                display_title = data['title'][:55] + "..." if len(data['title']) > 55 else data['title']
                
                title_html = f"""
                <div style='text-align: center; line-height: 1.4;'>
                    <span style='color: gray; font-size: 0.9em;'>Validating Match</span><br>
                    <span style='font-size: 1.1em;'><i>{display_title}</i></span>
                    <p></p>
                </div>
                """
                title_status.markdown(title_html, unsafe_allow_html=True)

        elif event_type == "BOOKMARK_DONE":
            progress_bar.progress(1.0)
            st.balloons()
            title_status.markdown("<p style='text-align: center; color: #8c2d19;'><b>Bookmarks Synchronized!</b></p>", unsafe_allow_html=True)

        elif event_type == "ERROR":
            st.session_state.scrape_error = {"message": message, "partial_data": data}
            st.rerun()
 
        elif event_type == "DONE":
            final_records = data
            title_status.markdown("<p style='text-align: center; color: #8c2d19;'><b>Done!</b></p>", unsafe_allow_html=True)
 
    if final_records is not None:
        st.session_state.df = pd.DataFrame(final_records)
        st.session_state.scrape_complete = True
        st.session_state.logging_in = False
        st.balloons()
        st.rerun()

def render_error_recovery(error_state):
    message = error_state.get("message", "Something went wrong.")
    partial_data = error_state.get("partial_data")
 
    st.error(message)
 
    if partial_data:
        st.write(f"Currently with **{len(partial_data)}** works stored.")
 
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Fetch again", use_container_width=True):
            del st.session_state["scrape_error"]
            st.rerun()
    with col2:
        if st.button(
            "Go with what I got",
            use_container_width=True,
            disabled=not partial_data,
            help=None if partial_data else "Nothing was scraped before the error.",
        ):
            st.session_state.df = pd.DataFrame(partial_data)
            st.session_state.scrape_complete = True
            st.session_state.logging_in = False
            del st.session_state["scrape_error"]
            st.rerun()
 


def render_results():
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
            use_container_width=True,
        )
    with col2:
        if st.button("Enter the Archives →", type="primary", use_container_width=True):
            st.session_state.current_page = "wrapper"
            st.rerun()