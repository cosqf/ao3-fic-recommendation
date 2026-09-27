import streamlit as st 
import pandas as pd
from call_api import stream_backend


def recommend():
    st.markdown('<div class="archive-sub">Reading AO3 // Probing the Shelves</div>', unsafe_allow_html=True)
    st.title("Finding Suggestions")
 
    if not st.session_state.get("scrape_unread_complete", False):
        render_ship_and_login()
    else:
        display_fics()
 
    st.markdown("---")
    if st.button("← Go back"):
        st.session_state.current_page = "intro"
        st.rerun()
 
 
def render_ship_and_login():
    if not st.session_state.get("ship_chosen", False):
        ship_set = sorted({
            s for row in st.session_state.df["ships"] if isinstance(row, list)
            for s in row if "/" in s or "&" in s
        })
        ship = st.selectbox(
            "Choose a ship you wish to read more of...",
            ship_set,
            index=ship_set.index(st.session_state.chosen_ship)
                if st.session_state.get("chosen_ship") in ship_set else 0,
        )
        if st.button("Find Fics →", type="primary"):
            st.session_state.ship_chosen = True
            st.session_state.chosen_ship = ship
            st.rerun()
        return
 
    username = st.session_state.get("username")
    password = st.session_state.get("password")
 
    if not (username and password):
        login_error = st.session_state.pop("login_error", None)
        if login_error:
            st.error(login_error)
 
        st.markdown("""
            <p class="serif-body">
                To find the most fics, your AO3 username and password is needed.
            </p>
            <p class="serif-body" style="font-size: 0.9rem; color:#6e5f4b;">
                No one has access to your session but yourself.
            </p>
        """, unsafe_allow_html=True)
 
        with st.form("recommend_login_form"):
            username_input = st.text_input("Username", max_chars=40)
            password_input = st.text_input("Password", type="password")
            submit_button = st.form_submit_button("Access Archives")
 
        if not submit_button:
            return
 
        if not (username_input and password_input):
            st.warning("Please provide both username and password.")
            return
 
        st.session_state.username = username_input
        st.session_state.password = password_input
        st.rerun()
        return
 
    payload = {
        "username": username,
        "password": password,
        "df": st.session_state.df.to_dict(orient="records"),
        "ship": st.session_state.chosen_ship,
    }
    fetch_works(payload)
 
 
def fetch_works(payload):
    with st.container(border=True):
        st.markdown('<div class="archive-sub" style="margin-bottom: 10px;">Probing the Shelves...</div>', unsafe_allow_html=True)
        progress_bar = st.progress(0)
        st.write("")
 
        spacer_left, col1, col2, spacer_right = st.columns([1.7, 1, 1, 1.7])
        with col1:
            works_metric = st.empty()
            works_metric.metric("Unread Found", "0")
        with col2:
            tag_metric = st.empty()
            tag_metric.metric("Tag Pass", "—")
        st.divider()
        status_display = st.empty()
        tags_display = st.empty()
 
    max_fics = 200
    final_records = None
 
    for event_type, message, data in stream_backend("fetch_works", payload):
 
        if event_type == "STATUS":
            status_display.markdown(
                f"<p style='text-align:center; color:gray; font-size:0.9em;'>{message}</p>",
                unsafe_allow_html=True,
            )
            # .markdown(f'<p class="archive-sub">{message}</p>', unsafe_allow_html=True)
 
        elif event_type == "LOGIN_FAILED":
            st.session_state.logged_in = False
            st.session_state.pop("username", None)
            st.session_state.pop("password", None)
            st.session_state.login_error = message
            st.rerun()
 
        elif event_type == "LOGIN_SUCCESS":
            st.toast(message)
            st.session_state.logged_in = True
 
        elif event_type == "UNREAD_PROGRESS" and data:
            if "max_fics" in data:
                max_fics = data["max_fics"]
 
            if "valid_works" in data:
                current_count = data["valid_works"]
                works_metric.metric("Unread Found", str(current_count))
                progress_bar.progress(min(1.0, current_count / max_fics))
 
            if "status" in data:
                status_text = data["status"]
                tag_match = [w for w in status_text.split() if w.isdigit()]
                if "tags" in status_text and tag_match:
                    tag_metric.metric("Tag Pass", f"{tag_match[0]} tags")
                status_display.markdown(
                    f"<p style='text-align:center; color:gray; font-size:0.9em;'>{status_text}</p>",
                    unsafe_allow_html=True,
                )
 
            if "current_tags" in data:
                tag_pills = " ".join(
                    f"<span style='background:muted; color:bg; border-radius:12px; "
                    f"padding:2px 10px; margin:2px; font-size:0.8em; display:inline-block;'>"
                    f"{tag}</span>"
                    for tag in data["current_tags"]
                )
                tags_display.markdown(
                    f"<div style='text-align:center; margin-top:6px;'>{tag_pills}</div>",
                    unsafe_allow_html=True,
                )
 
        elif event_type == "ERROR":
            status_display.error(message)
            return
 
        elif event_type == "UNREAD_DONE":
            final_records = data
            progress_bar.progress(1.0)
            status_display.markdown(
                "<p style='text-align:center; color:#8c2d19;'><b>Scoring fics...</b></p>",
                unsafe_allow_html=True,
            )
 
    if final_records is not None:
        st.session_state.df_scored_unread_fics = pd.DataFrame(final_records)
        st.session_state.scrape_unread_complete = True
        st.rerun()


def display_fics():
    df_scored = st.session_state.df_scored_unread_fics
    top_n = min(10, len(df_scored))

    if top_n == 0:
        st.warning("No unread fics could be scored for this ship. Try a different one.")
        return

    # HEADER
    st.markdown(f'<div class="archive-sub" style="text-align: center; margin-bottom: 0;">Top {top_n} Picks</div>', unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; margin-bottom: 0;'>Curated for Your Ledger</h2>", unsafe_allow_html=True)
    st.markdown('<p class="serif-body" style="text-align: center;">Ranked by how well they match your historical reading profile.</p>', unsafe_allow_html=True)
    st.markdown('<div class="flourish">✦ &nbsp; ✦ &nbsp; ✦</div>', unsafe_allow_html=True)

    # ENTRIES
    rank = 1
    for i, row in df_scored.head(top_n).iterrows():
        fic_id = row.get("fic_id", "")
        fic_url = f"https://archiveofourown.org/works/{fic_id}"

        title = row.get("title", "Untitled") or "Untitled"
        
        author_data = row.get("author", ["Unknown"])
        author_str = ", ".join(author_data) if isinstance(author_data, list) else author_data

        summary = row.get("summary", "")

        score = row.get("recommendation_score", 0.0)
        
        words = row.get("word_count", 0)
        words_str = f"{int(words):,}" if pd.notna(words) and words else "Unknown"

        fandoms = row.get("fandom", [])
        fandom_str = " · ".join(fandoms) if isinstance(fandoms, list) and fandoms else "Varied Lore"

        ships = row.get("ships", [])
        ship_str = " · ".join(ships) if isinstance(ships, list) and ships else ""

        tags = row.get("tags", [])

        with st.container(border=True):
            # rank and score
            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown(f'<div class="archive-sub" style="margin-bottom: 0;">Entry No. {rank:02d}</div>', unsafe_allow_html=True)
            with cols[1]:
                st.markdown(f'<div class="archive-sub" style="margin-bottom: 0; text-align: right; color: var(--accent-lt);">Match: {score:.2f}</div>', unsafe_allow_html=True)
            
            # Title
            st.markdown(f'<div class="fic-title"><h3 style="margin-top: 5px; margin-bottom: 10px;"><a href="{fic_url}" target="_blank">{title}</a></h3></div>', unsafe_allow_html=True)
            
            # Metadata
            st.write(f"**Written by:** {author_str} &nbsp;·&nbsp; **Words:** {words_str}")
            st.write(f"**Fandom:** {fandom_str}")
            if ship_str:
                st.write(f"**Ships:** {ship_str}")
            
            # Tags
            if isinstance(tags, list) and tags:
                tag_html = "".join(
                    f"<span style='border: 1px solid var(--border-lt); border-radius: 2px; "
                    f"padding: 2px 8px; margin: 0 4px 6px 0; font-family: \"Courier Prime\", monospace; "
                    f"font-size: 0.75rem; color: var(--muted); display: inline-block; background: var(--bg2);'>{t}</span>"
                    for t in tags[:15]
                )
                st.markdown(f"<div style='margin-top: 10px;'>{tag_html}</div>", unsafe_allow_html=True)

            # Summary
            st.markdown("---")
            if summary:
                st.caption(f"{summary}")

        rank += 1

    # FOOTER & NAV
    st.markdown('<div class="flourish">✦ &nbsp; ✦ &nbsp; ✦</div>', unsafe_allow_html=True)
    
    if st.button("↩ Return to Index (Try another ship)", use_container_width=True):
        st.session_state.ship_chosen = False
        st.session_state.scrape_unread_complete = False
        st.session_state.chosen_ship = None 
        st.rerun()
