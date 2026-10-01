import sqlite3
import os
import streamlit as st
from dotenv import load_dotenv

from database import (
    init_db, seed_demo_data, seed_operational_data, get_business, list_processes, list_knowledge, get_activity,
    get_process, create_process, update_process, delete_process, get_process_versions, restore_process_version,
    authenticate_user, list_users, create_user, get_user, update_user, reset_user_password, update_business, log_activity, ensure_demo_users,
    get_daily_operations, create_sale, create_sale_items, get_sale, approve_supplier_order, list_supplier_orders,
    list_products, create_product, update_product, bulk_add_products, set_product_price,
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


def receipt_download_text(sale):
    lines = [
        "BUSINESS BRAIN — SALE RECEIPT",
        "=" * 38,
        f"Sale Reference: {sale.get('transaction_ref','')}",
        f"Sale ID: #{sale.get('id','')}",
        f"Date: {sale.get('created_at','')}",
        "",
    ]
    for item in sale.get("items", []):
        qty=float(item.get("quantity",0) or 0)
        price=float(item.get("unit_price",0) or 0)
        subtotal=float(item.get("subtotal",0) or 0)
        lines.append(f"{item.get('name','Product')}  x {qty:g}")
        lines.append(f"  Rs. {price:,.2f} each = Rs. {subtotal:,.2f}")
    lines += ["", "=" * 38, f"TOTAL: Rs. {float(sale.get('total',0) or 0):,.2f}", "", "Thank you."]
    return "\n".join(lines)


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
if "sale_missing_price" not in st.session_state: st.session_state.sale_missing_price = []

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
    page_header("Good morning 👋", "A quick view of today’s sales, stock, and pending actions.", "Home")
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
                    route = route_request(order, business_id)
                    if route["route"] != "sale":
                        st.warning(f"This request looks like a {route['route']} request. Please use the matching workflow.")
                    else:
                        result = build_cart(order, business_id)
                        st.session_state.sale_missing_price = result.get("missing_price", [])
                        st.session_state.sale_cart = result.get("cart", [])
                        st.session_state.sale_route = route
                        if not st.session_state.sale_cart:
                            st.warning("I couldn't match any product in your shop catalog. Add the product in Shop Catalog or try again.")
                        else:
                            st.success("Order understood. Every matched item is shown below with its saved price and stock.")
                except Exception:
                    st.error("I couldn't build the order. Please check the product names and quantities.")
        with c2:
            if st.button("Clear Cart", use_container_width=True):
                st.session_state.sale_cart = []
                st.session_state.sale_last_id = None
                st.session_state.sale_input_value = ""
                st.session_state.sale_missing_price = []
                st.rerun()

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
            ready=(len(refreshed)>0 and not missing_price and not stock_errors and len(priced)==len(refreshed))
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
