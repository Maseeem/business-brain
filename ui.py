import streamlit as st

NAV = [
    ("Dashboard", "⌂"),
    ("Ask Brain", "✦"),
    ("Processes", "▣"),
    ("Knowledge", "◫"),
    ("Record Process", "＋"),
    ("Activity", "◷"),
    ("Settings", "⚙"),
]

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    :root { --ink:#172033; --muted:#687386; --line:#e7eaf0; --soft:#f7f8fa; --accent:#1f5eff; }
    * { font-family: Inter, system-ui, sans-serif; }
    .stApp { background:#fbfcfe; color:var(--ink); }
    [data-testid="stSidebar"] { background:#fff; border-right:1px solid var(--line); }
    [data-testid="stSidebar"] > div:first-child { padding:1.1rem .8rem; }
    .brand { padding:.35rem .65rem 1.2rem; }
    .brand-name { font-size:1.12rem; font-weight:700; letter-spacing:-.02em; }
    .brand-sub { color:var(--muted); font-size:.72rem; margin-top:.15rem; }
    .nav-label { color:#9aa3b2; font-size:.68rem; text-transform:uppercase; letter-spacing:.09em; padding:.7rem .65rem .35rem; }
    .page-kicker { color:#738097; font-size:.72rem; text-transform:uppercase; letter-spacing:.09em; margin-bottom:.35rem; font-weight:600; }
    h1 { letter-spacing:-.04em !important; font-size:2rem !important; }
    h2,h3 { letter-spacing:-.025em; }
    .subtitle { color:var(--muted); font-size:.92rem; }
    .stat { background:#fff; border:1px solid var(--line); border-radius:16px; padding:1rem 1.1rem; }
    .stat-label { color:var(--muted); font-size:.78rem; }
    .stat-value { font-size:1.65rem; font-weight:700; margin:.15rem 0; }
    .stat-sub { color:#9aa3b2; font-size:.72rem; }
    .action-card { min-height:140px; border:1px solid var(--line); background:#fff; border-radius:16px; padding:1rem; }
    .action-icon { width:34px; height:34px; border-radius:10px; background:#f0f4ff; color:var(--accent); display:flex; align-items:center; justify-content:center; font-weight:700; margin-bottom:.8rem; }
    .action-title { font-weight:650; margin-bottom:.25rem; }
    .action-desc { color:var(--muted); font-size:.78rem; line-height:1.45; }
    .info-banner { background:#f4f7ff; border:1px solid #dfe7ff; border-radius:14px; padding:1rem 1.1rem; color:#43506a; }
    .brain-hero { text-align:center; padding:2.3rem 1rem; border:1px solid var(--line); background:#fff; border-radius:20px; margin-bottom:1.2rem; }
    .brain-mark { margin:auto; width:48px; height:48px; border-radius:14px; display:flex; align-items:center; justify-content:center; background:#eef3ff; color:var(--accent); font-size:1.3rem; }
    .brain-hero p { color:var(--muted); max-width:620px; margin:auto; }
    .activity-row { display:flex; gap:.7rem; padding:.7rem 0; border-bottom:1px solid #f0f1f4; }
    .activity-dot { width:7px; height:7px; border-radius:50%; background:#7d8798; margin-top:.42rem; flex:0 0 auto; }
    .muted { color:var(--muted); font-size:.78rem; }
    .tiny { color:#a1a9b7; font-size:.68rem; margin-top:.15rem; }
    .section-gap { height:1rem; }
    .step-row { display:flex; gap:.8rem; padding:.8rem 0; border-bottom:1px solid #edf0f4; }
    .step-number { flex:0 0 auto; width:28px; height:28px; border-radius:8px; background:#f0f3f8; display:flex; align-items:center; justify-content:center; font-weight:650; font-size:.78rem; }
    .footer { text-align:center; color:#a4acb9; font-size:.68rem; padding:2.5rem 0 1rem; }
    .source-card { border:1px solid var(--line); background:#fff; border-radius:12px; padding:.7rem .8rem; margin:.45rem 0; }
    button[kind="primary"] { border-radius:10px !important; }
    .stButton > button { border-radius:10px; }
    [data-testid="stMetric"] { background:#fff; }
    </style>
    """, unsafe_allow_html=True)

def sidebar(business):
    with st.sidebar:
        st.markdown(f"""
        <div class='brand'>
          <div class='brand-name'>◈ Business Brain</div>
          <div class='brand-sub'>{business['name']}</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<div class='nav-label'>Workspace</div>", unsafe_allow_html=True)
        for label, icon in NAV:
            active = st.session_state.page == label
            if st.button(f"{icon}  {label}", key=f"nav_{label}", use_container_width=True, type="primary" if active else "secondary"):
                st.session_state.page = label
                st.rerun()
        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div class='info-banner' style='font-size:.72rem'>
        <b>Demo workspace</b><br>
        Nova Bakery data is included so you can demonstrate the full capture → retrieve loop.
        </div>
        """, unsafe_allow_html=True)

def page_header(title, subtitle, kicker="Business Brain"):
    st.markdown(f"<div class='page-kicker'>{kicker}</div>", unsafe_allow_html=True)
    st.title(title)
    st.markdown(f"<div class='subtitle'>{subtitle}</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)

def stat_card(label, value, sub):
    st.markdown(f"""
    <div class='stat'>
      <div class='stat-label'>{label}</div>
      <div class='stat-value'>{value}</div>
      <div class='stat-sub'>{sub}</div>
    </div>
    """, unsafe_allow_html=True)

def empty_state(title, description):
    st.markdown(f"""
    <div style='text-align:center;padding:2.4rem 1rem;border:1px dashed #dfe3ea;border-radius:16px;background:#fff'>
      <div style='font-weight:650'>{title}</div>
      <div class='muted' style='margin-top:.3rem'>{description}</div>
    </div>
    """, unsafe_allow_html=True)

def source_card(source):
    score = source.get("score", 0)
    st.markdown(f"""
    <div class='source-card'>
      <div><b>{source['title']}</b> <span class='tiny'>· {source['type']} · relevance {score:.2f}</span></div>
      <div class='muted' style='margin-top:.25rem'>{source.get('content','')}</div>
    </div>
    """, unsafe_allow_html=True)
