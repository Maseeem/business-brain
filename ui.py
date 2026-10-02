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
    <style>/* FINAL FIX — Streamlit selectbox selected value + dropdown options */
[data-baseweb="select"] [role="combobox"],
[data-baseweb="select"] [role="combobox"] * {
    color: #17212b !important;
    -webkit-text-fill-color: #17212b !important;
    opacity: 1 !important;
    text-shadow: none !important;
}

[data-baseweb="select"] > div,
[data-baseweb="select"] > div > div,
[data-baseweb="select"] div[class*="singleValue"] {
    color: #17212b !important;
    -webkit-text-fill-color: #17212b !important;
    opacity: 1 !important;
}

[data-baseweb="popover"],
[data-baseweb="popover"] *,
[data-baseweb="menu"],
[data-baseweb="menu"] *,
[role="listbox"],
[role="listbox"] *,
[role="option"],
[role="option"] * {
    background: #ffffff !important;
    color: #17212b !important;
    -webkit-text-fill-color: #17212b !important;
    opacity: 1 !important;
}

[role="option"]:hover,
[role="option"][aria-selected="true"],
[role="option"][data-highlighted="true"] {
    background: #eaf7ef !important;
    color: #155c3b !important;
    -webkit-text-fill-color: #155c3b !important;
}

[data-baseweb="select"] svg {
    color: #17212b !important;
    fill: #17212b !important;
    opacity: 1 !important;
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
