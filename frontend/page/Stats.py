import streamlit as st
import pandas as pd
from collections import Counter
from itertools import product as iterproduct
from wrapped import generate_common_ship_tags, generate_common_ship_ratings
import altair as alt


def apply_filters(df, date_from, date_to, fandoms, ships, ratings, orientations, min_words, max_words):
    if df.empty:
        return pd.DataFrame()

    filtered = df.copy()

    def list_contains_any(series, values):
        def _check(cell):
            if not isinstance(cell, list):
                return False
            return any(v in cell for v in values)
        return series.apply(_check)

    if fandoms:
        filtered = filtered[list_contains_any(filtered["fandom"], fandoms)]

    if ships:
        filtered = filtered[list_contains_any(filtered["ships"], ships)]

    if orientations:
        filtered = filtered[list_contains_any(filtered["orientations"], orientations)]

    if ratings:
        filtered = filtered[filtered["rating"].isin(ratings)]

    filtered = filtered[(filtered["word_count"] >= min_words) & (filtered["word_count"] <= max_words)]

    if date_from or date_to:
        # normalise the column once
        dates = pd.to_datetime(filtered["last_visited"]).dt.tz_localize(None)

        if date_from:
            dt_from = pd.to_datetime(date_from).tz_localize(None)
            filtered = filtered[dates >= dt_from]
            # re-compute after row drop
            dates = pd.to_datetime(filtered["last_visited"]).dt.tz_localize(None)

        if date_to:
            dt_to = pd.to_datetime(date_to).tz_localize(None)
            filtered = filtered[dates <= dt_to]

    return filtered


def stats():
    if "filtered_df" not in st.session_state:
        st.session_state.filtered_df = st.session_state.df.copy()

    df = st.session_state.df

    with st.sidebar:
        st.header("Filters")
        st.markdown("Narrow down your reading history.")

        fandom_set      = sorted({f for row in df["fandom"] if isinstance(row, list) for f in row})
        ship_set        = sorted({s for row in df["ships"] if isinstance(row, list) for s in row if "/" in s or "&" in s})
        rating_set      = sorted(df["rating"].dropna().unique())
        orientation_set = sorted({o for row in df["orientations"] if isinstance(row, list) for o in row})

        sel_fandoms      = st.multiselect("Fandoms", fandom_set)
        sel_ships        = st.multiselect("Ships", ship_set)
        sel_ratings      = st.multiselect("Rating", rating_set)
        sel_orientations = st.multiselect("Orientation", orientation_set)

        w_col1, w_col2 = st.columns(2)
        with w_col1:
            min_words = st.number_input("Min Words", min_value=0, value=0, step=1000)
        with w_col2:
            max_words = st.number_input("Max Words", min_value=0, value=1_000_000, step=5000)

        d_col1, d_col2 = st.columns(2)
        with d_col1:
            date_from = st.date_input("Read since", value=None, max_value=pd.Timestamp.now().date())
        with d_col2:
            date_to = st.date_input("Read until", value=None)

        st.markdown("---")

        if st.button("Apply Filters", type="primary", width='stretch'):
            st.session_state.filtered_df = apply_filters(
                df, date_from, date_to,
                sel_fandoms, sel_ships, sel_ratings, sel_orientations,
                min_words, max_words,
            )
            st.rerun()

        if st.button("Clear Filters", width='stretch'):
            st.session_state.filtered_df = df.copy()
            st.rerun()

        n = len(st.session_state.filtered_df)
        total = len(df)
        st.caption(f"Showing **{n}** of **{total}** works")

    st.title("Archive Statistics")
    st.markdown('<p class="archive-sub">Narrow down the graphs using the filters on the sidebar.</p>', unsafe_allow_html=True)

    h_col1, h_spacer1, h_spacer2, h_col2 = st.columns(4)
    with h_col1:
        st.markdown("Analysing your reading history.")
    with h_col2:
        if st.button("GET RECOMMENDATIONS"):
            st.session_state.current_page = "rec"
            st.rerun()

    fdf = st.session_state.filtered_df

    if fdf.empty:
        st.warning("No works match the current filters. Try loosening them.")
        st.markdown("---")
        if st.button("← Back to Hub"):
            st.session_state.current_page = "intro"
            st.rerun()
        return

    tab_summary, tab_tropes, tab_timeline, tab_bookmarks, tab_data = st.tabs([
        "Summary",
        "Tropes & Ships",
        "Timeline & History",
        "Bookmarks",
        "Data Table",
    ])

    with tab_summary:
        fdf = st.session_state.filtered_df

        if fdf.empty:
            st.info("No works match your current filter criteria.")
        else:
            with st.container(border=True):
                st.subheader("At a glance")
                m1, m2, m3, m4 = st.columns(4)
                
                total_works = len(fdf)
                total_words = int(fdf['word_count'].sum())
                median_words = int(fdf['word_count'].median()) if total_works > 0 else 0
                unique_fandoms = fdf["fandom"].explode().nunique()

                m1.metric("Works read",          f"{total_works:,}")
                m2.metric("Total words",         f"{total_words:,}")
                m3.metric("Median words / work", f"{median_words:,}")
                m4.metric("Unique fandoms",      f"{unique_fandoms:,}")

            # AUTHORS
            with st.container(border=True):
                st.subheader("Your favourite authors")
                author_counts = Counter(
                    a.strip()
                    for cell in fdf["author"]
                    if isinstance(cell, list)
                    for a in cell
                )
                if author_counts:
                    top_authors = pd.DataFrame(
                        author_counts.most_common(10),
                        columns=["Author", "Works"]
                    )
                    # Pure native Streamlit interactive bar chart
                    st.bar_chart(top_authors, x="Author", y="Works", color="primary", horizontal=True, sort=False)
                else:
                    st.info("No author data available.")

            # FANDOM
            with st.container(border=True):
                st.subheader("Fandom breakdown")
                fandom_counts = Counter(f.strip() for cell in fdf["fandom"] if isinstance(cell, list) for f in cell)
                top_fandoms = pd.DataFrame(
                    fandom_counts.most_common(10),
                    columns=["Fandom", "Count"]
                )

                denom = total_works if total_works > 0 else 1
                top_fandoms["Proportion"] = top_fandoms["Count"] / denom

                st.dataframe(
                    top_fandoms,
                    column_config={
                        "Fandom": "Fandom",
                        "Count": "Works Read",
                        "Proportion": st.column_config.ProgressColumn(
                            "Share of Total Reading",
                            min_value=0.0,
                            max_value=1.0
                        )
                    },
                    hide_index=True,
                    width='stretch'
                )

            # ORIENTATION 
            with st.container(border=True):
                st.subheader("Orientation breakdown")
                orient_counts = Counter(o.strip() for cell in fdf["orientations"] if isinstance(cell, list) for o in cell)
                if orient_counts:
                    top_orients = pd.DataFrame(
                        orient_counts.most_common(10),
                        columns=["Orientation", "Count"]
                    )
                    
                    col_o1, col_o2 = st.columns([2, 1])
                    with col_o1:
                        st.bar_chart(top_orients, x="Orientation", y="Count", color="primary", sort=False)
                    with col_o2:
                        denom = total_works if total_works > 0 else 1
                        top_orients["Percentage"] = (top_orients["Count"] / denom * 100).round(1).astype(str) + "%"
                        st.dataframe(
                            top_orients[["Orientation", "Percentage"]],
                            hide_index=True,
                            width='stretch'
                        )
                else:
                    st.info("No orientation data available.")

            # RATINGS
            with st.container(border=True):
                st.subheader("Rating distribution")
                rating_counts = fdf["rating"].value_counts().reset_index()
                rating_counts.columns = ["Rating", "Count"]
                rating_counts["Proportion"] = rating_counts["Count"] / len(fdf)

                st.dataframe(
                    rating_counts,
                    column_config={
                        "Rating": "Age Rating",
                        "Count": "Works Read",
                        "Proportion": st.column_config.ProgressColumn("Share", min_value=0.0, max_value=1.0)
                    },
                    hide_index=True, width='stretch'
                )

            # WORD COUNT 
            with st.container(border=True):
                st.subheader("Reading distribution by story length")
                
                if not fdf.empty and fdf['word_count'].notna().any():
                    bins = [0, 1000, 5000, 10000, 50000, 100000, float('inf')]
                    labels = ["Under 1k", "1k - 5k", "5k - 10k", "10k - 50k", "50k - 100k", "100k+"]
                    
                    binned_words = pd.cut(
                        fdf['word_count'].fillna(0), 
                        bins=bins, 
                        labels=labels, 
                        include_lowest=True
                    )
                    
                    word_dist = binned_words.value_counts().reindex(labels).reset_index()
                    word_dist.columns = ["Length Range", "Number of Works"]
                    
                    chart = alt.Chart(word_dist).mark_line(
                        strokeWidth=3, 
                        color="#8c2d19",
                        point=alt.OverlayMarkDef(color="#8c2d19", size=60)
                    ).encode(
                        x=alt.X('Length Range:N', sort=labels, title=""),
                        y=alt.Y('Number of Works:Q', title="Works Read")
                    ).properties(height=300)
                    
                    st.altair_chart(chart, width='stretch')
                else:
                    st.info("No word count data available to plot.")
                    
    # SHIPS
    with tab_tropes:
        
        # TOP SHIPS 
        with st.container(border=True):
            st.subheader("Most common relationships")
            ship_counts = Counter(ship.strip() for cell in fdf["ships"] if isinstance(cell, list) for ship in cell if '/' in ship or '&' in ship)
            
            if ship_counts:
                top_ships = pd.DataFrame(ship_counts.most_common(100), columns=["Ship", "Count"])
                top_ships["Proportion"] = top_ships["Count"] / len(fdf)

                st.dataframe(
                    top_ships,
                    column_config={
                        "Ship": "Ship",
                        "Count": "Works",
                        "Proportion": st.column_config.ProgressColumn("Share", min_value=0.0, max_value=1.0)
                    },
                    hide_index=True, width='stretch'
                )
            else:
                st.info("No relationship data available.")

        # TOP TAGS
        with st.container(border=True):
            st.subheader("Most common tags")
            tag_counts = Counter(tag.strip() for cell in fdf["tags"] if isinstance(cell, list) for tag in cell)
            
            if tag_counts:
                top_tags = pd.DataFrame(tag_counts.most_common(100), columns=["Tag", "Count"])
                top_tags["Proportion"] = top_tags["Count"] / len(fdf)

                st.dataframe(
                    top_tags,
                    column_config={
                        "Tag": "AO3 Tag",
                        "Count": "Occurrences",
                        "Proportion": st.column_config.ProgressColumn("Share", min_value=0.0, max_value=1.0)
                    },
                    hide_index=True, width='stretch'
                )
            else:
                st.info("No tag data available.")

        # ship tag combos
        with st.container(border=True):
            st.subheader("Most common ship × tag combos")

            # ship filter
            all_ships_for_filter = sorted({
                s for cell in fdf["ships"]
                if isinstance(cell, list)
                for s in cell
                if "/" in s or "&" in s
            })
            
            selected_ship_filter = st.selectbox("Filter by ship (optional)", ["— all ships —"] + all_ships_for_filter,
                key="ship_tag_filter")
            ship_arg = None if selected_ship_filter == "— all ships —" else selected_ship_filter

            # tag filter
            all_tags_for_filter = sorted({
                t.strip() for cell in fdf["tags"]
                if isinstance(cell, list)
                for t in cell
            })
            selected_tag_filter = st.selectbox(
                "Filter by tag (optional)", 
                ["— all tags —"] + all_tags_for_filter,
                key="tag_filter"
            )
            tag_arg = None if selected_tag_filter == "— all tags —" else selected_tag_filter

            combo_df = generate_common_ship_tags(fdf, ship_tag=ship_arg, tag_filter=tag_arg)
            if combo_df.empty:
                st.info("No tag/ship co-occurrence data available.")
            else:
                st.dataframe(
                    combo_df.head(20),
                    column_config={
                        "ship": "Relationship Pairing",
                        "tag": "AO3 Additional Tag",
                        "count": st.column_config.NumberColumn("Occurrences", format="%d")
                    },
                    hide_index=True,
                    width='stretch'
                )

        # ship rating combos
        with st.container(border=True):
            st.subheader("Most common ship × rating combos")

            selected_ship_filter_rating = st.selectbox("Filter by ship (optional)", ["— all ships —"] + all_ships_for_filter,
                key="ship_rating_filter")
            ship_arg_rating = None if selected_ship_filter_rating == "— all ships —" else selected_ship_filter_rating

            # rating filter
            all_ratings_for_filter = sorted({
                str(cell).strip() for cell in fdf["rating"]
                if pd.notna(cell)
            })
            selected_rating_filter = st.selectbox(
                "Filter by rating (optional)", 
                ["— all ratings —"] + all_ratings_for_filter,
                key="rating_filter"
            )
            rating_arg = None if selected_rating_filter == "— all ratings —" else selected_rating_filter

            combo_df_rating = generate_common_ship_ratings(fdf, ship_tag=ship_arg_rating, rating_tag=rating_arg)
            if combo_df_rating.empty:
                st.info("No rating/ship co-occurrence data available.")
            else:
                st.dataframe(
                    combo_df_rating.head(20),
                    column_config={
                        "ship": "Relationship Pairing",
                        "rating": "Age Rating",
                        "count": st.column_config.NumberColumn("Occurrences", format="%d")
                    },
                    hide_index=True,
                    width='stretch'
                )

    # TIMELINE
    with tab_timeline:

        ts = pd.to_datetime(fdf["last_visited"]).dt.tz_localize(None)
        timeline_df = fdf.copy()
        timeline_df["_date"] = ts

        # works read per month
        with st.container(border=True):
            st.subheader("Works read per month")
            monthly = (
                timeline_df.set_index("_date")
                .resample("ME")
                .size()
                .reset_index(name="Works")
            )
            monthly.columns = ["Month", "Works"]
            
            month_chart = alt.Chart(monthly).mark_bar().encode(
                x=alt.X('Month:T', title=None),  # :T means its a timeline
                y=alt.Y('Works:Q', title="Works Read"),
                color=alt.Color('Works:Q', scale=alt.Scale(scheme='reds'), legend=None)
            ).properties(height=300)
            
            st.altair_chart(month_chart, width='stretch')

        # reading by day of week 
        with st.container(border=True):
            st.subheader("Reading by day of week")
            
            dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            dow = timeline_df["_date"].dt.day_name().value_counts().reindex(dow_order, fill_value=0).reset_index()
            dow.columns = ["Day", "Works"]
            
            dow_chart = alt.Chart(dow).mark_bar().encode(
                x=alt.X('Day:N', sort=dow_order, title=None),
                y=alt.Y('Works:Q', title="Works Read"),
                color=alt.Color('Works:Q', scale=alt.Scale(scheme='reds'), legend=None)
            ).properties(height=300)
            
            st.altair_chart(dow_chart, width='stretch')

        #cumulative word counter
        with st.container(border=True):
            st.subheader("Your reading journey over time")
            
            timeline_df = fdf.copy()
            timeline_df['last_visited'] = pd.to_datetime(timeline_df['last_visited'])
            timeline_df = timeline_df.dropna(subset=['last_visited', 'word_count'])
            
            if not timeline_df.empty:
                words_per_day = timeline_df.groupby(timeline_df['last_visited'].dt.date)['word_count'].sum().reset_index()
                words_per_day = words_per_day.sort_values('last_visited')

                words_per_day['Total Words Read'] = words_per_day['word_count'].cumsum()                
                words_per_day = words_per_day.rename(columns={'last_visited': 'Date'})
                
                st.line_chart(
                    words_per_day, 
                    x='Date', 
                    y='Total Words Read',
                    color='#8c2d19'
                )
            else:
                st.info("No timeline data available for the selected dates.")
    
    # BOOKMARKS
    with tab_bookmarks:
        fdf = st.session_state.filtered_df
        bdf = fdf[fdf.get('bookmarked') == True] if 'bookmarked' in fdf.columns else pd.DataFrame()

        if fdf.empty:
            st.info("No reading history available.")
        elif bdf.empty:
            st.info("No bookmarks found.")
        else:
            st.markdown("### Bookmarks Deep-Dive")
            st.caption("Contrasting your everyday reading history against your favorite.")
            
            # DIFFERENTIAL METRICS 
            with st.container(border=True):
                st.subheader("Key Differences")
                m1, m2, m3 = st.columns(3)
                
                # Word Count Delta
                avg_words_all = int(fdf['word_count'].mean()) if len(fdf) > 0 else 0
                avg_words_bkmk = int(bdf['word_count'].mean()) if len(bdf) > 0 else 0
                word_delta = avg_words_bkmk - avg_words_all
                
                unique_fandoms_bkmk = bdf["fandom"].explode().nunique()

                m1.metric("Number of bookmarks", f"{len(bdf)}")
                m2.metric("Avg. Bookmarked Length", f"{avg_words_bkmk:,}", f"{word_delta:,} vs history")
                m3.metric("Fandoms Bookmarked", f"{unique_fandoms_bkmk:,}")

            # ── WORD COUNT DENSITY (Overlapping Waves) ──
            with st.container(border=True):
                st.subheader("Story Length Breakdown")
                
                bins = [0, 1000, 5000, 10000, 50000, 100000, float('inf')]
                labels = ["Under 1k", "1k - 5k", "5k - 10k", "10k - 50k", "50k - 100k", "100k+"]
                
                hist_bins = pd.cut(fdf['word_count'].fillna(0), bins=bins, labels=labels, include_lowest=True)
                hist_dist = hist_bins.value_counts(normalize=True).reindex(labels).reset_index()
                hist_dist.columns = ["Length Range", "Percentage"]
                hist_dist["Dataset"] = "Overall History"
                
                bkmk_bins = pd.cut(bdf['word_count'].fillna(0), bins=bins, labels=labels, include_lowest=True)
                bkmk_dist = bkmk_bins.value_counts(normalize=True).reindex(labels).reset_index()
                bkmk_dist.columns = ["Length Range", "Percentage"]
                bkmk_dist["Dataset"] = "Bookmarks"
                
                combined_len = pd.concat([hist_dist, bkmk_dist])
                
                length_chart = alt.Chart(combined_len).mark_area(opacity=0.6, interpolate='monotone').encode(
                    x=alt.X('Length Range:N', sort=labels, title="Word Count Range"),
                    y=alt.Y('Percentage:Q', axis=alt.Axis(format='%'), title="Share of Works"),
                    color=alt.Color('Dataset:N', 
                        scale=alt.Scale(domain=['Overall History', 'Bookmarks'], range=['#555555', '#8c2d19']),
                        legend=alt.Legend(orient='bottom', direction='horizontal', title=None)
                    )
                ).properties(height=300)
                
                st.altair_chart(length_chart, width='stretch')

            # RATING PREFERENCES (Grouped Bars)
            with st.container(border=True):
                st.subheader("Rating Preferences")
                
                rate_hist = fdf['rating'].value_counts(normalize=True).reset_index()
                rate_hist.columns = ["Rating", "Percentage"]
                rate_hist["Dataset"] = "Overall History"
                
                rate_bkmk = bdf['rating'].value_counts(normalize=True).reset_index()
                rate_bkmk.columns = ["Rating", "Percentage"]
                rate_bkmk["Dataset"] = "Bookmarks"
                
                combined_rate = pd.concat([rate_hist, rate_bkmk])
                
                rating_chart = alt.Chart(combined_rate).mark_bar().encode(
                    x=alt.X('Rating:N', title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y('Percentage:Q', axis=alt.Axis(format='%')),
                    color=alt.Color('Dataset:N', 
                        scale=alt.Scale(domain=['Overall History', 'Bookmarks'], range=['#555555', '#8c2d19']),
                        legend=alt.Legend(orient='bottom', direction='horizontal', title=None)
                    ),
                    xOffset='Dataset:N'
                ).properties(height=300)
                
                st.altair_chart(rating_chart, width='stretch')

            # ── TAG HYPER-FIXATIONS (Side-by-Side) ──────
            with st.container(border=True):
                st.subheader("Tag Priorities")
                
                def get_top_tags(df, n=10):
                    counts = Counter(t.strip() for cell in df["tags"] if isinstance(cell, list) for t in cell)
                    tag_df = pd.DataFrame(counts.most_common(n), columns=["Tag", "Count"])
                    tag_df["Proportion"] = tag_df["Count"] / len(df) * 100 if len(df) > 0 else 0
                    return tag_df
                    
                col_t1, col_t2 = st.columns(2)
                
                with col_t1:
                    st.caption("Most Frequent in History")
                    top_hist_tags = get_top_tags(fdf, 10)
                    st.dataframe(
                        top_hist_tags,
                        column_config={
                            "Tag": "AO3 Tag",
                            "Count": None,
                            "Proportion": st.column_config.ProgressColumn("Frequency", format="%.1f%%", min_value=0.0, max_value=top_hist_tags["Proportion"].max() if not top_hist_tags.empty else 1.0)
                        },
                        hide_index=True, width='stretch'
                    )
                    
                with col_t2:
                    st.caption("Most Frequent in Bookmarks")
                    top_bkmk_tags = get_top_tags(bdf, 10)
                    st.dataframe(
                        top_bkmk_tags,
                        column_config={
                            "Tag": "AO3 Tag",
                            "Count": None,
                            "Proportion": st.column_config.ProgressColumn("Frequency", format="%.1f%%", min_value=0.0, max_value=top_bkmk_tags["Proportion"].max() if not top_bkmk_tags.empty else 1.0)
                        },
                        hide_index=True, width='stretch'
                    )

            # CONVERSION MATRIX (Fandoms)
        with st.container(border=True):
            st.subheader("The fandoms you love")
            st.caption("Which fandoms you bookmark the most?")
            
            hist_fandoms = Counter(f.strip() for cell in fdf["fandom"] if isinstance(cell, list) for f in cell)
            bkmk_fandoms = Counter(f.strip() for cell in bdf["fandom"] if isinstance(cell, list) for f in cell)
            
            matrix_data = []
            for fandom, total_read in hist_fandoms.items():
                bookmarked = bkmk_fandoms.get(fandom, 0)
                
                if total_read >= 5 and bookmarked > 0:
                    rate = (bookmarked / total_read) * 100
                    matrix_data.append({
                        "Fandom": fandom, 
                        "Read": total_read, 
                        "Bookmarked": bookmarked, 
                        "Conversion": rate
                    })
            
            if matrix_data:
                matrix_df = pd.DataFrame(matrix_data).sort_values("Conversion", ascending=False)
                
                st.dataframe(
                    matrix_df,
                    column_config={
                        "Fandom": "Fandom",
                        "Read": "Total Read",
                        "Bookmarked": "Bookmarked",
                        "Conversion": st.column_config.NumberColumn("Conversion Rate", format="%.1f%%")
                    },
                    hide_index=True, width='stretch'
                )
            else:
                st.info("No fandoms match the criteria yet (requires at least 5 works read and at least 1 bookmark).")
    
    # DATA TABLE
    with tab_data:
        with st.container(border=True):
            st.subheader("Raw ledger data")
            st.caption(f"{len(fdf):,} works shown — use the sidebar to filter.")

            display_df = fdf.copy()
            for col in ["fandom", "ships", "tags", "orientations", "author"]:
                if col in display_df.columns:
                    display_df[col] = display_df[col].apply(
                        lambda x: ", ".join(x) if isinstance(x, list) else x
                    )

            st.dataframe(display_df, width='stretch', hide_index=True)

    # footer
    st.markdown("---")

    f_col1, spacer, f_col2 = st.columns(3)
    with f_col1:
        if st.button("← Back to Hub"):
            st.session_state.current_page = "intro"
            st.rerun()
    with f_col2:
        st.download_button(
            label="Download stats (JSON)", 
            data=st.session_state.df.to_json(),
            file_name=f"{st.session_state.username}_history_data.json", 
            mime="application/json",
            icon="📩",
            on_click="ignore",
            width='stretch'
        )