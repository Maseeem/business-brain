import streamlit as st

NAV=[
    ("Dashboard","⌂"),
    ("Smart Sale","＋"),
    ("Inventory","▦"),
    ("Receipts","🧾"),
    ("Daily Operations","◉"),
    ("Ask Brain","✦"),
    ("Knowledge","◫"),
    ("Processes","▣"),
    ("Record Process","＋"),
    ("Activity","•"),
    ("Suppliers","⇄"),
    ("Settings","⚙"),
    ("WhatsApp","📱"),
]

def inject_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    :root{--bg:#f7faf8;--panel:#ffffff;--panel2:#eef9f2;--line:#dfe9e3;--text:#25312a;--muted:#66736b;--accent:#198754;--accent2:#157347;--good:#198754;--warn:#9a6700;--danger:#c0394b}
    html,body,[class*="css"]{font-family:Inter,system-ui,sans-serif;color:var(--text)}
    .stApp{background:linear-gradient(180deg,#fbfdfc 0%,#f4f8f5 100%);color:var(--text)}
    [data-testid="stSidebar"]{background:#ffffff;border-right:1px solid var(--line)}
    [data-testid="stSidebar"]>div:first-child{padding:.8rem .7rem}
    .brand{padding:.5rem .65rem 1.05rem}.brand-name{font-size:1.15rem;font-weight:800;letter-spacing:-.04em;color:#155c3b}.brand-sub{color:#8993a3;font-size:.7rem;margin-top:.2rem}
    .nav-label{color:#98a1ae;font-size:.62rem;text-transform:uppercase;letter-spacing:.12em;padding:.7rem .65rem .35rem}
    .page-kicker{color:#7c8797;font-size:.65rem;text-transform:uppercase;letter-spacing:.12em;font-weight:700;margin-bottom:.25rem}
    h1{font-size:2.15rem!important;letter-spacing:-.055em!important;color:#243b31!important}.subtitle{color:#5f7067;font-size:.92rem;font-weight:500}
    .section-gap{height:.85rem}
    .hero{border:1px solid #cfe5d7;border-radius:22px;padding:1.3rem 1.4rem;background:linear-gradient(135deg,#edf9f1,#ffffff 72%);box-shadow:0 8px 28px rgba(42,66,100,.06)}
    .hero-title{font-size:1.55rem;font-weight:800;letter-spacing:-.04em;color:#155c3b}.hero-copy{color:#69778a;margin-top:.25rem}
    .stat{background:#fff;border:1px solid var(--line);border-radius:18px;padding:1rem 1.05rem;min-height:104px;box-shadow:0 4px 18px rgba(42,66,100,.045)}.stat-label{color:#748093;font-size:.72rem}.stat-value{font-size:1.55rem;font-weight:800;margin:.2rem 0;color:#202938}.stat-sub{color:#9aa3b1;font-size:.68rem}
    .action-card{min-height:130px;border:1px solid var(--line);background:#fff;border-radius:18px;padding:1rem;box-shadow:0 5px 20px rgba(42,66,100,.045)}.action-icon{width:36px;height:36px;border-radius:11px;background:#eaf7ef;color:#198754;display:flex;align-items:center;justify-content:center;font-weight:800;margin-bottom:.75rem}.action-title{font-weight:750;color:#243044}.action-desc{color:#788394;font-size:.75rem;line-height:1.45;margin-top:.25rem}
    .premium-card{border:1px solid var(--line);background:#fff;border-radius:19px;padding:1.05rem 1.15rem;box-shadow:0 5px 20px rgba(42,66,100,.045)}.eyebrow{color:#7c8797;font-size:.64rem;text-transform:uppercase;letter-spacing:.12em;font-weight:700}.big-number{font-size:2rem;font-weight:800;letter-spacing:-.04em;color:#1f3d63}.muted{color:#778293;font-size:.78rem}.tiny{color:#9aa3b1;font-size:.66rem}
    .status-pill{display:inline-block;border:1px solid #dce3ec;background:#f8fafc;border-radius:999px;padding:.18rem .52rem;font-size:.64rem;color:#657084}.glow{color:#198754}
    .stButton>button{border-radius:11px!important;border:1px solid #dbe2eb!important;background:#fff!important;color:#263244!important;font-weight:600;min-height:2.35rem}.stButton>button:hover{border-color:#a9c6ef!important;background:#f3fbf6!important}.stButton>button[kind="primary"]{background:#198754!important;border:0!important;color:#fff!important;box-shadow:0 7px 18px rgba(25,135,84,.18)}
    .stTextInput input,.stTextArea textarea,.stNumberInput input{background:#fff!important;border:1px solid #dce3eb!important;color:#202938!important;border-radius:11px!important}.stSelectbox>div>div{background:#fff!important;border-color:#dce3eb!important}.stFileUploader{background:#fff;border:1px dashed #cbd5e1;border-radius:15px;padding:.2rem}
    [data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:16px;padding:.7rem}.info-banner{background:#f0f9f3;border:1px solid #cfe7d7;border-radius:15px;padding:.85rem 1rem;color:#42564a}
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
    .activity-row{display:flex;gap:.7rem;padding:.7rem 0;border-bottom:1px solid #edf0f4}.activity-dot{width:7px;height:7px;border-radius:50%;background:#198754;margin-top:.42rem;flex:0 0 auto}
    .footer{text-align:center;color:#718078;font-size:.64rem;padding:2rem 0 1rem}
    /* No dark/black panels: keep cards, fields and messages light and readable. */
    .stMarkdown,.stCaption,[data-testid="stCaptionContainer"]{color:#33443a}
    .receipt-card{background:#ffffff;border:1px solid #cfe5d7;border-radius:18px;padding:1.1rem 1.2rem;box-shadow:0 5px 18px rgba(35,75,52,.06)}
    .receipt-head{display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;border-bottom:1px solid #e4eee8;padding-bottom:.8rem;margin-bottom:.75rem}
    .receipt-title{font-size:1.15rem;font-weight:800;color:#155c3b}.receipt-ref{color:#198754;font-weight:800}.receipt-row{display:flex;justify-content:space-between;gap:1rem;padding:.45rem 0;border-bottom:1px solid #eef3ef;color:#34443a}.receipt-total{display:flex;justify-content:space-between;padding-top:.85rem;font-size:1.1rem;font-weight:800;color:#155c3b}
    /* Force Streamlit native widgets into the same light theme. */
    .stFileUploader, [data-testid="stFileUploader"], [data-testid="stFileUploaderDropzone"]{background:#ffffff!important;color:#34443a!important;border-color:#cfe0d7!important}
    [data-testid="stFileUploaderDropzone"] *{color:#34443a!important}
    [data-testid="stFileUploaderDropzoneInstructions"] div, [data-testid="stFileUploaderDropzoneInstructions"] span{color:#52655b!important}
    [data-testid="stFileUploaderDropzone"] small{color:#7a8a82!important}
    [data-testid="stFileUploaderDropzone"] button{background:#eef8f2!important;color:#176b46!important;border:1px solid #cfe5d7!important}
    [data-baseweb="select"]>div{background:#ffffff!important;color:#34443a!important;border-color:#dce3eb!important}
    [data-baseweb="select"] *{color:#34443a!important}
    [role="listbox"], [role="option"]{background:#ffffff!important;color:#34443a!important}
    /* Final selectbox readability: selected value AND opened options must stay dark on white. */
    [data-baseweb="select"],
    [data-baseweb="select"] > div,
    [data-baseweb="select"] [role="combobox"]{
        background:#ffffff!important;
        color:#253247!important;
        border-color:#cfe0d7!important;
    }
    [data-baseweb="select"] span,
    [data-baseweb="select"] div,
    [data-baseweb="select"] input,
    [data-baseweb="select"] svg{
        color:#253247!important;
        fill:#253247!important;
        opacity:1!important;
    }
    [data-baseweb="popover"],
    [data-baseweb="menu"],
    [data-baseweb="menu"] > div,
    [role="listbox"]{
        background:#ffffff!important;
        color:#253247!important;
        border-color:#dce3eb!important;
    }
    [data-baseweb="menu"] li,
    [role="option"],
    [role="option"] *{
        background:#ffffff!important;
        color:#253247!important;
        opacity:1!important;
    }
    [role="option"][aria-selected="true"],
    [role="option"][data-highlighted="true"]{
        background:#eaf7ef!important;
        color:#155c3b!important;
    }
    [role="option"][aria-selected="true"] *,
    [role="option"][data-highlighted="true"] *{
        color:#155c3b!important;
    }
    [data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li{color:#34443a}
    [data-testid="stHeader"]{background:#f8fbf9!important}
    [data-testid="stSidebar"] *{color:#34443a}
    [data-testid="stSidebar"] .stButton>button{background:#ffffff!important;color:#34443a!important}
    [data-testid="stSidebar"] .stButton>button[kind="primary"]{background:#198754!important;color:#ffffff!important}
    .stTextInput input::placeholder,.stTextArea textarea::placeholder,.stNumberInput input::placeholder{color:#8a9891!important;opacity:1!important}
    .stTextInput input:disabled,.stTextArea textarea:disabled,.stNumberInput input:disabled{background:#f5f8f6!important;color:#6b7b72!important}

    /* Final readability override: no black button surfaces and always-contrasting button text. */
    .stButton > button,
    .stButton > button[kind="secondary"],
    .stButton > button[kind="tertiary"],
    .stButton > button[kind="primary"],
    button[data-testid="baseButton-secondary"],
    button[data-testid="baseButton-primary"],
    button[data-testid="baseButton-tertiary"]{
        background:#ffffff!important;
        color:#253247!important;
        border:1px solid #cfe0d7!important;
        text-shadow:none!important;
        box-shadow:0 2px 8px rgba(42,66,100,.05)!important;
    }
    .stButton > button:hover,
    button[data-testid="baseButton-secondary"]:hover,
    button[data-testid="baseButton-tertiary"]:hover{
        background:#eef8f2!important;
        color:#155c3b!important;
        border-color:#a9d5ba!important;
    }
    .stButton > button[kind="primary"],
    button[data-testid="baseButton-primary"]{
        background:#198754!important;
        color:#ffffff!important;
        border:1px solid #198754!important;
    }
    .stButton > button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover{
        background:#157347!important;
        color:#ffffff!important;
    }
    .stButton > button:disabled{
        background:#f1f5f3!important;
        color:#7a8a82!important;
        border-color:#dce5df!important;
        opacity:1!important;
    }
    /* Catch dark native button descendants/icons too. */
    .stButton > button *,
    button[data-testid^="baseButton-"] *{
        color:inherit!important;
    }

    /* HARD LIGHT THEME OVERRIDES - prevents Streamlit dark theme from leaking through */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > .main,
    [data-testid="stMain"], main, section[data-testid="stSidebar"], [data-testid="stSidebar"],
    [data-testid="stHeader"], [data-testid="stToolbar"]{
        background:#f7faf8!important;
        color:#25312a!important;
    }
    [data-testid="stAppViewContainer"]{background:#f7faf8!important;}
    [data-testid="stSidebar"]{background:#ffffff!important;}
    [data-testid="stSidebar"] > div{background:#ffffff!important;}

    /* Every native button: NEVER black. */
    button,
    [role="button"],
    [data-testid="baseButton-secondary"],
    [data-testid="baseButton-primary"],
    [data-testid="baseButton-tertiary"],
    [data-testid="stBaseButton-secondary"],
    [data-testid="stBaseButton-primary"],
    [data-testid="stBaseButton-tertiary"]{
        background:#ffffff!important;
        color:#253247!important;
        border-color:#cfe0d7!important;
        text-shadow:none!important;
    }
    button:hover,
    [role="button"]:hover,
    [data-testid="baseButton-secondary"]:hover,
    [data-testid="baseButton-tertiary"]:hover{
        background:#eaf7ef!important;
        color:#155c3b!important;
        border-color:#9dccad!important;
    }
    [data-testid="baseButton-primary"],
    [data-testid="stBaseButton-primary"]{
        background:#198754!important;
        color:#ffffff!important;
        border-color:#198754!important;
    }
    [data-testid="baseButton-primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover{
        background:#157347!important;
        color:#ffffff!important;
    }
    button:disabled,
    [role="button"][aria-disabled="true"]{
        background:#eef2f0!important;
        color:#6b7b72!important;
        border-color:#d7e1db!important;
        opacity:1!important;
    }
    button svg, [role="button"] svg{color:currentColor!important;fill:currentColor!important;}
    button span, button p, button div{color:inherit!important;}

    /* Edit-price / action controls and other BaseWeb controls. */
    [data-baseweb="button"]{
        background:#ffffff!important;
        color:#253247!important;
        border-color:#cfe0d7!important;
    }
    [data-baseweb="button"]:hover{
        background:#eaf7ef!important;
        color:#155c3b!important;
    }
    [data-baseweb="popover"]{
        background:#ffffff!important;
        color:#253247!important;
    }
    [data-baseweb="menu"],
    [data-baseweb="menu"] > div,
    [role="menu"],
    [role="menuitem"]{
        background:#ffffff!important;
        color:#253247!important;
    }

    /* Remove dark surfaces from common Streamlit containers. */
    [data-testid="stVerticalBlock"],
    [data-testid="stHorizontalBlock"],
    [data-testid="stElementContainer"],
    [data-testid="stForm"],
    [data-testid="stDialog"],
    [data-testid="stPopover"]{
        color:#253247;
    }
    [data-testid="stForm"]{
        background:#ffffff!important;
        border-color:#dfe9e3!important;
    }

    /* Catch any black-ish inline surface generated by Streamlit widgets. */
    [data-testid="stFileUploaderDropzone"],
    [data-testid="stFileUploaderDropzone"] section{
        background:#ffffff!important;
        color:#34443a!important;
    }
    [data-testid="stFileUploaderDropzone"] button{
        background:#eef8f2!important;
        color:#176b46!important;
    }
    [data-baseweb="select"] > div,
    [data-baseweb="input"] > div{
        background:#ffffff!important;
        color:#253247!important;
        border-color:#dce3eb!important;
    }
    [data-baseweb="select"] input,
    [data-baseweb="input"] input{
        color:#253247!important;
    }

    /* ASK BRAIN / CHAT: force the chat composer and messages into the light theme. */
    [data-testid="stChatInput"],
    [data-testid="stChatInput"] > div,
    [data-testid="stChatInput"] form,
    [data-testid="stChatInput"] [data-baseweb="textarea"],
    [data-testid="stChatInput"] [data-baseweb="textarea"] > div,
    [data-testid="stChatInput"] textarea{
        background:#ffffff!important;
        color:#253247!important;
        border-color:#cfe0d7!important;
    }
    [data-testid="stChatInput"] textarea::placeholder{
        color:#7a8a82!important;
        opacity:1!important;
    }
    [data-testid="stChatInput"] button,
    [data-testid="stChatInput"] button svg{
        background:#198754!important;
        color:#ffffff!important;
        fill:#ffffff!important;
        border-color:#198754!important;
    }
    [data-testid="stChatMessage"],
    [data-testid="stChatMessageContent"],
    [data-testid="stChatMessageContent"] > div{
        color:#253247!important;
    }
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"],
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] li{
        color:#253247!important;
    }
    /* Any BaseWeb textarea/input used by Ask Brain must stay white even before hover/focus. */
    [data-baseweb="textarea"] > div,
    [data-baseweb="textarea"] textarea,
    textarea{
        background:#ffffff!important;
        color:#253247!important;
    }

    /* FINAL SELECTBOX FIX — only the closed selected-value box. */
    [data-testid="stSelectbox"] [data-baseweb="select"],
    [data-testid="stSelectbox"] [data-baseweb="select"] > div,
    [data-testid="stSelectbox"] [data-baseweb="select"] > div > div,
    [data-testid="stSelectbox"] [data-baseweb="select"] [role="combobox"] {
        background:#ffffff !important;
        color:#17212b !important;
        opacity:1 !important;
        color-scheme:light !important;
    }

    [data-testid="stSelectbox"] [data-baseweb="select"] *,
    [data-testid="stSelectbox"] [data-baseweb="select"] span,
    [data-testid="stSelectbox"] [data-baseweb="select"] div[class*="singleValue"],
    [data-testid="stSelectbox"] [data-baseweb="select"] div[class*="SingleValue"],
    [data-testid="stSelectbox"] [data-baseweb="select"] [aria-live="polite"],
    [data-testid="stSelectbox"] [data-baseweb="select"] input {
        color:#17212b !important;
        -webkit-text-fill-color:#17212b !important;
        opacity:1 !important;
        visibility:visible !important;
        text-shadow:none !important;
        filter:none !important;
        mix-blend-mode:normal !important;
    }

    [data-testid="stSelectbox"] [data-baseweb="select"] svg {
        color:#17212b !important;
        fill:#17212b !important;
        opacity:1 !important;
    }

    /* Open-menu options only: keep their existing white surface, dark text. */
    [data-testid="stSelectbox"] ~ [data-baseweb="popover"] [role="option"],
    [data-baseweb="popover"] [role="option"],
    [data-baseweb="menu"] [role="option"] {
        color:#17212b !important;
        -webkit-text-fill-color:#17212b !important;
        opacity:1 !important;
    }
    [data-baseweb="popover"] [role="option"] *,
    [data-baseweb="menu"] [role="option"] * {
        color:#17212b !important;
        -webkit-text-fill-color:#17212b !important;
        opacity:1 !important;
    }
    </style>
    """,unsafe_allow_html=True)

def sidebar(business, role="Owner"):
    from access_control import visible_pages
    allowed = set(visible_pages(role))
    with st.sidebar:
        st.markdown(f"<div class='brand'><div class='brand-name'>◈ Business Brain</div><div class='brand-sub'>{business['name']}</div></div>",unsafe_allow_html=True)
        st.markdown("<div class='nav-label'>Menu</div>",unsafe_allow_html=True)
        for label,icon in NAV:
            if label not in allowed:
                continue
            active=st.session_state.page==label
            if st.button(f"{icon}  {label}",key=f"nav_{label}",use_container_width=True,type="primary" if active else "secondary"):
                st.session_state.page=label; st.rerun()
        st.markdown("<div style='height:.8rem'></div>",unsafe_allow_html=True)
        st.markdown("<div class='info-banner' style='font-size:.68rem'><b>Simple mode</b><br>Just tell Business Brain what you need. The agents handle the background work.</div>",unsafe_allow_html=True)

def page_header(title,subtitle,kicker="Business Brain"):
    st.markdown(f"<div class='page-kicker'>{kicker}</div>",unsafe_allow_html=True); st.title(title); st.markdown(f"<div class='subtitle'>{subtitle}</div>",unsafe_allow_html=True); st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True)

def stat_card(label,value,sub):
    st.markdown(f"<div class='stat'><div class='stat-label'>{label}</div><div class='stat-value'>{value}</div><div class='stat-sub'>{sub}</div></div>",unsafe_allow_html=True)

def empty_state(title,description):
    st.markdown(f"<div style='text-align:center;padding:2.4rem 1rem;border:1px dashed #ccd5e1;border-radius:16px;background:#fff'><div style='font-weight:700;color:#263244'>{title}</div><div class='muted' style='margin-top:.3rem'>{description}</div></div>",unsafe_allow_html=True)

def source_card(source):
    st.markdown(f"<div class='premium-card'><b>{source['title']}</b> <span class='tiny'>· {source['type']} · {source.get('score',0):.2f}</span><div class='muted' style='margin-top:.3rem'>{source.get('content','')}</div></div>",unsafe_allow_html=True)
