import streamlit as st
import re
from dotenv import load_dotenv

from database import (
    init_db, seed_demo_data, get_business, list_processes, list_knowledge,
    list_chunks, get_activity, get_process, update_process, log_activity,
)
from agent import generate_sop_from_inputs, answer_business_question
from rag import ingest_knowledge_file, ingest_text_knowledge, index_process, bootstrap_index
from ui import inject_css, sidebar, page_header, stat_card, empty_state, source_card

load_dotenv()
init_db()
seed_demo_data()
bootstrap_index()

st.set_page_config(
    page_title="Business Brain",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_css()
business = get_business()

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
if "chat" not in st.session_state:
    st.session_state.chat = []
if "draft_sop" not in st.session_state:
    st.session_state.draft_sop = None
if "notice" not in st.session_state:
    st.session_state.notice = None
if "edit_process" not in st.session_state:
    st.session_state.edit_process = False

sidebar(business)

if st.session_state.get("notice"):
    st.success(st.session_state.notice)
    st.session_state.notice = None

page = st.session_state.page

if page == "Dashboard":
    page_header("Your Business Brain", "Your business information, processes, and answers — all in one place.", "Dashboard")
    processes = list_processes()
    knowledge = list_knowledge()
    chunks = list_chunks()
    activity = get_activity(6)
    indexed_count = sum(1 for x in knowledge if x["status"] == "Indexed")
    chunk_count = len(chunks)
    cols = st.columns(4)
    stats = [("Processes", len(processes), "Documented workflows"), ("Knowledge", len(knowledge), "Sources in your Brain"), ("Searchable chunks", chunk_count, "Ready for retrieval"), ("Activity", len(get_activity(1000)), "Recent workspace events")]
    for col, (label, value, sub) in zip(cols, stats):
        with col: stat_card(label, value, sub)
    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    if not knowledge:
        st.markdown("<div class='info-banner'><b>Business Brain needs knowledge.</b> Add a policy, guide, FAQ or document to start building your searchable Brain.</div>", unsafe_allow_html=True)
    elif indexed_count == len(knowledge) and chunk_count > 0:
        st.markdown(f"<div class='info-banner'><b>✓ Business Brain is healthy.</b> {indexed_count} knowledge items are indexed and {chunk_count} searchable chunks are ready for retrieval.</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='info-banner'><b>Business Brain needs attention.</b> {indexed_count} of {len(knowledge)} knowledge items are indexed. {chunk_count} searchable chunks are available.</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    left, right = st.columns([1.65, 1], gap="large")
    with left:
        st.markdown("### Quick actions")
        qcols = st.columns(3)
        actions = [("＋", "Record Process", "Describe a task and let AI turn it into an SOP.", "Record Process"), ("✦", "Add Knowledge", "Add a policy, guide, FAQ, or other business information.", "Knowledge"), ("⌕", "Ask Brain", "Ask a question and get an answer from your saved information.", "Ask Brain")]
        for c, (icon, title, desc, target) in zip(qcols, actions):
            with c:
                st.markdown(f"<div class='action-card'><div class='action-icon'>{icon}</div><div class='action-title'>{title}</div><div class='action-desc'>{desc}</div></div>", unsafe_allow_html=True)
                if st.button(f"Open {title}", key=f"qa_{target}", use_container_width=True): st.session_state.page = target; st.rerun()
        st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
        st.markdown("### Knowledge Coverage")
        type_counts = {}
        for item in knowledge:
            kind = item.get("type") or "Other"; type_counts[kind] = type_counts.get(kind, 0) + 1
        if type_counts:
            coverage_cols = st.columns(min(4, max(1, len(type_counts))))
            for col, (kind, count) in zip(coverage_cols, sorted(type_counts.items(), key=lambda x: (-x[1], x[0]))):
                with col: stat_card(kind, count, f"{round(count / len(knowledge) * 100)}% of knowledge")
        else: empty_state("No knowledge coverage yet", "Add your first knowledge item.")
        st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
        st.markdown("### Recent processes")
        if not processes: empty_state("No processes yet", "Record your first workflow to start teaching your Business Brain.")
        else:
            for p in processes[:5]:
                c1, c2, c3 = st.columns([4, 1.5, 1])
                with c1: st.markdown(f"**{p['name']}**"); st.caption(p["description"] or "Structured business workflow")
                with c2: st.caption(p["category"])
                with c3:
                    if st.button("Open", key=f"open_p_{p['id']}"): st.session_state.selected_process = p["id"]; st.session_state.page = "Process detail"; st.rerun()
    with right:
        st.markdown("### Recent activity")
        if not activity: empty_state("Nothing here yet", "Your workspace activity will appear here.")
        for item in activity:
            st.markdown(f"<div class='activity-row'><div class='activity-dot'></div><div><b>{item['action']}</b><div class='muted'>{item['details']}</div><div class='tiny'>{item['created_at']}</div></div></div>", unsafe_allow_html=True)

elif page == "Record Process":
    page_header(
        "Create a new process",
        "Describe how a task is done, and AI will turn it into an editable SOP.",
        "Process Recorder",
    )

    st.markdown("""
    <div class='info-banner'>
      <b>Start with what you know.</b> Describe the process in plain language, or add a document/screenshot.
      Business Brain will structure the evidence into an editable SOP. Nothing is saved until you approve it.
    </div>
    """, unsafe_allow_html=True)

    with st.form("process_recorder"):
        title_hint = st.text_input("Process name (optional)", placeholder="e.g. New Customer Order")
        description = st.text_area(
            "Describe the process",
            height=220,
            placeholder="Explain what normally happens from the trigger to the final outcome. Include people, tools, decisions, exceptions, and anything that is easy for a new employee to miss.",
        )
        uploads = st.file_uploader(
            "Supporting files",
            type=["pdf", "docx", "txt", "md", "csv", "xlsx", "png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            help="For MVP, text documents, PDFs and images are supported. Audio/video can be added later.",
        )
        submitted = st.form_submit_button("Generate SOP", type="primary", use_container_width=True)

    if submitted:
        if not description.strip() and not uploads:
            st.error("Add a process description or at least one supporting file.")
        else:
            with st.spinner("Analyzing your process and structuring the SOP…"):
                result = generate_sop_from_inputs(title_hint, description, uploads)
            if result["ok"]:
                st.session_state.draft_sop = result["sop"]
                st.session_state.draft_sources = result.get("sources", [])
                st.success("Draft SOP generated. Review it before saving.")
                st.rerun()
            else:
                st.error(result["error"])

    if st.session_state.draft_sop:
        st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
        st.markdown("### Review & edit")
        sop = st.session_state.draft_sop

        with st.form("sop_editor"):
            name = st.text_input("Process name", value=sop.get("process_name", ""))
            category = st.text_input("Category", value=sop.get("category", "Operations"))
            purpose = st.text_area("Purpose", value=sop.get("purpose", ""))
            trigger = st.text_input("Trigger", value=sop.get("trigger", ""))
            inputs = st.text_area("Required inputs", value="\n".join(sop.get("required_inputs", [])))
            roles = st.text_area("People / roles", value="\n".join(sop.get("roles", [])))
            steps = st.text_area("Step-by-step workflow", value="\n".join(
                [f"{i+1}. {s.get('action','')}" + (f" — {s.get('notes','')}" if s.get("notes") else "")
                 for i, s in enumerate(sop.get("steps", []))]
            ), height=260)
            decisions = st.text_area("Decisions / conditions", value="\n".join(sop.get("decisions", [])))
            exceptions = st.text_area("Exceptions / warnings", value="\n".join(sop.get("exceptions", [])))
            output = st.text_area("Expected output", value=sop.get("output", ""))
            tags = st.text_input("Tags", value=", ".join(sop.get("tags", [])))
            save = st.form_submit_button("Save to Business Brain", type="primary", use_container_width=True)

        if save:
            from database import create_process, log_activity
            process = {
                "name": name.strip() or "Untitled Process",
                "description": purpose.strip(),
                "category": category.strip() or "Operations",
                "owner": "Business Owner",
                "status": "Active",
                "trigger": trigger.strip(),
                "inputs": [x.strip() for x in inputs.splitlines() if x.strip()],
                "roles": [x.strip() for x in roles.splitlines() if x.strip()],
                "steps": [{"action": x.strip()} for x in steps.splitlines() if x.strip()],
                "decisions": [x.strip() for x in decisions.splitlines() if x.strip()],
                "exceptions": [x.strip() for x in exceptions.splitlines() if x.strip()],
                "output": output.strip(),
                "tags": [x.strip() for x in tags.split(",") if x.strip()],
            }
            pid = create_process(process)
            index_process(pid, process)
            log_activity("Process created", process["name"])
            st.session_state.draft_sop = None
            st.success("Process saved and indexed. Business Brain can now retrieve it.")
            st.session_state.page = "Processes"
            st.rerun()

elif page == "Knowledge":
    page_header(
        "Knowledge",
        "Store policies, guides, FAQs, documents, and other business information.",
        "Knowledge base",
    )
    tabs = st.tabs(["Add knowledge", "Library"])

    with tabs[0]:
        st.markdown("### Add a knowledge item")
        with st.form("knowledge_form"):
            title = st.text_input("Title", placeholder="e.g. Customer Service Policy")
            kind = st.selectbox("Type", ["Policy", "FAQ", "Guide", "Document", "Product info", "Note", "Other"])
            tags = st.text_input("Tags", placeholder="orders, customer-service")
            text = st.text_area("Notes / text", height=180, placeholder="Paste useful business knowledge here.")
            file = st.file_uploader(
                "Or upload a file",
                type=["pdf", "docx", "txt", "md", "csv", "xlsx", "png", "jpg", "jpeg", "webp"],
                accept_multiple_files=False,
            )
            save_k = st.form_submit_button("Add to Business Brain", type="primary", use_container_width=True)

        if save_k:
            if not title.strip():
                st.error("Give this knowledge item a title.")
            elif not text.strip() and not file:
                st.error("Add some text or upload a file.")
            else:
                with st.spinner("Extracting, structuring and indexing…"):
                    result = ingest_knowledge_file(title, kind, tags, file, text)

                if result.get("duplicate"):
                    st.info(
                        "This knowledge item already exists in your Business Brain. "
                        "Nothing new was added."
                    )
                elif result.get("ok"):
                    st.success("Knowledge added and indexed.")
                    st.session_state.notice = "Knowledge added and indexed successfully."
                    st.rerun()
                else:
                    st.error(result.get("error", "Something went wrong while adding knowledge."))

    with tabs[1]:
        knowledge = list_knowledge()
        if not knowledge:
            empty_state("Your knowledge base is empty", "Add policies, guides, FAQs and documents.")
        for k in knowledge:
            with st.container(border=True):
                a, b, c = st.columns([4, 1.2, 1.2])
                with a:
                    st.markdown(f"**{k['title']}**")
                    st.caption(k["description"] or "Business knowledge source")
                with b:
                    st.caption(k["type"])
                with c:
                    st.caption(k["status"])
                if k["tags"]:
                    st.caption(" · ".join(k["tags"]))

elif page == "Ask Brain":
    page_header(
        "Ask Brain",
        "Ask a question and Business Brain will answer using your saved business information and processes.",
        "AI workspace",
    )

    if not st.session_state.chat:
        st.markdown("""
        <div class='brain-hero'>
          <div class='brain-mark'>✦</div>
          <h2>Your business, remembered.</h2>
          <p>Ask about processes, policies, responsibilities, requirements, or related documents.</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### Suggested questions")
        qs = [
            "How does our order process work?",
            "What information is required before creating a new order?",
            "Who handles customer complaints?",
            "What should I do after receiving a custom cake order?",
        ]
        qcols = st.columns(2)
        for i, q in enumerate(qs):
            with qcols[i % 2]:
                if st.button(q, key=f"suggest_{i}", use_container_width=True):
                    st.session_state.pending_question = q
                    st.rerun()

    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                st.markdown("**Sources**")
                for source in message["sources"]:
                    source_card(source)

    pending = st.session_state.pop("pending_question", None)
    question = st.chat_input("Ask Business Brain…")
    question = question or pending

    if question:
        st.session_state.chat.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Searching your Business Brain…"):
                result = answer_business_question(question)
            if result["ok"]:
                st.markdown(result["answer"])
                if result["sources"]:
                    st.markdown("**Sources**")
                    for source in result["sources"]:
                        source_card(source)
                st.session_state.chat.append({
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result["sources"],
                })
            else:
                st.error(result["error"])
                st.session_state.chat.append({
                    "role": "assistant",
                    "content": result["error"],
                    "sources": [],
                })

elif page == "Processes":
    page_header(
        "Processes",
        "View and manage the step-by-step ways your business gets work done.",
        "Process library",
    )

    processes = list_processes()
    total = len(processes)
    active = sum(1 for p in processes if (p.get("status") or "").casefold() == "active")
    categories = sorted({(p.get("category") or "Other").strip() or "Other" for p in processes})

    cols = st.columns(4)
    for col, (label, value, sub) in zip(cols, [
        ("Total processes", total, "Documented workflows"),
        ("Active", active, "Currently in use"),
        ("Categories", len(categories), "Workflow areas"),
        ("Recently updated", min(total, 5), "Latest library entries"),
    ]):
        with col:
            stat_card(label, value, sub)

    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    search_col, filter_col = st.columns([2.2, 1])
    with search_col:
        process_search = st.text_input(
            "Search processes",
            placeholder="Search by process name or description…",
            label_visibility="collapsed",
        )
    with filter_col:
        category_filter = st.selectbox(
            "Category",
            ["All categories"] + categories,
            label_visibility="collapsed",
        )

    filtered = processes
    if process_search.strip():
        q = process_search.casefold().strip()
        filtered = [
            p for p in filtered
            if q in (p.get("name") or "").casefold()
            or q in (p.get("description") or "").casefold()
        ]
    if category_filter != "All categories":
        filtered = [p for p in filtered if (p.get("category") or "Other") == category_filter]

    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    if not filtered:
        if processes:
            empty_state("No matching processes", "Try a different search term or category.")
        else:
            empty_state("No processes yet", "Record a process to create your first SOP.")
    else:
        for p in filtered:
            with st.container(border=True):
                a, b, c, d = st.columns([3.7, 1.25, 1.15, 1])
                with a:
                    st.markdown(f"**{p['name']}**")
                    st.caption(p.get("description") or "Structured business workflow")
                    st.caption(f"Owner: {p.get('owner') or 'Business Owner'} · Updated {p.get('updated_at') or '—'}")
                with b:
                    st.caption(p.get("category") or "Other")
                with c:
                    st.caption(p.get("status") or "Active")
                with d:
                    if st.button("Open", key=f"view_{p['id']}", use_container_width=True):
                        st.session_state.selected_process = p["id"]
                        st.session_state.page = "Process detail"
                        st.rerun()

elif page == "Process detail":
    p = get_process(st.session_state.get("selected_process"))
    if not p:
        st.error("Process not found.")
    else:
        page_header(p["name"], p.get("description") or "Structured business workflow", "Process")
        st.caption(f"{p.get('category') or 'Other'} · {p.get('status') or 'Active'} · Owner: {p.get('owner') or 'Business Owner'} · Updated {p.get('updated_at') or '—'}")

        action_left, action_right = st.columns([1, 5])
        with action_left:
            edit_mode = st.button("Edit Process", use_container_width=True)
        if edit_mode:
            st.session_state.edit_process = True
            st.rerun()

        if st.session_state.get("edit_process"):
            st.markdown("### Edit process")
            with st.form("process_edit_form"):
                name = st.text_input("Process name", value=p.get("name", ""))
                category = st.text_input("Category", value=p.get("category", "Operations"))
                status = st.selectbox("Status", ["Active", "Draft", "Archived"], index=["Active", "Draft", "Archived"].index(p.get("status", "Active")) if p.get("status", "Active") in ["Active", "Draft", "Archived"] else 0)
                purpose = st.text_area("Description / purpose", value=p.get("description", ""))
                trigger = st.text_input("Trigger", value=p.get("trigger", ""))
                inputs = st.text_area("Required inputs", value="\n".join(p.get("inputs", [])))
                roles = st.text_area("People / roles", value="\n".join(p.get("roles", [])))
                steps_text = "\n".join(
                    [f"{i+1}. {s.get('action','')}" + (f" — {s.get('notes','')}" if s.get("notes") else "") for i, s in enumerate(p.get("steps", []))]
                )
                steps = st.text_area("Step-by-step workflow", value=steps_text, height=240)
                decisions = st.text_area("Decisions / conditions", value="\n".join(p.get("decisions", [])))
                exceptions = st.text_area("Exceptions / warnings", value="\n".join(p.get("exceptions", [])))
                output = st.text_area("Expected output", value=p.get("output", ""))
                tags = st.text_input("Tags", value=", ".join(p.get("tags", [])))
                save_edit = st.form_submit_button("Save changes", type="primary", use_container_width=True)

            if save_edit:
                clean_steps = []
                for line in steps.splitlines():
                    line = re.sub(r"^\s*\d+[.)]\s*", "", line).strip()
                    if not line:
                        continue
                    if " — " in line:
                        action, notes = line.split(" — ", 1)
                        clean_steps.append({"action": action.strip(), "notes": notes.strip()})
                    else:
                        clean_steps.append({"action": line})
                updated = {
                    "name": name.strip() or "Untitled Process",
                    "description": purpose.strip(),
                    "category": category.strip() or "Operations",
                    "owner": p.get("owner") or "Business Owner",
                    "status": status,
                    "trigger": trigger.strip(),
                    "inputs": [x.strip() for x in inputs.splitlines() if x.strip()],
                    "roles": [x.strip() for x in roles.splitlines() if x.strip()],
                    "steps": clean_steps,
                    "decisions": [x.strip() for x in decisions.splitlines() if x.strip()],
                    "exceptions": [x.strip() for x in exceptions.splitlines() if x.strip()],
                    "output": output.strip(),
                    "tags": [x.strip() for x in tags.split(",") if x.strip()],
                }
                if update_process(p["id"], updated):
                    index_process(p["id"], updated)
                    log_activity("Process updated", updated["name"])
                    st.session_state.edit_process = False
                    st.success("Process updated and re-indexed. Business Brain can use the latest version.")
                    st.rerun()
                else:
                    st.error("No changes were saved.")
        else:
            tabs = st.tabs(["Overview", "Workflow", "Decisions & exceptions", "Related knowledge", "History"])
            with tabs[0]:
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### Trigger")
                    st.write(p.get("trigger") or "Not specified")
                    st.markdown("#### Required inputs")
                    if p.get("inputs"):
                        for x in p["inputs"]: st.markdown(f"- {x}")
                    else:
                        st.caption("Not specified")
                with c2:
                    st.markdown("#### People / roles")
                    if p.get("roles"):
                        for x in p["roles"]: st.markdown(f"- {x}")
                    else:
                        st.caption("Not specified")
                    st.markdown("#### Expected output")
                    st.write(p.get("output") or "Not specified")
            with tabs[1]:
                if not p.get("steps"):
                    empty_state("No workflow steps yet", "Edit the process to add the step-by-step workflow.")
                for i, step in enumerate(p.get("steps", []), 1):
                    action = step.get("action", "")
                    notes = step.get("notes", "")
                    notes_html = f"<div class='muted'>{notes}</div>" if notes else ""
                    st.markdown(f"<div class='step-row'><span class='step-number'>{i}</span><div><b>{action}</b>{notes_html}</div></div>", unsafe_allow_html=True)
            with tabs[2]:
                st.markdown("#### Decision points")
                if p.get("decisions"):
                    for x in p["decisions"]: st.markdown(f"- {x}")
                else: st.caption("No decision points specified.")
                st.markdown("#### Exceptions & warnings")
                if p.get("exceptions"):
                    for x in p["exceptions"]: st.markdown(f"- {x}")
                else: st.caption("No exceptions or warnings specified.")
            with tabs[3]:
                st.caption("Knowledge relationships are intentionally lightweight in the MVP. Retrieval automatically surfaces semantically related sources when you ask Business Brain.")
            with tabs[4]:
                st.info("Version history is planned for the next stage. The current MVP preserves the process ID and records update activity while keeping the latest SOP searchable.")

elif page == "Activity":
    page_header("Activity", "See what has been added or changed in your Business Brain.", "Workspace")
    for item in get_activity(100):
        st.markdown(
            f"<div class='activity-row'><div class='activity-dot'></div>"
            f"<div><b>{item['action']}</b><div class='muted'>{item['details']}</div>"
            f"<div class='tiny'>{item['created_at']}</div></div></div>",
            unsafe_allow_html=True,
        )

elif page == "Settings":
    page_header("Settings", "Manage your Business Brain workspace configuration.", "Settings")
    st.markdown("### Business profile")
    with st.form("settings"):
        name = st.text_input("Business name", value=business["name"])
        profile = st.text_area("Short profile", value=business["profile"], height=120)
        save = st.form_submit_button("Save changes", type="primary")
    if save:
        from database import update_business, log_activity
        update_business(name.strip(), profile.strip())
        log_activity("Business profile updated", name.strip())
        st.success("Saved.")

st.markdown("<div class='footer'>Business Brain · MVP · Capture → Understand → Structure → Remember → Retrieve</div>", unsafe_allow_html=True)
