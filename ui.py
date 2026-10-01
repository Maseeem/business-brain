import streamlit as st

NAV = [
    ("Dashboard", "⌂"),
    ("Smart Sale", "＋"),
    ("Daily Operations", "◉"),
    ("Ask Brain", "✦"),
    ("Processes", "▣"),
    ("Knowledge", "◫"),
    ("Record Process", "↗"),
    ("Activity", "◷"),
    ("Settings", "⚙"),
]


def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    :root{--bg:#080b12;--panel:#101521;--panel2:#141a28;--line:#20283a;--text:#f4f7fb;--muted:#8994a8;--accent:#5b8cff;--cyan:#45d8ff;--good:#38d39f;--warn:#ffbd5a;--danger:#ff6b7a}
    html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif}
    .stApp{background:radial-gradient(circle at 80% -10%,rgba(69,216,255,.09),transparent 28%),radial-gradient(circle at 10% 0%,rgba(91,140,255,.12),transparent 25%),var(--bg);color:var(--text)}
    [data-testid="stSidebar"]{background:rgba(9,12,19,.94);border-right:1px solid var(--line)}
    [data-testid="stSidebar"]>div:first-child{padding:.9rem .75rem}
    .brand{padding:.5rem .7rem 1.1rem}.brand-name{font-size:1.12rem;font-weight:800;letter-spacing:-.035em}.brand-sub{color:var(--muted);font-size:.7rem;margin-top:.18rem}
    .nav-label{color:#66738a;font-size:.62rem;text-transform:uppercase;letter-spacing:.13em;padding:.7rem .7rem .35rem}
    .page-kicker{color:#71819d;font-size:.65rem;text-transform:uppercase;letter-spacing:.13em;font-weight:700;margin-bottom:.25rem}
    h1{font-size:2.25rem!important;letter-spacing:-.055em!important}.subtitle{color:var(--muted);font-size:.9rem}
    .section-gap{height:.8rem}
    .hero{border:1px solid var(--line);border-radius:24px;padding:1.35rem 1.45rem;background:linear-gradient(135deg,rgba(91,140,255,.13),rgba(69,216,255,.04) 55%,rgba(255,255,255,.015));box-shadow:0 18px 55px rgba(0,0,0,.18)}
    .hero-title{font-size:1.65rem;font-weight:800;letter-spacing:-.04em}.hero-copy{color:var(--muted);margin-top:.25rem}
    .stat{background:rgba(16,21,33,.88);border:1px solid var(--line);border-radius:18px;padding:1rem 1.05rem;min-height:105px}.stat-label{color:var(--muted);font-size:.72rem}.stat-value{font-size:1.55rem;font-weight:800;margin:.2rem 0}.stat-sub{color:#657188;font-size:.68rem}
    .action-card{min-height:145px;border:1px solid var(--line);background:linear-gradient(145deg,#111725,#0d121d);border-radius:18px;padding:1rem;box-shadow:0 12px 35px rgba(0,0,0,.12)}.action-icon{width:36px;height:36px;border-radius:11px;background:rgba(91,140,255,.13);color:#72a0ff;display:flex;align-items:center;justify-content:center;font-weight:800;margin-bottom:.8rem}.action-title{font-weight:750}.action-desc{color:var(--muted);font-size:.75rem;line-height:1.45;margin-top:.25rem}
    .premium-card{border:1px solid var(--line);background:rgba(16,21,33,.82);border-radius:20px;padding:1.05rem 1.15rem}.eyebrow{color:#71819d;font-size:.64rem;text-transform:uppercase;letter-spacing:.12em;font-weight:700}.big-number{font-size:2rem;font-weight:800;letter-spacing:-.04em}.muted{color:var(--muted);font-size:.78rem}.tiny{color:#647087;font-size:.66rem}
    .status-pill{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:.18rem .52rem;font-size:.64rem;color:#b6c0d0}.glow{color:#73a1ff}
    .stButton>button{border-radius:11px!important;border:1px solid var(--line)!important;background:#111725!important;color:#eaf0f8!important;font-weight:600}.stButton>button:hover{border-color:#3e5d91!important;background:#151d2d!important}.stButton>button[kind="primary"]{background:linear-gradient(135deg,#4e7ff7,#5f9eff)!important;border:0!important;color:white!important;box-shadow:0 8px 24px rgba(76,126,247,.24)}
    .stTextInput input,.stTextArea textarea,.stNumberInput input{background:#0d121d!important;border:1px solid var(--line)!important;color:var(--text)!important;border-radius:11px!important}.stFileUploader{background:#0d121d;border:1px dashed #2a3550;border-radius:16px;padding:.2rem}
    [data-testid="stMetric"]{background:#101521;border:1px solid var(--line);border-radius:16px;padding:.7rem}.info-banner{background:#101827;border:1px solid #263552;border-radius:15px;padding:.85rem 1rem;color:#aebbd0}
    .activity-row{display:flex;gap:.7rem;padding:.7rem 0;border-bottom:1px solid #192131}.activity-dot{width:7px;height:7px;border-radius:50%;background:#5f8fff;margin-top:.42rem;flex:0 0 auto}
    .footer{text-align:center;color:#536077;font-size:.64rem;padding:2rem 0 1rem}
    </style>
    """, unsafe_allow_html=True)


def sidebar(business):
    with st.sidebar:
        st.markdown(f"<div class='brand'><div class='brand-name'>◈ Business Brain</div><div class='brand-sub'>{business['name']}</div></div>", unsafe_allow_html=True)
        st.markdown("<div class='nav-label'>Workspace</div>", unsafe_allow_html=True)
        for label, icon in NAV:
            active=st.session_state.page==label
            if st.button(f"{icon}  {label}",key=f"nav_{label}",use_container_width=True,type="primary" if active else "secondary"):
                st.session_state.page=label; st.rerun()
        st.markdown("<div style='height:.7rem'></div>",unsafe_allow_html=True)
        st.markdown("<div class='info-banner' style='font-size:.68rem'><b>AI operations mode</b><br>Sales, stock, supplier drafts and Business Brain work from the same business data.</div>",unsafe_allow_html=True)


def page_header(title, subtitle, kicker="Business Brain"):
    st.markdown(f"<div class='page-kicker'>{kicker}</div>",unsafe_allow_html=True); st.title(title); st.markdown(f"<div class='subtitle'>{subtitle}</div>",unsafe_allow_html=True); st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True)


def stat_card(label,value,sub):
    st.markdown(f"<div class='stat'><div class='stat-label'>{label}</div><div class='stat-value'>{value}</div><div class='stat-sub'>{sub}</div></div>",unsafe_allow_html=True)


def empty_state(title,description):
    st.markdown(f"<div style='text-align:center;padding:2.4rem 1rem;border:1px dashed #2b3549;border-radius:16px;background:#0d121d'><div style='font-weight:700'>{title}</div><div class='muted' style='margin-top:.3rem'>{description}</div></div>",unsafe_allow_html=True)


def source_card(source):
    st.markdown(f"<div class='premium-card'><b>{source['title']}</b> <span class='tiny'>· {source['type']} · {source.get('score',0):.2f}</span><div class='muted' style='margin-top:.3rem'>{source.get('content','')}</div></div>",unsafe_allow_html=True)
