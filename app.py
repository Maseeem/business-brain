import sqlite3
import os
import streamlit as st
from dotenv import load_dotenv

from database import (
    init_db, seed_demo_data, seed_operational_data, get_business, list_processes, list_knowledge, get_activity,
    get_process, create_process, update_process, delete_process, get_process_versions, restore_process_version,
    authenticate_user, list_users, create_user, get_user, update_user, reset_user_password, update_business, log_activity, ensure_demo_users,
    get_daily_operations, create_sale, create_sale_items, get_sale, approve_supplier_order, list_supplier_orders,
    list_products, get_product_by_id, create_product, update_product, bulk_add_products, set_product_price,
    add_business_memory, list_business_memory, delete_business_memory,
)
from agent import generate_sop_from_inputs, answer_business_question, transcribe_audio_to_text
from coordinator_agent import route_request
from smart_sale_agent import build_cart, apply_cart_edit
from operations_agent import low_stock_items, supplier_draft, classify_operation_request
from knowledge_agent import answer as knowledge_answer
from receipt_agent import verify_receipt
from rag import ingest_knowledge_file, edit_knowledge_item, remove_knowledge_item, detect_knowledge_contradictions, index_process, bootstrap_index
from ui import inject_css, sidebar, page_header, stat_card, empty_state, source_card

load_dotenv()
init_db()
if os.getenv("SEED_DEMO_DATA", "true").lower() == "true":
    seed_demo_data()
    seed_operational_data()
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


def is_manager_or_owner():
    return (st.session_state.get("user") or {}).get("role") in {"Owner", "Manager"}

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
    if os.getenv("SEED_DEMO_DATA", "true").lower() == "true":
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
if "sale_last_id" not in st.session_state: st.session_state.sale_last_id = None
if "sale_input_value" not in st.session_state: st.session_state.sale_input_value = ""
if "sale_order_items" not in st.session_state: st.session_state.sale_order_items = []
if "sale_missing_price" not in st.session_state: st.session_state.sale_missing_price = []
if "sale_confirmed_notice" not in st.session_state: st.session_state.sale_confirmed_notice = ""

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
    business_id=current_business_id()
    ops=get_daily_operations(business_id)
    page_header("Good morning 👋", "The few things worth looking at today.", "Home")
    cols=st.columns(4)
    stats=[
        ("Today’s sales",f"Rs. {ops['sales_total']:,.0f}",f"{ops['sales_count']} sales"),
        ("Orders",ops["sales_count"],"Confirmed today"),
        ("Low stock",len(ops["low_stock"]),"Needs attention"),
        ("Pending",ops["pending_supplier_orders"],"Supplier actions"),
    ]
    for col,(label,value,sub) in zip(cols,stats):
        with col: stat_card(label,value,sub)
    st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True)
    st.markdown("### Quick actions")
    qcols=st.columns(3)
    actions=[("＋","New Sale","Speak or type a customer order.","Smart Sale"),("▦","Check Inventory","See products, prices and stock.","Inventory"),("🧾","Verify Receipt","Check a receipt against a confirmed sale.","Smart Sale")]
    for c,(icon,title,desc,target) in zip(qcols,actions):
        with c:
            st.markdown(f"<div class='action-card'><div class='action-icon'>{icon}</div><div class='action-title'>{title}</div><div class='action-desc'>{desc}</div></div>",unsafe_allow_html=True)
            if st.button(title,key=f"home_{target}_{title}",use_container_width=True): st.session_state.page=target; st.rerun()
    st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True)
    left,right=st.columns([1.25,1],gap="large")
    with left:
        st.markdown("### Needs attention")
        if not ops["low_stock"] and not ops["pending_supplier_orders"]:
            st.success("Nothing urgent right now.")
        for item in ops["low_stock"][:5]:
            stock=float(item.get("stock_quantity",item.get("stock",0)) or 0); minimum=float(item.get("minimum_stock",0) or 0); unit=item.get("unit") or "unit"
            st.markdown(f"<div class='premium-card' style='margin:.45rem 0'><span class='status-pill'>LOW STOCK</span><br><b>{item.get('name','Unknown product')}</b><div class='muted'>{stock:g} {unit} available · minimum {minimum:g}</div></div>",unsafe_allow_html=True)
        if ops["pending_supplier_orders"]:
            st.info(f"{ops['pending_supplier_orders']} supplier order(s) are waiting for review.")
    with right:
        st.markdown("### Recent sales")
        if not ops["recent_sales"]: empty_state("No sales yet","Your confirmed sales will appear here.")
        for sale in ops["recent_sales"][:5]:
            st.markdown(f"<div class='premium-card' style='margin:.45rem 0'><b>{sale['transaction_ref']}</b><div class='muted'>Rs. {sale['total']:,.2f} · {sale['created_at']}</div></div>",unsafe_allow_html=True)

# ---------- Smart Sale ----------
elif page == "Smart Sale":
    business_id = current_business_id()
    page_header("Smart Sale", "Speak or type an order. Every item stays visible with price and stock status before you confirm.", "Sales Agent")
    st.markdown("<div class='hero'><div class='hero-title'>Sell in one simple flow.</div><div class='hero-copy'>Coordinator → Smart Sale Agent → Product/Cart tools → database validation → human confirmation.</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='section-gap'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns([1.25, .9], gap="large")
    with col1:
        st.markdown("### 1 · Capture order")
        audio = st.audio_input("🎙️ Speak Order", key="sale_audio")
        if audio:
            try:
                audio_bytes = audio.getvalue()
                import hashlib
                audio_key = hashlib.sha256(audio_bytes).hexdigest()
                if st.session_state.get("sale_audio_key") != audio_key:
                    with st.spinner("Understanding your voice order…"):
                        transcript = transcribe_audio_to_text(audio)
                        st.session_state.sale_input_value = transcript
                        st.session_state.sale_input = transcript
                        st.session_state.sale_audio_key = audio_key
                        if transcript.strip():
                            result = build_cart(transcript, business_id)
                            st.session_state.sale_missing_price = result.get("missing_price", [])
                            st.session_state.sale_order_items = result.get("parsed_items", [])
                            st.session_state.sale_cart = result.get("cart", [])
                            st.session_state.sale_route = route_request(transcript)
                            st.session_state.sale_voice_understood = True
                            if result.get("missing_price"):
                                st.session_state.sale_voice_notice = "Price not set for: " + ", ".join(result["missing_price"]) + ". Open Shop Catalog and add the real selling price."
                            else:
                                st.session_state.sale_voice_notice = ""
            except Exception:
                st.error("I couldn't understand that recording. Please try again or type the order.")
        if st.session_state.get("sale_voice_notice"):
            st.warning(st.session_state.sale_voice_notice)
        if st.session_state.get("sale_input_value"):
            st.markdown(f"<div class='premium-card' style='margin:.55rem 0'><div class='eyebrow'>I understood</div><div style='font-size:1.05rem;font-weight:650;margin-top:.25rem'>{st.session_state.sale_input_value}</div><div class='muted'>The voice order has been converted into your cart. You can edit the text and press Understand Order if you want to change it.</div></div>",unsafe_allow_html=True)
        order = st.text_area("⌨️ Type Order", value=st.session_state.get("sale_input_value", ""), placeholder="1 Pepsi, 2 tissue aur 1 Surf", height=105, key="sale_input")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Understand Order", type="primary", use_container_width=True) and order.strip():
                try:
                    # Smart Sale is already the selected workflow. Do not let the
                    # general coordinator's LLM re-route a valid Urdu/Roman-Urdu sale
                    # back to an unrelated workflow. The sale parser/catalog remain the
                    # source of truth for product matching.
                    result = build_cart(order, business_id)
                    route = {"route": "sale", "reason": "Smart Sale workflow selected"}
                    st.session_state.sale_missing_price = result.get("missing_price", [])
                    st.session_state.sale_order_items = result.get("parsed_items", [])
                    st.session_state.sale_route = route
                    if not result["cart"]:
                        if result.get("missing_price"):
                            st.warning("These products are in your catalog but need real prices before they can be sold: " + ", ".join(result["missing_price"]) + ". Open Shop Catalog and set their prices.")
                        else:
                            st.warning("I couldn't match any product in your shop catalog. Add the product in Shop Catalog or try again.")
                    else:
                        st.session_state.sale_cart = result["cart"]
                        extra = (" Price missing for: " + ", ".join(result.get("missing_price",[])) + ".") if result.get("missing_price") else ""
                        if result.get("missing_price"):
                            st.warning("Order understood. Some items need prices: " + ", ".join(result["missing_price"]) + ". Set their real prices before confirming the sale.")
                        else:
                            st.success("Order understood. Prices were loaded from your shop catalog.")
                except Exception:
                    st.error("I couldn't build the cart. Please check the product names and quantities.")
        with c2:
            if st.button("Clear Cart", use_container_width=True):
                st.session_state.sale_cart = []
                st.session_state.sale_last_id = None
                st.session_state.sale_input_value = ""
                st.session_state.sale_input = ""
                st.session_state.sale_audio_key = None
                st.session_state.sale_voice_understood = False
                st.session_state.sale_voice_notice = ""
                st.session_state.sale_order_items = []
                st.rerun()
        order_items = st.session_state.get("sale_order_items", [])
        if order_items:
            st.markdown("### 2 · Review order")
            st.caption("Every requested item stays visible. Price and stock are checked from your shop database before confirmation.")
            blocked = False
            for entry in order_items:
                product = entry.get("product") or {}
                pid = int(product.get("id"))
                product = get_product_by_id(pid, business_id) or product
                name = product.get("name", "Unknown product")
                qty = float(entry.get("quantity") or 0)
                price = product.get("price")
                stock = float(product.get("stock_quantity") or 0)
                unit = product.get("unit") or "unit"
                price_missing = price is None
                out = stock <= 0
                insufficient = stock < qty
                status = "Price not set" if price_missing else ("Out of stock" if out else ("Not enough stock" if insufficient else "In stock"))
                status_class = "sale-item-warn" if (price_missing or out or insufficient) else "sale-item-good"
                if price_missing or out or insufficient: blocked = True
                left, mid, right = st.columns([2.4, 1.15, 1.65])
                with left:
                    st.markdown(f"<div class='sale-item-card'><div class='sale-item-name'>{name}</div><div class='sale-item-meta'>Requested × {qty:g} · {unit}</div></div>", unsafe_allow_html=True)
                with mid:
                    if price_missing:
                        new_price = st.number_input(f"Price · {name}", min_value=0.0, value=0.0, step=1.0, key=f"quick_price_{pid}", label_visibility="collapsed")
                        if st.button("Save price", key=f"save_quick_price_{pid}", use_container_width=True):
                            try:
                                set_product_price(pid, new_price, business_id)
                                log_activity("Product price updated", f"{name} · Rs. {new_price:,.2f}", st.session_state.user["name"], business_id)
                                st.success("Price saved")
                                st.rerun()
                            except Exception:
                                st.error("Price could not be saved. Enter a valid price.")
                    else:
                        st.markdown(f"<div class='sale-price-box'><span>PRICE</span><strong>Rs. {float(price):,.2f}</strong></div>", unsafe_allow_html=True)
                        if st.button("Edit price", key=f"edit_quick_price_{pid}", use_container_width=True):
                            st.session_state[f"show_price_editor_{pid}"] = True
                        if st.session_state.get(f"show_price_editor_{pid}"):
                            edited_price = st.number_input("New price", min_value=0.0, value=float(price), step=1.0, key=f"quick_edit_price_{pid}")
                            if st.button("Save", key=f"save_existing_price_{pid}", use_container_width=True):
                                try:
                                    set_product_price(pid, edited_price, business_id)
                                    st.session_state[f"show_price_editor_{pid}"] = False
                                    log_activity("Product price updated", f"{name} · Rs. {edited_price:,.2f}", st.session_state.user["name"], business_id)
                                    st.rerun()
                                except Exception:
                                    st.error("Price could not be saved.")
                with right:
                    st.markdown(f"<div class='sale-status-box {status_class}'><span>STOCK</span><strong>{stock:g} {unit}</strong><em>{status}</em></div>", unsafe_allow_html=True)
            if blocked:
                st.warning("Sale is not ready yet. Set missing prices and make sure requested quantities are in stock. Business Brain will not invent a price or sell more than available stock.")

            if st.session_state.sale_cart:
                from cart_tools import calculate_total
                total = calculate_total(st.session_state.sale_cart)
                st.markdown(f"<div class='premium-card'><div class='eyebrow'>Deterministic total</div><div class='big-number'>Rs. {total:,.2f}</div><div class='muted'>Calculated by Python from the saved shop prices.</div></div>", unsafe_allow_html=True)
            else:
                total = 0.0
            edit = st.text_input("Edit current order", placeholder="Tissue 3 kar do", key="cart_edit")
            if st.button("Apply Edit", use_container_width=True) and edit.strip():
                try:
                    edited = apply_cart_edit(st.session_state.sale_cart, edit, business_id)
                    if not edited["changed"]:
                        st.warning("I couldn't match that edit to a product in the current cart.")
                    else:
                        st.session_state.sale_cart = edited["cart"]
                        st.rerun()
                except Exception:
                    st.error("I couldn't apply that cart edit. Please try a quantity such as 'Tissue 3 kar do'.")
            if st.button("Confirm Sale", type="primary", use_container_width=True, disabled=(not st.session_state.sale_cart or bool(st.session_state.get("sale_missing_price")) or any((float((x.get("product") or {}).get("stock_quantity") or 0) < float(x.get("quantity") or 0)) for x in st.session_state.get("sale_order_items", [])))):
                try:
                    import uuid
                    ref = f"BB-{uuid.uuid4().hex[:8].upper()}"
                    from database_tools import save_sale
                    sale_id = save_sale(ref, total, st.session_state.sale_cart, st.session_state.user["id"], business_id)
                    st.session_state.sale_last_id = sale_id
                    st.session_state.sale_confirmed_notice = f"Sale {ref} confirmed and saved."
                    log_activity("Sale confirmed", f"{ref} · Rs. {total:,.2f}", st.session_state.user["name"], business_id)
                    st.success(f"Sale {ref} confirmed and saved successfully.")
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("Sale could not be saved. Please try again.")
    with col2:
        st.markdown("### 3 · Sale receipt")
        st.caption("Your confirmed order is shown here first. Upload a separate receipt below if you want Business Brain to verify it against this sale.")
        if st.session_state.sale_last_id:
            sale = get_sale(st.session_state.sale_last_id, business_id)
            if sale:
                st.markdown(
                    f"<div class='receipt-card'><div class='receipt-top'><div><div class='eyebrow'>SALE CONFIRMED</div><div class='receipt-ref'>{sale['transaction_ref']}</div></div><div class='receipt-status'>Confirmed</div></div>"
                    f"<div class='receipt-meta'>Sale #{sale['id']} · {sale['created_at']}</div></div>",
                    unsafe_allow_html=True,
                )
                for item in sale.get("items", []):
                    st.markdown(
                        f"<div class='receipt-line'><div><b>{item['name']}</b><div class='muted'>× {float(item['quantity']):g} · Rs. {float(item['unit_price']):,.2f} each</div></div><b>Rs. {float(item['subtotal']):,.2f}</b></div>",
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    f"<div class='receipt-total'><span>Total</span><strong>Rs. {float(sale['total']):,.2f}</strong></div>",
                    unsafe_allow_html=True,
                )
                receipt_text = [
                    "BUSINESS BRAIN — SALE RECEIPT",
                    f"Sale: {sale['transaction_ref']}",
                    f"Date: {sale['created_at']}",
                    "",
                ]
                for item in sale.get("items", []):
                    receipt_text.append(f"{item['name']} × {float(item['quantity']):g} @ Rs. {float(item['unit_price']):,.2f} = Rs. {float(item['subtotal']):,.2f}")
                receipt_text += ["", f"TOTAL: Rs. {float(sale['total']):,.2f}", "Status: Confirmed"]
                st.download_button("Download Sale Receipt", "\n".join(receipt_text), file_name=f"{sale['transaction_ref']}.txt", mime="text/plain", use_container_width=True)

                st.markdown("#### Verify an uploaded receipt")
                receipt = st.file_uploader("Upload receipt image", type=["png", "jpg", "jpeg", "webp"], key="receipt_upload")
                if receipt and st.button("Verify Receipt", use_container_width=True):
                    try:
                        expected = [{"product_id": x["product_id"], "name": x["name"], "quantity": x["quantity"], "unit_price": x["unit_price"]} for x in sale["items"]]
                        result = verify_receipt(receipt.getvalue(), receipt.type, expected, sale["total"])
                        from database import save_receipt_verification
                        save_receipt_verification(sale["id"], result.get("status", "Unclear"), result.get("extracted", {}), result.get("mismatches", []), st.session_state.user["id"], business_id)
                        if result.get("status") == "Match": st.success("Receipt matches the saved order.")
                        elif result.get("status") == "Unclear": st.warning("I couldn't read part of the receipt clearly. Please upload a clearer image or verify manually.")
                        else: st.warning("Possible mismatch detected. Please verify.")
                        for mismatch in result.get("mismatches", []): st.markdown(f"- {mismatch.get('message', 'Please verify this receipt detail.')}")
                    except Exception:
                        st.error("Receipt verification could not be completed. Please try a clearer image.")
        else:
            st.markdown("<div class='receipt-empty'><div class='receipt-empty-icon'>🧾</div><b>No confirmed sale yet</b><div class='muted'>Confirm the cart above and your sale receipt will appear here automatically.</div></div>", unsafe_allow_html=True)

# ---------- Inventory / Product Catalog ----------
elif page == "Inventory":
    business_id=current_business_id()
    page_header("Shop Catalog", "Add products quickly, then set the real selling prices your shop uses.", "Inventory")

    products=list_products(business_id)

    with st.container(border=True):
        st.markdown("### Add products quickly")
        st.caption("One product per line. You can add as many as you want; prices are never invented by Business Brain.")
        names=st.text_area(
            "Product names",
            placeholder="Atta\nPapad\nNimko\nSurf\nSabun\nPepsi",
            height=130,
            label_visibility="collapsed",
            key="catalog_bulk_names",
        )
        if st.button("＋ Add products",type="primary",use_container_width=True,key="catalog_add_products"):
            lines=[x.strip() for x in names.splitlines() if x.strip()]
            if not lines:
                st.warning("Write at least one product name.")
            else:
                result=bulk_add_products(lines,business_id)
                if result["created"]:
                    log_activity("Products added",", ".join(result["created"]),st.session_state.user["name"],business_id)
                if result["created"]:
                    st.success(f"Added {len(result['created'])} product(s). Now set their prices below.")
                if result["existing"]:
                    st.info("Already in catalog: " + ", ".join(result["existing"]))
                st.rerun()

    st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True)

    if not products:
        empty_state("No products yet","Add your shop items above. Their prices will stay empty until you enter them.")
    else:
        st.markdown("### Your products")
        st.caption("Prices shown below come directly from your shop database. White/blank price means the price has not been set yet.")

        # Search/filter keeps a large catalog easy to use.
        search=st.text_input("Search products",placeholder="Search Atta, Surf, Pepsi...",key="catalog_search")
        q=(search or "").strip().lower()
        visible=[p for p in products if not q or q in p.get("name","").lower() or q in (p.get("aliases") or "").lower()]

        if not visible:
            empty_state("No matching products", "Try another product name.")

        for product in visible:
            price=product.get("price")
            stock=float(product.get("stock_quantity") or 0)
            minimum=float(product.get("minimum_stock") or 0)
            unit=product.get("unit") or "unit"
            price_text="Price not set" if price is None else f"Rs. {float(price):,.2f}"
            price_class="catalog-price missing" if price is None else "catalog-price"
            stock_class="catalog-stock low" if stock <= minimum and minimum > 0 else "catalog-stock"

            st.markdown(
                f"""<div class='catalog-card'>
                    <div class='catalog-main'>
                        <div class='catalog-name'>{product['name']}</div>
                        <div class='catalog-meta'>{unit} · aliases: {product.get('aliases','') or product['name']}</div>
                    </div>
                    <div class='{price_class}'><span>SELLING PRICE</span><strong>{price_text}</strong></div>
                    <div class='{stock_class}'><span>STOCK</span><strong>{stock:g} {unit}</strong></div>
                    <div class='catalog-stock'><span>MINIMUM</span><strong>{minimum:g} {unit}</strong></div>
                </div>""",
                unsafe_allow_html=True,
            )

            with st.expander(f"Edit {product['name']}",expanded=(price is None)):
                with st.form(f"product_edit_{product['id']}"):
                    e1,e2=st.columns(2)
                    with e1:
                        new_price=st.number_input(
                            "Selling price (Rs.)",
                            min_value=0.0,
                            value=float(product["price"]) if product.get("price") is not None else 0.0,
                            step=1.0,
                            format="%.2f",
                            help="Enter the real price used by your shop. Business Brain will use this price in sales.",
                        )
                        new_unit=st.text_input("Unit",value=product.get("unit") or "unit",placeholder="kg / pack / piece / liter")
                        new_stock=st.number_input("Current stock",min_value=0.0,value=float(product.get("stock_quantity") or 0),step=1.0,format="%.2f")
                    with e2:
                        new_min=st.number_input("Minimum stock",min_value=0.0,value=float(product.get("minimum_stock") or 0),step=1.0,format="%.2f")
                        new_aliases=st.text_input("Aliases",value=product.get("aliases") or "",help="Optional names customers may say, e.g. aatta, flour")
                        new_name=st.text_input("Product name",value=product["name"])
                    save=st.form_submit_button("Save product",type="primary",use_container_width=True)
                if save:
                    try:
                        update_product(
                            product["id"],name=new_name,price=new_price,unit=new_unit,
                            stock_quantity=new_stock,minimum_stock=new_min,aliases=new_aliases,
                            business_id=business_id
                        )
                        log_activity("Product updated",new_name,st.session_state.user["name"],business_id)
                        st.success(f"{new_name} updated. Price: Rs. {new_price:,.2f}")
                        st.rerun()
                    except Exception:
                        st.error("The product could not be updated. Check the name, price and stock values.")

    st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True)
    st.markdown("### Business memory")
    st.caption("Small long-term facts that help Business Brain remember your shop. Prices and stock remain in the database; documents remain in Knowledge/RAG.")
    with st.form("memory_form"):
        mk=st.text_input("Memory name",placeholder="Preferred supplier")
        mv=st.text_input("Remember this",placeholder="ABC Distributor for grocery deliveries")
        save_mem=st.form_submit_button("Remember",use_container_width=True)
    if save_mem:
        if mk.strip() and mv.strip():
            add_business_memory(mk,mv,business_id=business_id); log_activity("Business memory updated",mk,st.session_state.user["name"],business_id); st.success("Remembered."); st.rerun()
        else:
            st.warning("Add both a name and a value.")
    memories=list_business_memory(business_id)
    for mem in memories[:10]:
        a,b=st.columns([5,1])
        with a: st.markdown(f"**{mem['key']}** · {mem['value']}")
        with b:
            if st.button("Forget",key=f"forget_mem_{mem['id']}"):
                delete_business_memory(mem["id"],business_id); st.rerun()

# ---------- Daily Operations ----------
elif page == "Daily Operations":
    page_header("Daily Operations", "Only the business items that actually need attention.", "Operations Agent")
    business_id = current_business_id()
    data=get_daily_operations(business_id)
    cols=st.columns(4)
    with cols[0]: stat_card("Sales today",data["sales_count"],f"Rs. {data['sales_total']:,.0f} total")
    with cols[1]: stat_card("Low stock",len(data["low_stock"]),"Actual database levels")
    with cols[2]: stat_card("Supplier drafts",data["pending_supplier_orders"],"Awaiting approval")
    with cols[3]: stat_card("Recent sales",len(data["recent_sales"]),"Latest transactions")
    st.markdown("<div class='section-gap'></div>",unsafe_allow_html=True)
    left,right=st.columns([1.2,1],gap="large")
    with left:
        st.markdown("### What needs attention?")
        if not data["low_stock"]: st.success("No low-stock products right now.")
        for item in data["low_stock"]:
            st.markdown(f"<div class='premium-card' style='margin:.45rem 0'><span class='status-pill'>LOW STOCK</span><br><b>{item['name']}</b><div class='muted'>{item.get('stock', item.get('stock_quantity', 0)):g} {item.get('unit', 'unit')} available · minimum {item.get('minimum_stock', 0):g}</div></div>",unsafe_allow_html=True)
            if st.button(f"Create draft · {item['name']}",key=f"draft_{item['id']}",use_container_width=True):
                try:
                    draft=supplier_draft(item["id"],business_id,None,st.session_state.user["id"])
                    from supplier_tools import create_supplier_order_draft
                    order_id=create_supplier_order_draft(draft["supplier"]["id"],[{"product_id":item["id"],"quantity":draft["suggested_quantity"],"unit_price":draft["supplier"].get("supplier_price")}],st.session_state.user["id"],business_id)
                    log_activity("Supplier order draft created",f"{draft['supplier']['name']} · {item['name']} × {draft['suggested_quantity']:g}",st.session_state.user["name"],business_id)
                    st.success(f"Draft #{order_id} created. Approval is still required.")
                except Exception as e: st.error(str(e))
    with right:
        st.markdown("### Supplier orders")
        orders=list_supplier_orders(business_id,8)
        if not orders: st.caption("No supplier drafts yet.")
        for order in orders:
            st.markdown(f"<div class='premium-card' style='margin:.45rem 0'><b>#{order['id']} · {order['supplier_name']}</b><div class='muted'>{order['status']} · {order['created_at']}</div></div>",unsafe_allow_html=True)
            if order["status"] in ("Draft","Pending Approval") and st.button("Approve order",key=f"approve_{order['id']}",type="primary",use_container_width=True):
                if not is_manager_or_owner():
                    st.error("Only an Owner or Manager can approve supplier orders.")
                elif approve_supplier_order(order["id"],st.session_state.user["id"],business_id):
                    log_activity("Supplier order approved",f"Order #{order['id']} · {order['supplier_name']}",st.session_state.user["name"],business_id); st.success("Order approved."); st.rerun()

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
            with st.spinner("Searching your Business Brain…"): result=answer_business_question(question, conversation=st.session_state.chat)
            if result["ok"]:
                st.markdown(result["answer"])
                if result["sources"]:
                    st.markdown("**Sources**")
                    for source in result["sources"]: source_card(source)
                st.session_state.chat.append({"role":"assistant","content":result["answer"],"sources":result["sources"]})
            else: st.error(result["error"]); st.session_state.chat.append({"role":"assistant","content":result["error"],"sources":[]})

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
