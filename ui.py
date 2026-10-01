import streamlit as st

NAV=[
    ("Dashboard","⌂"),
    ("Smart Sale","＋"),
    ("Inventory","▦"),
    ("Daily Operations","◉"),
    ("Ask Brain","✦"),
    ("Knowledge","◫"),
    ("Processes","▣"),
    ("Settings","⚙"),
]

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    :root{--bg:#f6f8fb;--panel:#ffffff;--panel2:#eef4ff;--line:#e4e9f0;--text:#202938;--muted:#6d7787;--accent:#3b82f6;--accent2:#2563eb;--good:#1f9d6a;--warn:#c98516;--danger:#d94b5b}
    html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif;color:var(--text)}
    .stApp{background:linear-gradient(180deg,#f9fbfd 0%,#f4f7fb 100%);color:var(--text)}
    [data-testid="stSidebar"]{background:#ffffff;border-right:1px solid var(--line)}
    [data-testid="stSidebar"]>div:first-child{padding:.8rem .7rem}
    .brand{padding:.5rem .65rem 1.05rem}.brand-name{font-size:1.15rem;font-weight:800;letter-spacing:-.04em;color:#1e293b}.brand-sub{color:#8993a3;font-size:.7rem;margin-top:.2rem}
    .nav-label{color:#98a1ae;font-size:.62rem;text-transform:uppercase;letter-spacing:.12em;padding:.7rem .65rem .35rem}
    .page-kicker{color:#7c8797;font-size:.65rem;text-transform:uppercase;letter-spacing:.12em;font-weight:700;margin-bottom:.25rem}
    h1{font-size:2.15rem!important;letter-spacing:-.055em!important;color:#202938!important}.subtitle{color:var(--muted);font-size:.92rem}
    .section-gap{height:.85rem}
    .hero{border:1px solid #dfe8f7;border-radius:22px;padding:1.3rem 1.4rem;background:linear-gradient(135deg,#edf5ff,#ffffff 72%);box-shadow:0 8px 28px rgba(42,66,100,.06)}
    .hero-title{font-size:1.55rem;font-weight:800;letter-spacing:-.04em;color:#1e3a5f}.hero-copy{color:#69778a;margin-top:.25rem}
    .stat{background:#fff;border:1px solid var(--line);border-radius:18px;padding:1rem 1.05rem;min-height:104px;box-shadow:0 4px 18px rgba(42,66,100,.045)}.stat-label{color:#748093;font-size:.72rem}.stat-value{font-size:1.55rem;font-weight:800;margin:.2rem 0;color:#202938}.stat-sub{color:#9aa3b1;font-size:.68rem}
    .action-card{min-height:130px;border:1px solid var(--line);background:#fff;border-radius:18px;padding:1rem;box-shadow:0 5px 20px rgba(42,66,100,.045)}.action-icon{width:36px;height:36px;border-radius:11px;background:#edf5ff;color:#2563eb;display:flex;align-items:center;justify-content:center;font-weight:800;margin-bottom:.75rem}.action-title{font-weight:750;color:#243044}.action-desc{color:#788394;font-size:.75rem;line-height:1.45;margin-top:.25rem}
    .premium-card{border:1px solid var(--line);background:#fff;border-radius:19px;padding:1.05rem 1.15rem;box-shadow:0 5px 20px rgba(42,66,100,.045)}.eyebrow{color:#7c8797;font-size:.64rem;text-transform:uppercase;letter-spacing:.12em;font-weight:700}.big-number{font-size:2rem;font-weight:800;letter-spacing:-.04em;color:#1f3d63}.muted{color:#778293;font-size:.78rem}.tiny{color:#9aa3b1;font-size:.66rem}
    .status-pill{display:inline-block;border:1px solid #dce3ec;background:#f8fafc;border-radius:999px;padding:.18rem .52rem;font-size:.64rem;color:#657084}.glow{color:#2563eb}
    .stButton>button{border-radius:11px!important;border:1px solid #dbe2eb!important;background:#fff!important;color:#263244!important;font-weight:600;min-height:2.35rem}.stButton>button:hover{border-color:#a9c6ef!important;background:#f7fbff!important}.stButton>button[kind="primary"]{background:#3b82f6!important;border:0!important;color:#fff!important;box-shadow:0 7px 18px rgba(59,130,246,.18)}
    .stTextInput input,.stTextArea textarea,.stNumberInput input{background:#fff!important;border:1px solid #dce3eb!important;color:#202938!important;border-radius:11px!important}.stSelectbox>div>div{background:#fff!important;border-color:#dce3eb!important}.stFileUploader{background:#fff;border:1px dashed #cbd5e1;border-radius:15px;padding:.2rem}
    [data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:16px;padding:.7rem}.info-banner{background:#f5f9ff;border:1px solid #dbe8fb;border-radius:15px;padding:.85rem 1rem;color:#5f6f83}
    /* Light, readable Streamlit messages and form labels */
    [data-testid="stAlert"]{background:#ffffff!important;border:1px solid #dbe3ee!important;border-radius:12px!important;color:#253247!important;box-shadow:0 3px 12px rgba(42,66,100,.04)!important}
    [data-testid="stAlert"] p,[data-testid="stAlert"] div,[data-testid="stAlert"] span{color:#253247!important}
    [data-testid="stAlert"] svg{color:#64748b!important}
    [data-testid="stAlert"] [data-testid="stMarkdownContainer"]{color:#253247!important}
    [data-testid="stAlert"][kind="warning"]{background:#fffaf0!important;border-color:#f2d38b!important}
    [data-testid="stAlert"][kind="error"]{background:#fff5f6!important;border-color:#f0c4ca!important}
    [data-testid="stAlert"][kind="success"]{background:#f2fbf7!important;border-color:#bfe6d3!important}
    [data-testid="stAlert"][kind="info"]{background:#f4f8ff!important;border-color:#cfe0fb!important}
    label,[data-testid="stWidgetLabel"] p,[data-testid="stWidgetLabel"] div{color:#344054!important;font-weight:600!important}
    .stNumberInput label,.stTextInput label,.stTextArea label,.stSelectbox label{color:#344054!important}
    .stPopover [data-testid="stPopover"]{background:#fff!important}
    [data-testid="stExpander"]{background:#fff!important;border:1px solid #e1e7ef!important;border-radius:14px!important}
    .inventory-card{background:#fff;border:1px solid var(--line);border-radius:17px;padding:1rem 1.05rem;margin:.55rem 0;box-shadow:0 4px 16px rgba(42,66,100,.04)}
    .inventory-title{font-size:1rem;font-weight:750;color:#202938}.inventory-meta{color:#6d7787;font-size:.76rem;margin-top:.2rem}.inventory-label{color:#667085;font-size:.68rem;text-transform:uppercase;letter-spacing:.08em;font-weight:700;margin-bottom:.18rem}
    .stock-good{color:#18794e;font-weight:700}.stock-low{color:#9a6700;font-weight:700}.stock-out{color:#b42318;font-weight:700}.price-missing{color:#b54708;font-weight:700}
    .activity-row{display:flex;gap:.7rem;padding:.7rem 0;border-bottom:1px solid #edf0f4}.activity-dot{width:7px;height:7px;border-radius:50%;background:#3b82f6;margin-top:.42rem;flex:0 0 auto}
    .footer{text-align:center;color:#a0a8b4;font-size:.64rem;padding:2rem 0 1rem}
    </style>
    """,unsafe_allow_html=True)

def sidebar(business):
    with st.sidebar:
        st.markdown(f"<div class='brand'><div class='brand-name'>◈ Business Brain</div><div class='brand-sub'>{business['name']}</div></div>",unsafe_allow_html=True)
        st.markdown("<div class='nav-label'>Menu</div>",unsafe_allow_html=True)
        for label,icon in NAV:
            active=st.session_state.page==label
            if st.button(f"{icon}  {label}",key=f"nav_{label}",use_container_width=True,type="primary" if active else "secondary"):
                st.session_state.page=label; st.rerun()
        st.markdown("<div style='height:.8rem'></div>",unsafe_allow_html=True)
        st.markdown("<div class='info-banner' style='font-size:.68rem'><b>Simple mode</b><br>Just tell Business Brain what you need. The agents handle the background work.</div>",unsafe_allow_html=True)

def page_header(title,subtitle,kicker="Business Brain"):
    st.markdown(f"<div class='page-kicker'>{kicker}</div>",unsafe_allow_html=True); st.title(title); st.markdown(f"<div class='subtitle'>{subtitle}</div>"); st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True)

def stat_card(label,value,sub):
    st.markdown(f"<div class='stat'><div class='stat-label'>{label}</div><div class='stat-value'>{value}</div><div class='stat-sub'>{sub}</div></div>",unsafe_allow_html=True)

def empty_state(title,description):
    st.markdown(f"<div style='text-align:center;padding:2.4rem 1rem;border:1px dashed #ccd5e1;border-radius:16px;background:#fff'><div style='font-weight:700;color:#263244'>{title}</div><div class='muted' style='margin-top:.3rem'>{description}</div></div>",unsafe_allow_html=True)

def source_card(source):
    st.markdown(f"<div class='premium-card'><b>{source['title']}</b> <span class='tiny'>· {source['type']} · {source.get('score',0):.2f}</span><div class='muted' style='margin-top:.3rem'>{source.get('content','')}</div></div>",unsafe_allow_html=True)
