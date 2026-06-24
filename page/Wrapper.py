from collections import Counter
from datetime import datetime
import pandas as pd
import streamlit as st

def wrapper():
    df = st.session_state.df.copy()

    dates = pd.to_datetime(df["last_visited"]).dt.tz_localize(None)
    current_year = datetime.now().year
    dt_from = pd.to_datetime(f"{current_year}-01-01")
    fdf = df[dates >= dt_from].copy()

    if fdf.empty:
        st.info(f"Your ledger has no records for {current_year}. Please read some fics or sync your history!")
        return

    username = st.session_state.get("username", "Reader") or "Reader"

    # ── HEADER ────────────────────────────────────────────────────────────────

    st.markdown(f'<div class="archive-sub">AO3 Stats // {current_year} in Review</div>', unsafe_allow_html=True)
    st.title(f"The {current_year} Ledger")
    st.markdown(
        '<p class="serif-body">A record of your reading history on the Archive this year — '
        "your top fandoms, your favorite authors, and your milestones. Turn the pages below.</p>"
        '<div class="flourish">𓆝 𓆟 𓆞 𓆝 𓆟</div>',
        unsafe_allow_html=True,
    )

    # ── STATS ─────────────────────────────────────────────────────────────────

    if "word_count" in fdf.columns:
        def assign_bucket(wc):
            if pd.isna(wc) or wc < 10_000:  return "Short"
            if wc < 50_000:                 return "Medium"
            if wc < 100_000:                return "Long"
            return "Epic"

        fdf["bucket"] = fdf["word_count"].apply(assign_bucket)
        try:
            word_heavyweight = fdf.groupby("bucket")["word_count"].sum().idxmax()
        except ValueError:
            word_heavyweight = "Short"
    else:
        word_heavyweight = "Short"

    length_title = {
        "Epic":   "Reader of Epics",
        "Long":   "Reader of Long Stories",
        "Medium": "Reader of Mid-Length Stories",
    }.get(word_heavyweight, "Reader of Short Stories")

    top_rating = (
        fdf["rating"].mode()[0]
        if "rating" in fdf.columns and not fdf["rating"].mode().empty
        else "Unknown"
    )
    rating_title = {
        "Explicit":              "Reader of Explicit Fiction",
        "Mature":                "Reader of Mature Fiction",
        "Teen And Up Audiences": "Reader of Teen Fiction",
    }.get(top_rating, "Reader of General Fiction")

    median_words = fdf["word_count"].median() if "word_count" in fdf.columns else 0
    total_words  = int(fdf["word_count"].sum()) if "word_count" in fdf.columns else 0
    total_works  = len(fdf)

    ASOIAF_SERIES = 1_770_000
    ASOIAF_BOOK   = 354_000
    HOBBIT        = 95_000
    asoiaf_series = round(total_words / ASOIAF_SERIES, 2)
    asoiaf_books  = round(total_words / ASOIAF_BOOK, 1)
    hobbit_equiv  = round(total_words / HOBBIT, 1)

    if asoiaf_series >= 1:
        volume_main  = f"{asoiaf_series}×"
        volume_unit  = "the entire ASOIAF series"
        volume_extra = f"That's {asoiaf_books} individual ASOIAF volumes, or {hobbit_equiv} copies of <em>The Hobbit</em>."
    else:
        volume_main  = f"{asoiaf_books}×"
        volume_unit  = "an ASOIAF volume"
        volume_extra = f"Or {hobbit_equiv} copies of <em>The Hobbit</em> — you'll get there."

    all_authors = [a.strip() for cell in fdf["author"] if isinstance(cell, list) for a in cell]
    top_author, top_author_count = (
        Counter(all_authors).most_common(1)[0] if all_authors else ("Anonymous", 0)
    )

    all_ships = [
        s.strip()
        for cell in fdf["ships"] if isinstance(cell, list)
        for s in cell if "/" in s or "&" in s
    ]
    top_ship = Counter(all_ships).most_common(1)[0][0] if all_ships else "No primary ship"

    all_fandoms = [f.strip() for cell in fdf["fandom"] if isinstance(cell, list) for f in cell]
    top_fandom_overall = Counter(all_fandoms).most_common(1)[0][0] if all_fandoms else "Varied Lore"

    # ── MIGRATION / DEVOTION ──────────────────────────────────────────────────

    temp = fdf.copy()
    temp["month"] = pd.to_datetime(temp["last_visited"]).dt.to_period("M")
    timeline_raw = []
    for month, group in temp.groupby("month"):
        fandoms = [f.strip() for cell in group["fandom"] if isinstance(cell, list) for f in cell]
        if fandoms:
            timeline_raw.append((month.strftime("%B"), Counter(fandoms).most_common(1)[0][0]))

    migration = []
    for entry in timeline_raw:
        if not migration or migration[-1][1] != entry[1]:
            migration.append(entry)

    unique_fandoms = list(dict.fromkeys(f for _, f in migration))
    single_fandom_mode = len(unique_fandoms) <= 1

    if single_fandom_mode:
        devotion_fandom = unique_fandoms[0] if unique_fandoms else top_fandom_overall
        devotion_count  = sum(
            1 for cell in fdf["fandom"]
            if isinstance(cell, list) and devotion_fandom in [f.strip() for f in cell]
        )
        page4_html = f"""
  <div class="page-label mono-label mb-md">A Singular Focus</div>
  <div class="ruled-top"></div>
  <div class="text-center my-lg">
    <div class="mono-label mb-md">A loyal reader</div>
    <div class="title-lg text-italic text-accent mb-md">{devotion_fandom}</div>
    <div class="text-muted text-italic">
      You stayed put. {devotion_count} work{"s" if devotion_count != 1 else ""},
      one main fandom; an impressive level of dedication!
    </div>
  </div>
  <div class="ruled-bottom"></div>"""
    else:
        migration_rows_html = "".join(
            f'<div class="flex-list">'
            f'<span class="mono-label" style="min-width: 82px;">{month}</span>'
            f'<span class="text-md text-italic">{fandom}</span>'
            f'</div>'
            for month, fandom in migration[-7:]
        )
        page4_html = f"""
  <div class="page-label mono-label">Fandom Timeline</div>
  <div class="ruled-top"></div>
  <div class="text-muted text-italic text-center my-md">The fandoms that defined your year, month by month</div>
  <div class="w-full max-w-sm mb-lg">{migration_rows_html}</div>
  <div class="ruled-bottom"></div>"""

    # Dialed down frame height slightly since internal buttons are removed
    extra_rows   = 0 if single_fandom_mode else max(0, len(migration) - 4)
    frame_height = 610 + extra_rows * 40

    theme = st.context.theme.type
    with open(f"styles/{theme}.css", "r") as f:
        css = f.read()

    # ── HTML ──────────────────────────────────────────────────────────────────

    html_content = f"""
<style>
{css}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: transparent;
    font-family: 'EB Garamond', Georgia, serif;
    color: var(--text);
    padding: 0 0 12px;
    font-size: 18px;
}}

/* -- TYPOGRAPHY & UTILITIES -- */
.mono-label {{ font-family: 'Courier Prime', monospace; font-size: 13px; letter-spacing: 2px; text-transform: uppercase; color: var(--muted); }}
.text-italic {{ font-style: italic; }}
.text-muted {{ color: var(--muted); }}
.text-accent {{ color: var(--accent-lt); font-weight: 600; }}
.text-accent-dark {{ color: var(--accent); font-weight: 600; }}
.text-center {{ text-align: center; }}
.text-sm {{ font-size: clamp(14px, 2.5vw, 17px); }}
.text-md {{ font-size: clamp(15px, 2.8vw, 19px); line-height: 1.7; }}
.title-md {{ font-size: clamp(18px, 3.5vw, 24px); line-height: 1.3; font-weight: 600; }}
.title-lg {{ font-size: clamp(22px, 4.5vw, 32px); line-height: 1.2; }}
.title-xl {{ font-size: clamp(68px, 15vw, 110px); line-height: 1; color: var(--accent); }}

/* -- SPACING & SIZING -- */
.w-full {{ width: 100%; }}
.max-w-sm {{ max-width: 480px; }}
.mb-sm {{ margin-bottom: 8px; }}
.mb-md {{ margin-bottom: 16px; }}
.mb-lg {{ margin-bottom: 24px; }}
.my-sm {{ margin: 12px 0; }}
.my-md {{ margin: 18px 0; }}
.my-lg {{ margin: 28px 0; }}

/* -- LAYOUT COMPONENTS -- */
.page-counter {{ text-align: center; margin-bottom: 24px; padding-top: 4px; }}
.page {{ display: none; flex-direction: column; align-items: center; animation: fadeUp 0.45s ease forwards; }}
.page.active {{ display: flex; }}
@keyframes fadeUp {{ from {{ opacity:0; transform:translateY(12px); }} to {{ opacity:1; transform:translateY(0); }} }}

.ruled-top {{ width:100%; border-top:3px solid var(--border); margin:0 0 8px; }}
.ruled-top::after {{ content:''; display:block; border-top:1.5px solid var(--border-lt); margin-top:7px; }}
.ruled-bottom {{ width:100%; border-top:1.5px solid var(--border-lt); margin:8px 0 0; }}
.ruled-bottom::after {{ content:''; display:block; border-top:3px solid var(--border); margin-top:7px; }}
.divider {{ border: none; border-top: 1px solid var(--border); margin: 12px auto; width: 60%; }}

.ornament {{ font-size:20px; color:var(--accent-lt); text-align:center; margin:12px 0; letter-spacing:10px; opacity:0.85; }}
.ornament.gap {{ margin-top:22px; }}

.card {{ border: 1.5px solid var(--border); padding: 32px; max-width: 460px; width: 100%; text-align: center; position: relative; }}
.card-bookplate::before, .card-bookplate::after {{ content:'✦'; position:absolute; font-size:14px; color:var(--accent-lt); opacity:0.75; }}
.card-bookplate::before {{ top:12px; left:16px; }}
.card-bookplate::after  {{ bottom:12px; right:16px; }}
.card-transcript::before {{ content:''; position:absolute; inset:7px; border:1px solid var(--border-lt); pointer-events:none; }}

.flex-between {{ display: flex; justify-content: space-between; align-items: baseline; gap: 14px; padding: 9px 0; }}
.flex-list {{ display: flex; gap: 20px; align-items: baseline; padding: 12px 0; border-bottom: 1px solid var(--border-lt); }}
.flex-list:last-child {{ border-bottom: none; }}

/* -- NAV -- */
.nav-row {{ display:flex; align-items:center; gap:20px; margin-top:28px; justify-content:center; }}
.nav-btn  {{
    background: transparent; border: 1.5px solid var(--border); color: var(--text);
    font-family: 'Courier Prime', monospace; text-transform: uppercase;
    font-size: 13px; letter-spacing: 1px; padding: 9px 24px;
    cursor: pointer; border-radius: 2px; transition: all 0.15s ease;
}}
.nav-btn:hover:not(:disabled) {{ background: var(--bg2); border-color: var(--muted); }}
.nav-btn:disabled {{ opacity: 0.2; cursor: default; }}
.nav-dots {{ display: flex; gap: 7px; align-items: center; }}
.dot {{ width:6px; height:6px; border-radius:50%; background:var(--border); transition:background 0.2s; }}
.dot.active {{ background: var(--muted); }}
</style>

<body>

<div class="page-counter mono-label" id="counter">Page I of V</div>

<div class="page active" id="p0">
  <div class="page-label mono-label mb-md">Library</div>
  <div class="ruled-top"></div>
  <div class="ornament">✦ &nbsp; ✦ &nbsp; ✦</div>
  <div class="card card-bookplate my-md">
    <div class="mono-label mb-sm">Reading Ledger of</div>
    <div class="title-lg text-italic mb-md">{username}</div>
    <hr class="divider">
    <div class="title-md text-accent-dark mt-md">{length_title}</div>
    <div class="text-md text-muted text-italic">& {rating_title}</div>
    <div class="text-md text-muted text-italic my-md">
      Typical length: {int(median_words):,} words &nbsp;·&nbsp; Most-read rating: {top_rating}
    </div>
  </div>
  <div class="ornament">✦ &nbsp; ✦ &nbsp; ✦</div>
  <div class="ruled-bottom"></div>
</div>

<div class="page" id="p1">
  <div class="page-label mono-label mb-md">The Volume</div>
  <div class="ruled-top"></div>
  <div class="title-xl my-md">{volume_main}</div>
  <div class="title-md text-italic mb-md">{volume_unit}</div>
  <div class="text-md text-muted text-italic max-w-sm text-center my-sm">{volume_extra}</div>
  <div class="ornament gap">— &nbsp; · &nbsp; —</div>
  <div class="mono-label my-md">{total_words:,} words &nbsp;·&nbsp; {total_works} works &nbsp;·&nbsp; {current_year}</div>
  <div class="ruled-bottom gap"></div>
</div>

<div class="page" id="p2">
  <div class="page-label mono-label mb-md">Author Spotlight</div>
  <div class="ruled-top"></div>
  <div class="ornament gap">✦</div>
  <div class="max-w-sm w-full text-center my-md">
    <div class="mono-label mb-md">Author Spotlight</div>
    <div class="text-md text-muted text-italic my-sm">The writer who captivated your attention and held your reading focus more than any other this year</div>
    <div class="title-lg text-accent my-sm">{top_author}</div>
    <div class="mono-label my-sm">{top_author_count} work{"s" if top_author_count != 1 else ""} read this year</div>
    <div class="ornament gap">— &nbsp; · &nbsp; —</div>
    <div class="mono-label">Send them some flowers, they deserve it.</div>
  </div>
  <div class="ornament">✦</div>
  <div class="ruled-bottom"></div>
</div>

<div class="page" id="p3">
  {page4_html}
</div>

<div class="page" id="p4">
  <div class="page-label mono-label mb-md">Year in Review</div>
  <div class="ruled-top"></div>
  <div class="card card-transcript my-md max-w-sm">
    <div class="mono-label mb-sm">Reading Ledger &nbsp;·&nbsp; {current_year}</div>
    <div class="title-lg text-italic mb-lg">{username}</div>
    <hr class="divider w-full mb-md">
    <div class="flex-between"><span class="mono-label">Works consumed</span><span class="text-sm text-italic">{total_works:,}</span></div>
    <div class="flex-between"><span class="mono-label">Words read</span><span class="text-sm text-italic">{total_words:,}</span></div>
    <div class="flex-between"><span class="mono-label">Primary realm</span><span class="text-sm text-italic">{top_fandom_overall}</span></div>
    <div class="flex-between"><span class="mono-label">Dearest companions</span><span class="text-sm text-italic">{top_ship}</span></div>
    <div class="flex-between"><span class="mono-label">Patron of</span><span class="text-sm text-italic">{top_author}</span></div>
    <hr class="divider w-full my-md">
    <div class="mono-label" style="opacity:0.7;">Stamped by the AO3 Ledger &nbsp;·&nbsp; {current_year}</div>
  </div>
  <div class="ruled-bottom gap"></div>
</div>

<div class="nav-row">
  <button class="nav-btn" id="prev" onclick="turn(-1)" disabled>&#8592; prev</button>
  <div class="nav-dots" id="dots"></div>
  <button class="nav-btn" id="next" onclick="turn(1)">next &#8594;</button>
</div>

<script>
  const pages      = document.querySelectorAll('.page');
  const total      = pages.length;
  const romans     = ['I','II','III','IV','V'];
  let cur = 0;

  const dotsEl = document.getElementById('dots');
  for (let i = 0; i < total; i++) {{
    const d = document.createElement('div');
    d.className = 'dot' + (i === 0 ? ' active' : '');
    dotsEl.appendChild(d);
  }}

  function turn(dir) {{
    pages[cur].classList.remove('active');
    dotsEl.children[cur].classList.remove('active');
    cur = Math.max(0, Math.min(total - 1, cur + dir));
    pages[cur].classList.add('active');
    dotsEl.children[cur].classList.add('active');
    document.getElementById('counter').textContent = 'Page ' + romans[cur] + ' of ' + romans[total - 1];
    document.getElementById('prev').disabled = cur === 0;
    document.getElementById('next').disabled = cur === total - 1;
  }}

  document.addEventListener('keydown', (e) => {{
    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') turn(1);
    if (e.key === 'ArrowLeft'  || e.key === 'ArrowUp')   turn(-1);
  }});
</script>
</body>"""

    st.iframe(html_content, height=frame_height)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("View Full Stats →", use_container_width=True):
        st.session_state.current_page = "stats"
        st.rerun()