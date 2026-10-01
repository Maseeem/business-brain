import sqlite3
import os
import streamlit as st
from dotenv import load_dotenv

from database import (
    init_db, seed_demo_data, get_business, list_processes, list_knowledge, get_activity,
    get_process, create_process, update_process, delete_process, get_process_versions, restore_process_version,
    authenticate_user, list_users, create_user, get_user, update_user, reset_user_password, update_business, log_activity, ensure_demo_users,
    get_daily_operations, list_products, update_product, bulk_add_products, get_sale, list_supplier_orders, approve_supplier_order,
    save_confirmed_sale, find_supplier, find_supplier_for_product, create_supplier_order,
)
from agent import generate_sop_from_inputs, transcribe_audio_to_text
from knowledge_agent import answer as answer_knowledge_question
from coordinator_agent import route_request
from smart_sale_agent import execute_sale_request, apply_cart_edit
from operations_agent import low_stock_items, supplier_draft, classify_operation_request, answer_inventory_question, draft_supplier_order, execute_operation
from receipt_agent import verify_receipt
from rag import ingest_knowledge_file, edit_knowledge_item, remove_knowledge_item, detect_knowledge_contradictions, index_process, bootstrap_index
from ui import inject_css, sidebar, page_header, stat_card, empty_state, source_card

load_dotenv()
init_db()
if os.getenv("SEED_DEMO_DATA", "true").lower() == "true":
    seed_demo_data()
    ensure_demo_users()
bootstrap_index()

st.set_page_config(page_title="Business Brain", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
inject_css()

ROLE_PERMISSIONS = {
    "Owner": {"record": True, "knowledge": True, "edit": True, "users": True, "settings": True},
    "Manager": {"record": True, "knowledge": True, "edit": True, "users": False, "settings": False},
    "Employee": {"record": False, "knowledge": False, "edit": False, "users": False, "settings": False},
}

def can(action):
    user = st.session_state.get("user") or {}
    return ROLE_PERMISSIONS.get(user.get("role", "Employee"), {}).get(action, False)

def current_business_id():
    return int((st.session_state.get("user") or {}).get("business_id") or 1)

def receipt_download_text(sale):
    lines=["BUSINESS BRAIN — SALE RECEIPT","="*38,f"Sale Reference: {sale.get('transaction_ref','')}",f"Sale ID: #{sale.get('id','')}",f"Date: {sale.get('created_at','')}",""]
    for item in sale.get("items",[]):
        qty=float(item.get("quantity",0) or 0); price=float(item.get("unit_price",0) or 0); subtotal=float(item.get("subtotal",0) or 0)
        lines += [f"{item.get('name','Product')}  x {qty:g}",f"  Rs. {price:,.2f} each = Rs. {subtotal:,.2f}"]
    lines += ["","="*38,f"TOTAL: Rs. {float(sale.get('total',0) or 0):,.2f}","","Thank you."]
    return "\n".join(lines)

def is_manager_or_owner():
    return (st.session_state.get("user") or {}).get("role") in {"Owner","Manager"}


def _as_list(value):
    if value is None: return []
    if isinstance(value, list): return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, tuple): return [str(x).strip() for x in value if str(x).strip()]
    text = str(value).strip()
    return [x.strip() for x in text.splitlines() if x.strip()] if text else []

def _as_steps(value):
    if not isinstance(value, list): return []
    out=[]
    for item in value:
        if isinstance(item, dict): out.append(item)
        elif str(item).strip(): out.append({"action": str(item).strip()})
    return out

def _save_process_from_editor(values, existing_id=None, reason="Updated process"):
    if existing_id:
        changed = update_process(existing_id, values, st.session_state.user["id"], st.session_state.user["name"], reason)
        if changed:
            index_process(existing_id, values)
            log_activity("Process updated", values["name"], st.session_state.user["name"])
        return changed
    pid = create_process(values, st.session_state.user["id"], st.session_state.user["name"], "Initial version")
    index_process(pid, values)
    log_activity("Process created", values["name"], st.session_state.user["name"])
    return pid


def _delete_old_process_version(process_id, version):
    """Delete a historical version while protecting the current/latest version."""
    try:
        conn = sqlite3.connect("business_brain.db")
        conn.row_factory = sqlite3.Row

        # Find the version table columns so this works with the Phase 2 schema.
        cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(process_versions)").fetchall()
        }
        if not cols:
            conn.close()
            return False, "Version history table was not found."

        process_col = "process_id" if "process_id" in cols else "pid" if "pid" in cols else None
        version_col = "version" if "version" in cols else None

        if not process_col or not version_col:
            conn.close()
            return False, "The version history schema is missing required columns."

        versions = conn.execute(
            f"SELECT {version_col} AS version FROM process_versions "
            f"WHERE {process_col}=? ORDER BY {version_col} DESC",
            (process_id,),
        ).fetchall()

        if not versions:
            conn.close()
            return False, "Version not found."

        latest_version = int(versions[0]["version"])

        # Never delete the current/latest version. It is the active SOP.
        if int(version) == latest_version:
            conn.close()
            return False, "The current version cannot be deleted."

        cur = conn.execute(
            f"DELETE FROM process_versions WHERE {process_col}=? AND {version_col}=?",
            (process_id, version),
        )
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()

        if deleted:
            return True, "Version deleted."
        return False, "Version could not be deleted."
    except Exception as exc:
        try:
            conn.close()
        except Exception:
            pass
        return False, f"Could not delete version: {exc}"


# ---------- Authentication ----------
if "user" not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.markdown("<div style='max-width:520px;margin:8vh auto 0'>", unsafe_allow_html=True)
    st.markdown("# ◈ Business Brain")
    st.caption("Your business knowledge, organized and ready to work.")
    st.markdown("### Sign in")
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="admin")
        password = st.text_input("Password", type="password", placeholder="Your password")
        submit = st.form_submit_button("Sign in", type="primary", use_container_width=True)
    if submit:
        user = authenticate_user(username, password)
        if user:
            st.session_state.user = user
            st.session_state.page = "Dashboard"
            st.rerun()
        else:
            st.error("Invalid username or password.")
    st.info("Demo login: admin / BusinessBrain123!  ·  manager / BusinessBrain123!  ·  employee / BusinessBrain123!")
    st.caption("Demo credentials are for testing only. Change them before production use.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

business = get_business()
if "page" not in st.session_state: st.session_state.page = "Dashboard"
if "chat" not in st.session_state: st.session_state.chat = []
if "draft_sop" not in st.session_state: st.session_state.draft_sop = None
if "draft_sources" not in st.session_state: st.session_state.draft_sources = []
if "notice" not in st.session_state: st.session_state.notice = None
if "sale_cart" not in st.session_state: st.session_state.sale_cart = []
if "sale_input_value" not in st.session_state: st.session_state.sale_input_value = ""
if "sale_last_id" not in st.session_state: st.session_state.sale_last_id = None
if "sale_missing_price" not in st.session_state: st.session_state.sale_missing_price = []
if "sale_unknown_items" not in st.session_state: st.session_state.sale_unknown_items = []

def reset_sale_workflow(clear_last_sale=True):
    """Reset only active Smart Sale state; leave unrelated session state intact."""
    st.session_state.sale_cart = []
    st.session_state.sale_input_value = ""
    st.session_state.sale_input = ""
    st.session_state.sale_missing_price = []
    st.session_state.sale_unknown_items = []
    st.session_state.sale_route = None
    if clear_last_sale:
        st.session_state.sale_last_id = None


sidebar(business)
with st.sidebar:
    st.markdown(f"**{st.session_state.user['name']}**")
    st.caption(f"{st.session_state.user['role']} · @{st.session_state.user['username']}")
    if st.button("Sign out", use_container_width=True):
        log_activity("User signed out", st.session_state.user["username"], st.session_state.user["name"])
        st.session_state.user = None
        st.rerun()

if st.session_state.get("notice"):
    st.success(st.session_state.notice); st.session_state.notice = None

page = st.session_state.page

# ---------- Dashboard ----------
if page == "Dashboard":
    business_id = current_business_id()
    page_header("Good morning 👋", "Your business knowledge, organized and ready to work.", "Dashboard")

    # Dashboard data is live and business-scoped. Keep the existing visual
    # components; only the Dashboard content is intentionally restored here.
    daily = get_daily_operations(business_id)
    products = list_products(business_id)

    today_sales = float(daily.get("sales_total", 0) or 0)
    today_orders = int(daily.get("sales_count", 0) or 0)
    low_stock = list(daily.get("low_stock", []) or [])
    low_stock_count = len(low_stock)

    missing_price = [p for p in products if p.get("active", 1) and p.get("price") is None]
    out_of_stock = [p for p in products if p.get("active", 1) and float(p.get("stock_quantity", 0) or 0) <= 0]

    pending_receipts = 0
    try:
        with sqlite3.connect("business_brain.db") as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM receipt_verifications WHERE business_id=? AND status IN ('Needs Review','Possible mismatch','Unclear')",
                (business_id,),
            ).fetchone()
            pending_receipts = int(row[0] or 0)
    except Exception:
        pending_receipts = 0

    pending_supplier_orders = int(daily.get("pending_supplier_orders", 0) or 0)
    attention_count = len(out_of_stock) + len([p for p in low_stock if p not in out_of_stock]) + len(missing_price) + pending_receipts + pending_supplier_orders

    cols = st.columns(4)
    stats = [
        ("Today's Sales", f"Rs. {today_sales:,.2f}", "Confirmed sales today"),
        ("Today's Orders", today_orders, "Confirmed orders today"),
        ("Low Stock", low_stock_count, "Products at or below minimum"),
        ("Need Attention", attention_count, "Items needing review"),
    ]
    for col, (label, value, sub) in zip(cols, stats):
        with col:
            stat_card(label, value, sub)

    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    left, right = st.columns([1.55, 1], gap="large")

    with left:
        st.markdown("### Need Attention")
        attention_items = []
        for product in out_of_stock:
            attention_items.append(("Out of stock", f"{product['name']} is out of stock.", "Inventory", f"attention_inventory_{product['id']}"))
        for product in low_stock:
            if product in out_of_stock:
                continue
            attention_items.append(("Low stock", f"{product['name']} · {float(product.get('stock_quantity', 0) or 0):g} {product.get('unit') or 'unit'} remaining.", "Inventory", f"attention_low_{product['id']}"))
        for product in missing_price:
            attention_items.append(("Missing price", f"{product['name']} has no selling price.", "Inventory", f"attention_price_{product['id']}"))
        if pending_receipts:
            attention_items.append(("Receipt verification pending", f"{pending_receipts} receipt verification(s) need review.", "Receipts", "attention_receipts"))
        if pending_supplier_orders:
            attention_items.append(("Supplier approval pending", f"{pending_supplier_orders} supplier order(s) need human approval.", "Suppliers", "attention_suppliers"))

        if not attention_items:
            empty_state("Nothing needs attention", "Your current business data has no outstanding dashboard actions.")
        else:
            for kind, detail, target, key in attention_items:
                c1, c2 = st.columns([4, 1.25])
                with c1:
                    st.markdown(f"**{kind}**")
                    st.caption(detail)
                with c2:
                    if st.button("Review", key=key, use_container_width=True):
                        st.session_state.page = target
                        st.rerun()

    with right:
        st.markdown("### Quick Actions")
        quick_actions = [
            ("＋", "New Sale", "Start a new Smart Sale order.", "Smart Sale", True, "dashboard_new_sale"),
            ("▦", "Inventory", "Review stock and product prices.", "Inventory", True, "dashboard_inventory"),
            ("🧾", "Check Receipt", "Review receipt verification.", "Receipts", True, "dashboard_receipt"),
            ("✦", "Ask Brain", "Ask an evidence-backed business question.", "Ask Brain", True, "dashboard_brain"),
        ]
        for icon, title, desc, target, allowed, key in quick_actions:
            st.markdown(f"<div class='action-card'><div class='action-icon'>{icon}</div><div class='action-title'>{title}</div><div class='action-desc'>{desc}</div></div>", unsafe_allow_html=True)
            if allowed and st.button(f"Open {title}", key=key, use_container_width=True):
                st.session_state.page = target
                st.rerun()

# ---------- Record Process ----------
elif page == "Record Process":
    if not can("record"):
        st.warning("Your Employee role is view-only. Ask a Manager or Owner to record a process."); st.stop()
    page_header("Record a process","Teach Business Brain how your team actually gets work done.","Process Recorder")
    st.markdown("<div class='info-banner'><b>Two easy ways to record.</b> Type the process, upload evidence, or record your explanation by voice. Nothing is saved until you approve the SOP.</div>",unsafe_allow_html=True)
    tab_text,tab_voice=st.tabs(["Text / files","🎙️ Voice-to-SOP"])
    with tab_text:
        with st.form("process_recorder"):
            title_hint=st.text_input("Process name (optional)",placeholder="e.g. Customer Appointment Booking")
            description=st.text_area("Describe the process",height=220,placeholder="Explain what normally happens from trigger to final outcome. Roman Urdu is fine.")
            uploads=st.file_uploader("Supporting files",type=["pdf","docx","txt","md","csv","xlsx","png","jpg","jpeg","webp"],accept_multiple_files=True)
            submitted=st.form_submit_button("Generate SOP",type="primary",use_container_width=True)
        if submitted:
            if not description.strip() and not uploads: st.error("Add a process description or at least one supporting file.")
            else:
                with st.spinner("Analyzing your process and structuring the SOP…"):
                    result=generate_sop_from_inputs(title_hint,description,uploads)
                if result["ok"]:
                    st.session_state.draft_sop=result["sop"]; st.session_state.draft_sources=result.get("sources",[]); st.success("Draft SOP generated. Review it before saving."); st.rerun()
                else: st.error(result["error"])
    with tab_voice:
        st.markdown("Record yourself explaining the process naturally. Gemini will transcribe it and turn it into the same editable SOP.")
        audio=st.audio_input("Record your process explanation",key="process_voice")
        voice_title=st.text_input("Process name (optional)",key="voice_title",placeholder="e.g. Customer Appointment Booking")
        if st.button("Turn voice into SOP",type="primary",disabled=audio is None,use_container_width=True):
            try:
                with st.spinner("Transcribing your recording…"): transcript=transcribe_audio_to_text(audio)
                with st.spinner("Turning the transcript into an editable SOP…"):
                    result=generate_sop_from_inputs(voice_title,transcript,[])
                if result["ok"]:
                    st.session_state.voice_transcript=transcript; st.session_state.draft_sop=result["sop"]; st.session_state.draft_sources=["Voice recording"]; st.success("Voice converted to an SOP draft. Review it below."); st.rerun()
                else: st.error(result["error"])
            except Exception as e: st.error(f"Voice-to-SOP failed: {e}")
        if st.session_state.get("voice_transcript"):
            with st.expander("View transcript"): st.write(st.session_state.voice_transcript)

    if st.session_state.draft_sop:
        st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True); st.markdown("### Review & edit")
        sop=st.session_state.draft_sop or {}; required_inputs=_as_list(sop.get("required_inputs")); roles_list=_as_list(sop.get("roles")); decisions_list=_as_list(sop.get("decisions")); exceptions_list=_as_list(sop.get("exceptions")); tags_list=_as_list(sop.get("tags")); steps_list=_as_steps(sop.get("steps"))
        with st.form("sop_editor"):
            name=st.text_input("Process name",value=sop.get("process_name","")); category=st.text_input("Category",value=sop.get("category","Operations")); purpose=st.text_area("Purpose",value=sop.get("purpose","")); trigger=st.text_input("Trigger",value=sop.get("trigger","")); inputs=st.text_area("Required inputs",value="\n".join(required_inputs)); roles=st.text_area("People / roles",value="\n".join(roles_list)); steps=st.text_area("Step-by-step workflow",value="\n".join([f"{i+1}. {s.get('action','')}"+(f" — {s.get('notes','')}" if s.get('notes') else "") for i,s in enumerate(steps_list)]),height=260); decisions=st.text_area("Decisions / conditions",value="\n".join(decisions_list)); exceptions=st.text_area("Exceptions / warnings",value="\n".join(exceptions_list)); output=st.text_area("Expected output",value=sop.get("output","")); tags=st.text_input("Tags",value=", ".join(tags_list))
            save=st.form_submit_button("Save to Business Brain",type="primary",use_container_width=True)
        if save:
            process={"name":name.strip() or "Untitled Process","description":purpose.strip(),"category":category.strip() or "Operations","owner":st.session_state.user["name"],"status":"Active","trigger":trigger.strip(),"inputs":[x.strip() for x in inputs.splitlines() if x.strip()],"roles":[x.strip() for x in roles.splitlines() if x.strip()],"steps":[{"action":x.strip()} for x in steps.splitlines() if x.strip()],"decisions":[x.strip() for x in decisions.splitlines() if x.strip()],"exceptions":[x.strip() for x in exceptions.splitlines() if x.strip()],"output":output.strip(),"tags":[x.strip() for x in tags.split(",") if x.strip()]}
            pid=_save_process_from_editor(process); st.session_state.draft_sop=None; st.session_state.voice_transcript=None; st.session_state.notice="Process saved as version 1 and indexed."; st.session_state.page="Processes"; st.rerun()

# ---------- Knowledge ----------
elif page == "Knowledge":
    page_header("Knowledge","Store policies, guides and business information.","Knowledge base")
    tabs=st.tabs(["Add knowledge","Library"])
    with tabs[0]:
        if not can("knowledge"):
            st.info("Employees can view knowledge and ask Brain, but only Managers and Owners can add it.")
        else:
            with st.form("knowledge_form"):
                title=st.text_input("Title",placeholder="e.g. Customer Service Policy")
                kind=st.selectbox("Type",["Policy","FAQ","Guide","Document","Product info","Note","Other"])
                tags=st.text_input("Tags",placeholder="orders, customer-service")
                text=st.text_area("Notes / text",height=180,placeholder="Paste useful business knowledge here.")
                file=st.file_uploader("Or upload a file",type=["pdf","docx","txt","md","csv","xlsx","png","jpg","jpeg","webp"])
                save_k=st.form_submit_button("Add to Business Brain",type="primary",use_container_width=True)
            if save_k:
                if not title.strip(): st.error("Give this knowledge item a title.")
                elif not text.strip() and not file: st.error("Add some text or upload a file.")
                else:
                    with st.spinner("Extracting, structuring and indexing…"):
                        result=ingest_knowledge_file(title,kind,tags,file,text)
                    if result.get("duplicate"):
                        st.info("This knowledge item already exists in your Business Brain. Nothing new was added.")
                    elif result.get("ok"):
                        st.session_state.notice="Knowledge added and indexed successfully."
                        st.rerun()
                    else:
                        st.error(result.get("error","Something went wrong while adding knowledge."))

    with tabs[1]:
        knowledge=list_knowledge()
        conflicts=detect_knowledge_contradictions(knowledge)

        if conflicts:
            st.warning(f"⚠️ {len(conflicts)} possible information contradiction(s) detected. Review the affected knowledge items before relying on them.")
            for conflict in conflicts:
                st.markdown(
                    f"**Possible conflict:** `{conflict['a_title']}` ↔ `{conflict['b_title']}`  \n"
                    f"{conflict['reason']}"
                )

        if not knowledge:
            empty_state("Your knowledge base is empty","Add policies, guides, FAQs and documents.")

        for k in knowledge:
            kid=k["id"]
            edit_key=f"edit_knowledge_{kid}"
            delete_key=f"confirm_delete_knowledge_{kid}"
            with st.container(border=True):
                a,b,c,d=st.columns([4,1.1,1.1,1.6])
                with a:
                    st.markdown(f"**{k['title']}**")
                    st.caption(k["description"] or "Business knowledge source")
                    if k["tags"]: st.caption(" · ".join(k["tags"]))
                with b: st.caption(k["type"])
                with c: st.caption(k["status"])
                with d:
                    x1,x2=st.columns(2)
                    with x1:
                        if st.button("Open",key=f"open_k_{kid}",use_container_width=True):
                            st.session_state[f"view_knowledge_{kid}"]=True
                            st.rerun()
                    with x2:
                        if can("edit"):
                            if st.button("Edit",key=f"edit_btn_{kid}",use_container_width=True):
                                st.session_state[edit_key]=True
                                st.rerun()

                if st.session_state.get(f"view_knowledge_{kid}"):
                    st.markdown("#### Knowledge details")
                    st.caption(f"Source: {k.get('source') or 'Manual note'} · Updated: {k.get('updated_at','')}")
                    st.text_area("Saved content",value=k.get("content",""),height=260,key=f"view_content_{kid}",disabled=True)
                    if st.button("Close",key=f"close_k_{kid}"):
                        st.session_state.pop(f"view_knowledge_{kid}",None)
                        st.rerun()

                if st.session_state.get(edit_key) and can("edit"):
                    st.markdown("#### Edit knowledge")
                    with st.form(f"knowledge_edit_form_{kid}"):
                        new_title=st.text_input("Title",value=k["title"])
                        type_options=["Policy","FAQ","Guide","Document","Product info","Note","Other"]
                        current_type=k.get("type","Document")
                        new_kind=st.selectbox("Type",type_options,index=type_options.index(current_type) if current_type in type_options else 0)
                        new_tags=st.text_input("Tags",value=", ".join(k.get("tags",[])))
                        new_text=st.text_area("Content",value=k.get("content",""),height=260)
                        save_edit=st.form_submit_button("Save changes",type="primary",use_container_width=True)
                    if save_edit:
                        result=edit_knowledge_item(kid,new_title,new_kind,new_tags,new_text)
                        if result.get("duplicate"):
                            st.warning(result["message"])
                        elif result.get("ok"):
                            st.session_state.notice=f"Knowledge '{new_title}' updated and re-indexed successfully."
                            st.session_state.pop(edit_key,None)
                            st.rerun()
                        else:
                            st.error(result.get("error","Knowledge could not be updated."))
                    if st.button("Cancel edit",key=f"cancel_edit_{kid}"):
                        st.session_state.pop(edit_key,None)
                        st.rerun()

                if can("edit"):
                    if st.button("Delete",key=f"delete_btn_{kid}"):
                        st.session_state[delete_key]=True
                        st.rerun()
                    if st.session_state.get(delete_key):
                        st.error(
                            f"Delete '{k['title']}' permanently? Its stored content and indexed search data will be removed."
                        )
                        y1,y2=st.columns(2)
                        with y1:
                            if st.button("Yes, delete knowledge",type="primary",key=f"yes_delete_{kid}",use_container_width=True):
                                result=remove_knowledge_item(kid)
                                if result.get("ok"):
                                    st.session_state.pop(delete_key,None)
                                    st.session_state.pop(edit_key,None)
                                    st.session_state.pop(f"view_knowledge_{kid}",None)
                                    st.session_state.notice=f"Knowledge '{result['title']}' deleted successfully."
                                    st.rerun()
                                else:
                                    st.error(result.get("error","Knowledge could not be deleted."))
                        with y2:
                            if st.button("Cancel",key=f"cancel_delete_{kid}",use_container_width=True):
                                st.session_state.pop(delete_key,None)
                                st.rerun()

# ---------- Ask Brain ----------
elif page == "Ask Brain":
    page_header("Ask Business Brain","Ask questions about how your business works. Answers are grounded in your stored knowledge.","AI workspace")
    if not st.session_state.chat:
        st.markdown("<div class='brain-hero'><div class='brain-mark'>✦</div><h2>Your business, remembered.</h2><p>Ask about processes, policies, responsibilities, requirements, or related documents.</p></div>",unsafe_allow_html=True)
        st.markdown("### Suggested questions")
        qs=["How does our order process work?","What information is required before creating a new order?","Who handles customer complaints?","What should I do after receiving a custom cake order?"]
        qcols=st.columns(2)
        for i,q in enumerate(qs):
            with qcols[i%2]:
                if st.button(q,key=f"suggest_{i}",use_container_width=True): st.session_state.pending_question=q; st.rerun()
    for message in st.session_state.chat:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                st.markdown("**Sources**")
                for source in message["sources"]: source_card(source)
    pending=st.session_state.pop("pending_question",None); question=st.chat_input("Ask Business Brain…") or pending
    if question:
        st.session_state.chat.append({"role":"user","content":question})
        with st.chat_message("user"): st.markdown(question)
        with st.chat_message("assistant"):
            with st.spinner("Business Brain is routing your request…"):
                try:
                    business_id = current_business_id()
                    route_result = route_request(question, business_id)
                    route = route_result.get("route", "unknown") if isinstance(route_result, dict) else str(route_result)

                    if route == "operations":
                        result = execute_operation(
                            question,
                            business_id,
                            int((st.session_state.get("user") or {}).get("id") or 0),
                        )

                    elif route == "sale":
                        result = {
                            "ok": True,
                            "answer": "Ye sale request hai. **Smart Sale** page par isi order ko type/speak karein; wahan Smart Sale Agent catalog, price, stock aur cart ko handle karega.",
                            "sources": [],
                        }

                    elif route == "receipt":
                        result = {
                            "ok": True,
                            "answer": "Ye receipt-verification request hai. **Smart Sale → Receipt Verification** workflow mein receipt upload karein; Receipt Agent saved order ke against receipt ko verify karega.",
                            "sources": [],
                        }

                    elif route == "knowledge":
                        with st.spinner("Knowledge Agent is searching your Business Brain…"):
                            result = answer_knowledge_question(
                                question,
                                conversation=st.session_state.chat,
                                business_id=business_id,
                            )

                    else:
                        result = {
                            "ok": True,
                            "answer": "Main is request ko confidently classify nahi kar saka. Aap stock, sales, orders, suppliers, receipts, policies ya processes ke bare mein pooch sakte hain.",
                            "sources": [],
                        }

                    if result["ok"]:
                        st.markdown(result["answer"])
                        if result["sources"]:
                            st.markdown("**Sources**")
                            for source in result["sources"]:
                                source_card(source)
                        st.session_state.chat.append({
                            "role": "assistant",
                            "content": result["answer"],
                            "sources": result["sources"]
                        })
                    else:
                        st.error(result["error"])
                        st.session_state.chat.append({
                            "role": "assistant",
                            "content": result["error"],
                            "sources": []
                        })
                except Exception:
                    st.error("I couldn't process that request right now. Please try again.")
                    st.session_state.chat.append({
                        "role": "assistant",
                        "content": "I couldn't process that request right now. Please try again.",
                        "sources": []
                    })

# ---------- Smart Sale ----------
elif page == "Smart Sale":
    business_id = current_business_id()
    page_header("Smart Sale", "Speak or type an order. Every requested item stays visible with price and stock status.", "Sales Agent")
    st.markdown("<div class='hero'><div class='hero-title'>Sell in one simple flow.</div><div class='hero-copy'>Capture → match catalog → check stock & price → fix issues here → confirm → receipt.</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([1.25, .9], gap="large")
    with col1:
        st.markdown("### 1 · Capture order")
        audio = st.audio_input("🎙️ Speak Order", key="sale_audio")
        if audio and st.button("Transcribe voice order", use_container_width=True):
            try:
                with st.spinner("Transcribing order…"):
                    transcript = transcribe_audio_to_text(audio)
                    st.session_state.sale_input_value = transcript
                    st.session_state.sale_input = transcript
                st.success("Voice order transcribed. Review it before pricing.")
            except Exception:
                st.error("I couldn't transcribe that recording. Please try again or type the order.")
        if st.session_state.get("sale_input_value"):
            st.markdown(f"<div class='premium-card' style='margin:.55rem 0'><div class='eyebrow'>I understood</div><div style='font-size:1.05rem;font-weight:650;margin-top:.25rem'>{st.session_state.sale_input_value}</div><div class='muted'>Review the transcript, then click Understand Order.</div></div>",unsafe_allow_html=True)
        order = st.text_area("⌨️ Type Order", value=st.session_state.get("sale_input_value", ""), placeholder="1 Pepsi, 2 tissue aur 1 Surf", height=105, key="sale_input")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Understand Order", type="primary", use_container_width=True) and order.strip():
                try:
                    # A new captured request always replaces the active sale.
                    # This prevents a previous cart/unknown item from leaking into
                    # the next order when routing or parsing fails.
                    reset_sale_workflow(clear_last_sale=True)
                    route = route_request(order, business_id)
                    if route["route"] != "sale":
                        st.warning(f"This request looks like a {route['route']} request. Please use the matching workflow.")
                    else:
                        result = execute_sale_request(order, business_id)
                        st.session_state.sale_missing_price = result.get("missing_price", [])
                        st.session_state.sale_unknown_items = result.get("unknown_items", [])
                        st.session_state.sale_cart = result.get("cart", [])
                        st.session_state.sale_route = route
                        st.session_state.sale_input_value = order
                        st.session_state.sale_input = order
                        if not st.session_state.sale_cart and not st.session_state.sale_unknown_items:
                            st.warning("I couldn't match any product in your shop catalog. Add the product in Shop Catalog or try again.")
                        else:
                            st.success("Order understood. Every matched item is shown below with its saved price and stock.")
                except Exception:
                    reset_sale_workflow(clear_last_sale=True)
                    st.error("I couldn't build the order. Please check the product names and quantities.")
        with c2:
            if st.button("Clear Cart", use_container_width=True):
                reset_sale_workflow(clear_last_sale=True)
                st.rerun()

        unknown_items = st.session_state.get("sale_unknown_items", []) or []
        if unknown_items:
            st.markdown("### Unresolved products")
            for unknown in unknown_items:
                name = str(unknown.get("name", "Unknown product")).strip() or "Unknown product"
                qty = float(unknown.get("quantity", 0) or 0)
                st.warning(f"**{name.title()} × {qty:g} — Unknown product**\n\nThis product is not in the catalog yet. Add it to Inventory before completing the sale.")

        if st.session_state.sale_cart:
            st.markdown("### 2 · Review order")
            st.caption("Every requested item stays visible. Price and stock are checked from your shop database before confirmation.")
            refreshed=[]
            missing_price=[]
            stock_errors=[]
            for item in st.session_state.sale_cart:
                product = next((x for x in list_products(business_id) if int(x["id"]) == int(item["product_id"])), None)
                if not product:
                    continue
                qty=float(item.get("quantity",0) or 0)
                price=product.get("price")
                stock=float(product.get("stock_quantity",0) or 0)
                unit=product.get("unit") or "unit"
                subtotal=(qty*float(price)) if price is not None else None
                refreshed_item={**item,"name":product["name"],"quantity":qty,"unit_price":(float(price) if price is not None else None),"subtotal":subtotal,"unit":unit,"stock_quantity":stock}
                refreshed.append(refreshed_item)
                if price is None: missing_price.append(product["name"])
                if qty > stock: stock_errors.append(f"{product['name']}: requested {qty:g}, available {stock:g} {unit}")

                with st.container(border=True):
                    h1,h2,h3=st.columns([2.5,1.2,1.3])
                    with h1:
                        st.markdown(f"**{product['name']}**")
                        st.caption(f"Requested × {qty:g} · {unit}")
                    with h2:
                        if price is None:
                            st.markdown("**PRICE**")
                            new_price=st.number_input("Set price", min_value=0.0, step=1.0, value=0.0, key=f"sale_price_{product['id']}", label_visibility="collapsed")
                            if st.button("Save price", key=f"save_sale_price_{product['id']}", use_container_width=True):
                                if new_price <= 0:
                                    st.error("Enter a real selling price greater than 0.")
                                else:
                                    update_product(product["id"], price=float(new_price), business_id=business_id)
                                    log_activity("Product price updated", f"{product['name']} · Rs. {new_price:,.2f}", st.session_state.user["name"], business_id)
                                    st.success("Price saved.")
                                    st.rerun()
                        else:
                            st.markdown("**PRICE**")
                            st.markdown(f"Rs. {float(price):,.2f}")
                            with st.popover("Edit price"):
                                edited_price=st.number_input("Selling price", min_value=0.0, step=1.0, value=float(price), key=f"edit_sale_price_{product['id']}")
                                if st.button("Save", key=f"save_edit_price_{product['id']}", use_container_width=True):
                                    if edited_price <= 0: st.error("Enter a price greater than 0.")
                                    else:
                                        update_product(product["id"], price=float(edited_price), business_id=business_id)
                                        st.success("Price updated.")
                                        st.rerun()
                    with h3:
                        st.markdown("**STOCK**")
                        if stock <= 0:
                            st.error(f"0 {unit} · Out of stock")
                        elif qty > stock:
                            st.warning(f"{stock:g} {unit} · Not enough")
                        else:
                            st.success(f"{stock:g} {unit} · In stock")
                    if price is None:
                        st.warning("Price not set. Enter the real selling price above; Business Brain will not invent it.")
                    elif qty > stock:
                        st.warning(f"Not enough stock. Reduce the quantity or update stock before confirming.")
                    else:
                        st.caption(f"Line total · Rs. {subtotal:,.2f}")
            st.session_state.sale_cart=refreshed
            priced=[x for x in refreshed if x.get("unit_price") is not None]
            total=round(sum(float(x["subtotal"]) for x in priced),2)
            ready=(len(refreshed)>0 and not unknown_items and not missing_price and not stock_errors and len(priced)==len(refreshed))
            if missing_price or stock_errors:
                st.warning("Sale is not ready yet. Fix the price and stock issues above. You do not need to leave this page.")
            st.markdown(f"<div class='premium-card'><div class='eyebrow'>Deterministic total</div><div class='big-number'>{('Rs. '+format(total,',.2f')) if ready else 'Pending price / stock checks'}</div><div class='muted'>Calculated by Python from the saved shop prices.</div></div>", unsafe_allow_html=True)
            edit = st.text_input("Edit current order", placeholder="Tissue 3 kar do", key="cart_edit")
            if st.button("Apply Edit", use_container_width=True) and edit.strip():
                try:
                    edited=apply_cart_edit(st.session_state.sale_cart, edit, business_id)
                    if not edited["changed"]: st.warning("I couldn't match that edit to a product in the current order.")
                    else: st.session_state.sale_cart=edited["cart"]; st.rerun()
                except Exception: st.error("I couldn't apply that order edit. Try a quantity such as 'Tissue 3 kar do'.")
            confirm = st.button("Confirm Sale", type="primary", use_container_width=True, disabled=not ready)
            if confirm:
                try:
                    import uuid
                    ref=f"BB-{uuid.uuid4().hex[:8].upper()}"
                    from database_tools import save_sale
                    sale_id=save_sale(ref,total,st.session_state.sale_cart,st.session_state.user["id"],business_id)
                    st.session_state.sale_last_id=sale_id
                    reset_sale_workflow(clear_last_sale=False)
                    log_activity("Sale confirmed", f"{ref} · Rs. {total:,.2f}", st.session_state.user["name"], business_id)
                    st.success(f"Sale {ref} saved successfully.")
                    st.rerun()
                except ValueError as exc: st.error(str(exc))
                except Exception: st.error("Sale could not be saved. Please try again.")

    with col2:
        st.markdown("### 3 · Sale receipt")
        st.caption("Your confirmed order is shown here first. Upload a separate receipt below if you want Business Brain to verify it against this sale.")
        if st.session_state.sale_last_id:
            sale=get_sale(st.session_state.sale_last_id,business_id)
            if sale:
                st.markdown("<div class='receipt-card'><div class='receipt-head'><div><div class='receipt-title'>SALE CONFIRMED</div><div class='muted'>Sale #" + str(sale['id']) + " · " + str(sale['created_at']) + "</div></div><div class='receipt-ref'>" + str(sale['transaction_ref']) + "</div></div>", unsafe_allow_html=True)
                for item in sale["items"]:
                    st.markdown(f"<div class='receipt-row'><span><b>{item['name']}</b> × {float(item['quantity']):g}<br><span class='muted'>Rs. {float(item['unit_price']):,.2f} each</span></span><b>Rs. {float(item['subtotal']):,.2f}</b></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='receipt-total'><span>Total</span><span>Rs. {float(sale['total']):,.2f}</span></div></div>", unsafe_allow_html=True)
                st.download_button("⬇️ Download Receipt", data=receipt_download_text(sale), file_name=f"{sale['transaction_ref']}_receipt.txt", mime="text/plain", use_container_width=True, key=f"download_receipt_{sale['id']}")
            receipt=st.file_uploader("Verify an uploaded receipt",type=["png","jpg","jpeg","webp"],key="receipt_upload")
            if receipt and st.button("Verify Receipt",use_container_width=True):
                try:
                    expected=[{"product_id":x["product_id"],"name":x["name"],"quantity":x["quantity"],"unit_price":x["unit_price"]} for x in sale["items"]]
                    result=verify_receipt(receipt.getvalue(),receipt.type,expected,sale["total"])
                    from database import save_receipt_verification
                    save_receipt_verification(sale["id"],result.get("status","Unclear"),result.get("extracted",{}),result.get("mismatches",[]),st.session_state.user["id"],business_id)
                    if result.get("status")=="Match": st.success("Receipt matches the saved order.")
                    elif result.get("status")=="Unclear": st.warning("I couldn't read part of the receipt clearly. Please upload a clearer image or verify manually.")
                    else: st.warning("Possible mismatch detected. Please verify.")
                    for mismatch in result.get("mismatches",[]): st.markdown(f"- {mismatch.get('message','Please verify this receipt detail.')}")
                except Exception: st.error("Receipt verification could not be completed. Please try a clearer image.")
        else:
            st.info("Confirm the order first. The saved sale receipt will appear here automatically.")

# ---------- Inventory ----------
elif page == "Inventory":
    business_id = current_business_id()
    page_header("Inventory", "Edit prices and stock directly here. You do not need to leave the page while taking an order.", "Shop Catalog")
    products = list_products(business_id)

    top1, top2 = st.columns([2.2, 1])
    with top1:
        search = st.text_input("Search products", placeholder="e.g. flour, papad, sugar", key="inventory_search")
    with top2:
        st.markdown("<div class='inventory-label' style='margin-top:1.9rem'>Catalog</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='inventory-meta'>{len(products)} active product(s)</div>", unsafe_allow_html=True)

    if search.strip():
        q = search.strip().lower()
        products = [p for p in products if q in str(p.get("name","")).lower() or q in str(p.get("aliases","")).lower()]

    if not products:
        empty_state("No products found", "Add a product or change your search.")
    else:
        for product in products:
            stock = float(product.get("stock_quantity", 0) or 0)
            minimum = float(product.get("minimum_stock", 0) or 0)
            price = product.get("price")
            unit = product.get("unit") or "unit"
            if stock <= 0:
                stock_class, stock_text = "stock-out", f"0 {unit} · Out of stock"
            elif stock <= minimum:
                stock_class, stock_text = "stock-low", f"{stock:g} {unit} · Low stock"
            else:
                stock_class, stock_text = "stock-good", f"{stock:g} {unit} · In stock"

            with st.container(border=True):
                st.markdown(f"<div class='inventory-title'>{product['name']}</div><div class='inventory-meta'>Current status: <span class='{stock_class}'>{stock_text}</span> · Minimum {minimum:g} {unit}</div>", unsafe_allow_html=True)
                st.markdown("<div style='height:.55rem'></div>", unsafe_allow_html=True)
                with st.form(f"inventory_edit_{product['id']}"):
                    c1, c2, c3, c4 = st.columns([1.15, 1.15, 1, 1.05])
                    with c1:
                        st.markdown("<div class='inventory-label'>Selling price (Rs.)</div>", unsafe_allow_html=True)
                        new_price = st.number_input("Selling price", min_value=0.0, step=1.0, value=float(price) if price is not None else 0.0, key=f"inv_price_{product['id']}", label_visibility="collapsed")
                    with c2:
                        st.markdown("<div class='inventory-label'>Current stock</div>", unsafe_allow_html=True)
                        new_stock = st.number_input("Current stock", min_value=0.0, step=1.0, value=stock, key=f"inv_stock_{product['id']}", label_visibility="collapsed")
                    with c3:
                        st.markdown("<div class='inventory-label'>Unit</div>", unsafe_allow_html=True)
                        units = ["unit","piece","pack","kg","liter"]
                        current_unit = unit if unit in units else "unit"
                        new_unit = st.selectbox("Unit", units, index=units.index(current_unit), key=f"inv_unit_{product['id']}", label_visibility="collapsed")
                    with c4:
                        st.markdown("<div class='inventory-label'>Minimum stock</div>", unsafe_allow_html=True)
                        new_min = st.number_input("Minimum stock", min_value=0.0, step=1.0, value=minimum, key=f"inv_min_{product['id']}", label_visibility="collapsed")
                    save = st.form_submit_button("Save changes", type="primary", use_container_width=True)
                if save:
                    try:
                        update_product(product["id"], price=float(new_price), stock_quantity=float(new_stock), unit=new_unit, minimum_stock=float(new_min), business_id=business_id)
                        log_activity("Product updated", f"{product['name']} · price Rs. {new_price:,.2f} · stock {new_stock:g} {new_unit}", st.session_state.user["name"], business_id)
                        st.success(f"{product['name']} updated successfully.")
                        st.rerun()
                    except Exception:
                        st.error("Product could not be updated. Please check the price and stock values.")

    st.markdown("### Add products")
    st.caption("Add one product per line. Business Brain will create the catalog records without inventing prices.")
    with st.form("bulk_add_inventory"):
        names = st.text_area("Product names", placeholder="Papad\nNimko\nBiscuits", height=100)
        add = st.form_submit_button("Add products", use_container_width=True)
    if add:
        try:
            result = bulk_add_products(names.splitlines(), business_id)
            created = result.get("created", [])
            existing = result.get("existing", [])
            if created:
                st.success(f"Added: {', '.join(created)}. Set their real prices above before selling.")
            if existing:
                st.info(f"Already in catalog: {', '.join(existing)}")
            if not created and not existing:
                st.warning("Enter at least one product name.")
            st.rerun()
        except Exception:
            st.error("Products could not be added. Please try again.")


# ---------- Process Library ----------
elif page == "Processes":
    page_header("Processes","View and manage how work gets done.","Process library")
    processes=list_processes()
    total=len(processes); active=sum(1 for p in processes if p["status"]=="Active"); cats=len(set(p["category"] for p in processes)); recent=sum(1 for p in processes if p.get("updated_at","")[:10] >= __import__('datetime').datetime.now().strftime('%Y-%m-%d'))
    m=st.columns(4); 
    for col,(lab,val,sub) in zip(m,[("Total",total,"Documented processes"),("Active",active,"Currently in use"),("Categories",cats,"Process areas"),("Updated today",recent,"Recent changes")]):
        with col: stat_card(lab,val,sub)
    st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True)
    c1,c2=st.columns([2,1]);
    with c1: search=st.text_input("Search processes",placeholder="Search by name, purpose or category",label_visibility="collapsed")
    with c2: category=st.selectbox("Category",["All categories"]+sorted(set(p["category"] for p in processes)),label_visibility="collapsed")
    filtered=[p for p in processes if (not search or search.lower() in (p["name"]+" "+p["description"]+" "+p["category"]).lower()) and (category=="All categories" or p["category"]==category)]
    if not filtered: empty_state("No matching processes","Try a different search or category.")
    for p in filtered:
        with st.container(border=True):
            a,b,c,d=st.columns([4,1.2,1.2,1])
            with a: st.markdown(f"**{p['name']}**"); st.caption(p["description"] or "No description")
            with b: st.caption(p["category"])
            with c: st.caption(p["status"]); st.caption(p["updated_at"][:10])
            with d:
                if st.button("Open",key=f"view_{p['id']}"): st.session_state.selected_process=p["id"]; st.session_state.page="Process detail"; st.rerun()

# ---------- Process Detail / Versioning ----------
elif page == "Process detail":
    p=get_process(st.session_state.get("selected_process"))
    if not p: st.error("Process not found.")
    else:
        page_header(p["name"],p["description"],"Process")
        versions=get_process_versions(p["id"])
        st.caption(f"{p['category']} · {p['status']} · Owner: {p['owner']} · Updated {p['updated_at']} · Version {versions[0]['version'] if versions else 1}")
        if can("edit"):
            e1,e2=st.columns([1,1])
            with e1:
                if st.button("Edit process",type="primary",use_container_width=True): st.session_state.edit_process=True; st.rerun()
            with e2:
                if st.button("Delete process",use_container_width=True):
                    st.session_state[f"confirm_delete_process_{p['id']}"] = True

            process_delete_key = f"confirm_delete_process_{p['id']}"
            if st.session_state.get(process_delete_key):
                st.error(
                    f"Delete '{p['name']}' permanently? This will remove the process, "
                    "its version history, and its indexed search data. This cannot be undone."
                )
                d1,d2=st.columns(2)
                with d1:
                    if st.button("Yes, delete process",type="primary",use_container_width=True):
                        process_name = p["name"]
                        if delete_process(p["id"]):
                            log_activity("Process deleted",f"{process_name} (ID {p['id']})",st.session_state.user["name"])
                            st.session_state.pop(process_delete_key, None)
                            st.session_state.pop("selected_process", None)
                            st.session_state.pop("edit_process", None)
                            st.session_state.notice = f"Process '{process_name}' deleted successfully."
                            st.session_state.page = "Processes"
                            st.rerun()
                        else:
                            st.error("The process could not be deleted.")
                with d2:
                    if st.button("Cancel",use_container_width=True):
                        st.session_state.pop(process_delete_key, None)
                        st.rerun()
        if st.session_state.get("edit_process"):
            st.markdown("### Edit current version")
            with st.form("edit_process_form"):
                name=st.text_input("Process name",p["name"]); category=st.text_input("Category",p["category"]); purpose=st.text_area("Purpose",p["description"]); trigger=st.text_input("Trigger",p["trigger"]); inputs=st.text_area("Required inputs","\n".join(p["inputs"])); roles=st.text_area("People / roles","\n".join(p["roles"])); steps=st.text_area("Step-by-step workflow","\n".join([f"{i+1}. {x.get('action','')}" for i,x in enumerate(p["steps"])]),height=220); decisions=st.text_area("Decisions / conditions","\n".join(p["decisions"])); exceptions=st.text_area("Exceptions / warnings","\n".join(p["exceptions"])); output=st.text_area("Expected output",p["output"]); tags=st.text_input("Tags",", ".join(p["tags"])); note=st.text_input("Change note","Updated SOP")
                save=st.form_submit_button("Save new version",type="primary")
            if save:
                updated={"name":name.strip(),"description":purpose.strip(),"category":category.strip() or "Operations","owner":p["owner"],"status":p["status"],"trigger":trigger.strip(),"inputs":[x.strip() for x in inputs.splitlines() if x.strip()],"roles":[x.strip() for x in roles.splitlines() if x.strip()],"steps":[{"action":x.strip()} for x in steps.splitlines() if x.strip()],"decisions":[x.strip() for x in decisions.splitlines() if x.strip()],"exceptions":[x.strip() for x in exceptions.splitlines() if x.strip()],"output":output.strip(),"tags":[x.strip() for x in tags.split(",") if x.strip()]}
                if _save_process_from_editor(updated,p["id"],note): st.session_state.edit_process=False; st.session_state.notice="New SOP version saved and re-indexed."; st.rerun()
        tabs=st.tabs(["Overview","Workflow","Decisions & exceptions","Version history"])
        with tabs[0]:
            c1,c2=st.columns(2)
            with c1:
                st.markdown("#### Trigger")
                st.write(p["trigger"] or "Not specified")
                st.markdown("#### Required inputs")
                for x in p["inputs"]:
                    st.markdown(f"- {x}")
            with c2:
                st.markdown("#### People / roles")
                for x in p["roles"]:
                    st.markdown(f"- {x}")
                st.markdown("#### Expected output")
                st.write(p["output"] or "Not specified")
        with tabs[1]:
            for i,step in enumerate(p["steps"],1):
                st.markdown(f"<div class='step-row'><span class='step-number'>{i}</span><div><b>{step.get('action','')}</b></div></div>",unsafe_allow_html=True)
        with tabs[2]:
            st.markdown("#### Decision points")
            for x in p["decisions"]:
                st.markdown(f"- {x}")
            st.markdown("#### Exceptions & warnings")
            for x in p["exceptions"]:
                st.markdown(f"- {x}")
        with tabs[3]:
            if not versions: st.info("No version history yet.")
            for v in versions:
                with st.container(border=True):
                    a,b,c=st.columns([1,2,2]);
                    with a: st.markdown(f"**Version {v['version']}**")
                    with b: st.caption(f"{v['changed_by']} · {v['created_at']}")
                    with c: st.caption(v["change_note"] or "No change note")
                    snapshot = v.get("snapshot") or {}
                    with st.expander(f"Open version {v['version']}"):
                        st.markdown(f"**Purpose:** {snapshot.get('description') or 'Not specified'}")
                        st.markdown(f"**Trigger:** {snapshot.get('trigger') or 'Not specified'}")
                        st.markdown("**Required inputs**")
                        for item in snapshot.get("inputs", []) or []:
                            st.markdown(f"- {item}")
                        st.markdown("**People / roles**")
                        for item in snapshot.get("roles", []) or []:
                            st.markdown(f"- {item}")
                        st.markdown("**Workflow**")
                        for i, step in enumerate(snapshot.get("steps", []) or [], 1):
                            action = step.get("action", "") if isinstance(step, dict) else str(step)
                            st.markdown(f"{i}. {action}")
                        st.markdown("**Decisions**")
                        for item in snapshot.get("decisions", []) or []:
                            st.markdown(f"- {item}")
                        st.markdown("**Exceptions / warnings**")
                        for item in snapshot.get("exceptions", []) or []:
                            st.markdown(f"- {item}")
                        st.markdown(f"**Expected output:** {snapshot.get('output') or 'Not specified'}")
                    if can("edit"):
                        latest_version = versions[0]["version"] if versions else v["version"]
                        action_cols = st.columns(2)

                        with action_cols[0]:
                            if st.button(
                                f"Restore v{v['version']}",
                                key=f"restore_{p['id']}_{v['version']}",
                                use_container_width=True,
                            ):
                                if restore_process_version(
                                    p["id"],
                                    v["version"],
                                    st.session_state.user["id"],
                                    st.session_state.user["name"],
                                ):
                                    index_process(p["id"],v["snapshot"])
                                    log_activity(
                                        "Process version restored",
                                        f"{p['name']} → v{v['version']}",
                                        st.session_state.user["name"],
                                    )
                                    st.session_state.notice = (
                                        f"Version {v['version']} restored as a new version."
                                    )
                                    st.rerun()

                        with action_cols[1]:
                            if int(v["version"]) == int(latest_version):
                                st.button(
                                    "Delete",
                                    key=f"delete_disabled_{p['id']}_{v['version']}",
                                    disabled=True,
                                    use_container_width=True,
                                )
                            elif st.button(
                                f"Delete v{v['version']}",
                                key=f"delete_{p['id']}_{v['version']}",
                                use_container_width=True,
                            ):
                                st.session_state[
                                    f"confirm_delete_{p['id']}_{v['version']}"
                                ] = True

                        confirm_key = f"confirm_delete_{p['id']}_{v['version']}"
                        if st.session_state.get(confirm_key):
                            st.warning(
                                f"Delete Version {v['version']} permanently? "
                                "This removes only this historical version."
                            )
                            confirm_cols = st.columns(2)
                            with confirm_cols[0]:
                                if st.button(
                                    "Yes, delete version",
                                    key=f"confirm_yes_{p['id']}_{v['version']}",
                                    type="primary",
                                    use_container_width=True,
                                ):
                                    ok, message = _delete_old_process_version(
                                        p["id"], v["version"]
                                    )
                                    if ok:
                                        log_activity(
                                            "Process version deleted",
                                            f"{p['name']} · v{v['version']}",
                                            st.session_state.user["name"],
                                        )
                                        st.session_state.pop(confirm_key, None)
                                        st.session_state.notice = (
                                            f"Version {v['version']} deleted."
                                        )
                                        st.rerun()
                                    else:
                                        st.error(message)

                            with confirm_cols[1]:
                                if st.button(
                                    "Cancel",
                                    key=f"confirm_no_{p['id']}_{v['version']}",
                                    use_container_width=True,
                                ):
                                    st.session_state.pop(confirm_key, None)
                                    st.rerun()

# ---------- Daily Operations ----------
elif page == "Daily Operations":
    business_id=current_business_id()
    ops=get_daily_operations(business_id)
    page_header("Daily Operations","See what needs attention today without digging through the database.","Operations")
    cols=st.columns(4)
    stats=[("Today sales",f"Rs. {ops['sales_total']:,.0f}",f"{ops['sales_count']} confirmed sale(s)"),("Low stock",len(ops['low_stock']),"Products at or below minimum"),("Pending supplier",ops['pending_supplier_orders'],"Draft / approval actions"),("Recent sales",len(ops['recent_sales']),"Latest transactions")]
    for c,(a,b,d) in zip(cols,stats):
        with c: stat_card(a,b,d)
    st.markdown("### Needs attention")
    if ops['low_stock']:
        for item in ops['low_stock']:
            st.warning(f"{item['name']}: {float(item['stock_quantity']):g} {item['unit']} available; minimum is {float(item['minimum_stock']):g}.")
    else: st.success("No low-stock items right now.")
    st.markdown("### Recent sales")
    for sale in ops['recent_sales']:
        st.markdown(f"<div class='premium-card' style='margin:.45rem 0'><b>{sale['transaction_ref']}</b><div class='muted'>Rs. {sale['total']:,.2f} · {sale['status']} · {sale['created_at']}</div></div>",unsafe_allow_html=True)
    if is_manager_or_owner():
        st.markdown("### Supplier actions")
        for order in list_supplier_orders(business_id,20):
            with st.container(border=True):
                st.write(f"**Order #{order['id']} · {order['supplier_name']}**")
                st.caption(f"Status: {order['status']} · {order['created_at']}")
                if order['status'] in ('Draft','Pending Approval') and st.button("Approve",key=f"approve_ops_{order['id']}"):
                    if approve_supplier_order(order['id'],st.session_state.user['id'],business_id):
                        log_activity("Supplier order approved",f"Order #{order['id']} · {order['supplier_name']}",st.session_state.user['name'])
                        st.success("Supplier order approved.")
                        st.rerun()

# ---------- Receipts ----------
elif page == "Receipts":
    business_id=current_business_id()
    page_header("Receipts","Review saved sales and verify a customer receipt against the original order.","Receipt Agent")
    sales=[]
    for item in get_daily_operations(business_id)['recent_sales']:
        sales.append(item)
    if not sales:
        empty_state("No sales yet","Confirm a sale from Smart Sale first.")
    else:
        options={f"#{s['id']} · {s['transaction_ref']} · Rs. {s['total']:,.2f}":s['id'] for s in sales}
        label=st.selectbox("Select sale",list(options))
        sale=get_sale(options[label],business_id)
        if sale:
            st.markdown(f"<div class='receipt-card'><div class='receipt-head'><div><div class='receipt-title'>Sale Receipt</div><div class='muted'>{sale['created_at']}</div></div><div class='receipt-ref'>{sale['transaction_ref']}</div></div>",unsafe_allow_html=True)
            for item in sale['items']:
                st.markdown(f"<div class='receipt-row'><span>{item['name']} × {float(item['quantity']):g}</span><span>Rs. {float(item['subtotal']):,.2f}</span></div>",unsafe_allow_html=True)
            st.markdown(f"<div class='receipt-total'><span>Total</span><span>Rs. {float(sale['total']):,.2f}</span></div></div>",unsafe_allow_html=True)
            st.download_button("⬇️ Download Receipt",receipt_download_text(sale),file_name=f"{sale['transaction_ref']}_receipt.txt",mime="text/plain",use_container_width=True)
            uploaded=st.file_uploader("Upload receipt image for verification",type=['png','jpg','jpeg','webp'],key=f"receipt_upload_{sale['id']}")
            if uploaded and st.button("Verify Receipt",type="primary",use_container_width=True):
                try:
                    with st.spinner("Reading and comparing receipt…"):
                        expected=[{"product_id":x["product_id"],"name":x["name"],"quantity":x["quantity"],"unit_price":x["unit_price"]} for x in sale["items"]]
                        result=verify_receipt(uploaded.getvalue(),uploaded.type,expected,sale["total"])
                    st.session_state.receipt_result=result
                except Exception:
                    st.error("Receipt verification could not be completed. Please upload a clearer receipt image.")
            if st.session_state.get('receipt_result'):
                result=st.session_state.receipt_result
                status=result.get('status','Needs Review')
                if status == 'Match': st.success("Receipt matches the saved sale.")
                elif status == 'Mismatch': st.warning("Receipt and saved sale contain differences. Review the details below.")
                else: st.info("Receipt needs manual review.")
                for m in result.get('mismatches',[]): st.write("•",m)

# ---------- Suppliers ----------
elif page == "Suppliers":
    business_id=current_business_id()
    page_header("Suppliers","See suppliers and create reviewable reorder drafts from low-stock items.","Operations Agent")
    ops=get_daily_operations(business_id)
    low=ops['low_stock']
    if low:
        st.markdown("### Reorder suggestions")
        products=list_products(business_id)
        for item in low:
            product=next((p for p in products if int(p['id'])==int(item['id'])),None)
            if not product: continue
            supplier=find_supplier_for_product(product['id'],business_id)
            with st.container(border=True):
                st.write(f"**{product['name']}** · {float(product['stock_quantity']):g} {product['unit']} left")
                if supplier:
                    st.caption(f"Supplier: {supplier['name']} · contact: {supplier.get('contact','not provided')}")
                    qty=max(float(product['minimum_stock'])-float(product['stock_quantity']),1.0)
                    if is_manager_or_owner() and st.button(f"Create reorder draft ({qty:g} {product['unit']})",key=f"reorder_{product['id']}"):
                        try:
                            oid=create_supplier_order(supplier['id'],[{"product_id":product['id'],"quantity":qty,"unit_price":supplier.get('supplier_price')}],st.session_state.user['id'],business_id)
                            log_activity("Supplier order draft created",f"Order #{oid} · {supplier['name']} · {product['name']}",st.session_state.user['name'])
                            st.success(f"Draft #{oid} created. It still needs approval.")
                            st.rerun()
                        except Exception:
                            st.error("Supplier draft could not be created.")
                else: st.info("No supplier is linked to this product yet.")
    else: st.success("No low-stock reorder suggestions right now.")
    st.markdown("### Recent supplier orders")
    for order in list_supplier_orders(business_id,30):
        st.markdown(f"<div class='premium-card' style='margin:.45rem 0'><b>Order #{order['id']} · {order['supplier_name']}</b><div class='muted'>{order['status']} · {order['created_at']}</div></div>",unsafe_allow_html=True)

# ---------- Activity ----------
elif page == "Activity":
    page_header("Activity","See what was added or changed.","Workspace")
    for item in get_activity(100):
        st.markdown(f"<div class='activity-row'><div class='activity-dot'></div><div><b>{item['action']}</b><div class='muted'>{item['details']}</div><div class='tiny'>{item['created_at']}</div></div></div>",unsafe_allow_html=True)

# ---------- Settings ----------
elif page == "Settings":
    page_header("Settings", "Manage your workspace, team and access.", "Settings")
    if not can("settings"):
        st.info("Settings are available to the Owner role.")
    else:
        st.markdown("### Business profile")
        with st.form("settings"):
            name = st.text_input("Business name", business["name"])
            profile = st.text_area("Short profile", business["profile"], height=120)
            save = st.form_submit_button("Save changes", type="primary", use_container_width=True)
        if save:
            if not name.strip():
                st.error("Business name cannot be empty.")
            else:
                update_business(name.strip(), profile.strip())
                log_activity("Business profile updated", name.strip(), st.session_state.user["name"])
                st.session_state.notice = "Business profile updated successfully."
                st.rerun()

        st.markdown("### Team & roles")
        st.caption("Owner-only controls: create users, change roles, activate/deactivate accounts, and reset passwords.")
        users = list_users()
        if users:
            for u in users:
                with st.container(border=True):
                    h1, h2, h3 = st.columns([2.4, 1.2, 1.2])
                    with h1:
                        st.markdown(f"**{u['name']}**")
                        st.caption(f"@{u['username']} · Created {u['created_at']}")
                    with h2:
                        st.write(f"**{u['role']}**")
                        st.caption(u["status"])
                    with h3:
                        st.write("Active" if u["status"] == "Active" else "Inactive")

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        with st.form(f"edit_user_{u['id']}"):
                            new_name = st.text_input("Name", u["name"], key=f"name_{u['id']}")
                            new_role = st.selectbox("Role", ["Owner", "Manager", "Employee"], index=["Owner","Manager","Employee"].index(u["role"]), key=f"role_{u['id']}")
                            new_status = st.selectbox("Status", ["Active", "Inactive"], index=0 if u["status"] == "Active" else 1, key=f"status_{u['id']}")
                            update_btn = st.form_submit_button("Save user", use_container_width=True)
                        if update_btn:
                            try:
                                if u["id"] == st.session_state.user["id"] and new_status == "Inactive":
                                    st.error("You cannot deactivate the account you are currently using.")
                                else:
                                    update_user(u["id"], new_name, new_role, new_status)
                                    log_activity("User updated", f"@{u['username']} · {new_role} · {new_status}", st.session_state.user["name"])
                                    st.session_state.notice = f"User @{u['username']} updated successfully."
                                    st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                    with c2:
                        with st.form(f"reset_pw_{u['id']}"):
                            new_pw = st.text_input("New password", type="password", key=f"pw_{u['id']}")
                            confirm_pw = st.text_input("Confirm password", type="password", key=f"cpw_{u['id']}")
                            reset_btn = st.form_submit_button("Reset password", use_container_width=True)
                        if reset_btn:
                            if new_pw != confirm_pw:
                                st.error("Passwords do not match.")
                            else:
                                try:
                                    reset_user_password(u["id"], new_pw)
                                    log_activity("Password reset", f"@{u['username']}", st.session_state.user["name"])
                                    st.session_state.notice = f"Password reset for @{u['username']}."
                                    st.rerun()
                                except Exception as exc:
                                    st.error(str(exc))
                    with c3:
                        st.markdown("**Access**")
                        if u["id"] == st.session_state.user["id"]:
                            st.caption("Current account")
                        elif u["status"] == "Active":
                            st.caption("Can sign in")
                        else:
                            st.caption("Sign-in blocked")

        st.markdown("### Add team member")
        with st.form("new_user"):
            n = st.text_input("Full name", placeholder="Team member name")
            un = st.text_input("Username", placeholder="e.g. sara")
            pw = st.text_input("Temporary password", type="password", placeholder="At least 8 characters")
            role = st.selectbox("Role", ["Manager", "Employee"])
            add = st.form_submit_button("Create user", type="primary", use_container_width=True)
        if add:
            try:
                uid = create_user(n, un, pw, role)
                log_activity("User created", f"@{un.strip().lower()} · {role}", st.session_state.user["name"])
                st.session_state.notice = f"User @{un.strip().lower()} created successfully."
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("That username is already in use. Choose another username.")
            except Exception as exc:
                st.error(str(exc))

st.markdown("<div class='footer'>Business Brain · Phase 3 · Capture → Structure → Remember → Retrieve → Govern</div>",unsafe_allow_html=True)
