"""HomeCooks D2C Label Tool — Streamlit UI."""

import streamlit as st
import os

from label_generator import generate_label_pdf, generate_batch_labels
from nutrition_calculator import NUTRITION_FIELDS, NUTRITION_LABELS
from ean_generator import assign_eans
from sheet_reader import load_products_from_sheet

# --- Config ---
SPREADSHEET_ID = "1WFiAzrT4lrKQjIsXQDjf2K8HF01eOBz0X3MFWaFDLKM"
CHAR_LIMITS = {
    "product_name": 42, "chef_name": 66, "chef_story": 350,
    "cooking_microwave_chilled": 170, "cooking_microwave_frozen": 170,
    "cooking_oven_chilled": 170, "cooking_oven_frozen": 170,
    "ingredients": 920, "storage_instructions": 198,
}

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


def validate_product(product: dict) -> list[str]:
    warnings = []
    for field, limit in CHAR_LIMITS.items():
        val = str(product.get(field, ""))
        if len(val) > limit:
            warnings.append(f"**{field.replace('_', ' ').title()}**: {len(val)}/{limit} chars (over by {len(val) - limit})")
    return warnings


# --- Page config ---
st.set_page_config(
    page_title="HomeCooks Label Tool",
    page_icon=os.path.join(ASSETS_DIR, "logo.png"),
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Load CSS
css_path = os.path.join(ASSETS_DIR, "style.css")
with open(css_path) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# --- Header ---
import base64
logo_path = os.path.join(ASSETS_DIR, "logo.png")
with open(logo_path, "rb") as f:
    logo_b64 = base64.b64encode(f.read()).decode()

st.markdown(f"""
<div class="main-header">
    <img src="data:image/png;base64,{logo_b64}" alt="HomeCooks">
    <div>
        <h1>D2C Label Tool</h1>
        <div class="subtitle">Generate print-ready overprint labels</div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- Load products ---
if "products" not in st.session_state:
    try:
        products = load_products_from_sheet(SPREADSHEET_ID)
        products = assign_eans(products)
        st.session_state["products"] = products
    except Exception as e:
        st.session_state["products"] = []
        st.error(f"Failed to load products: {e}")

products = st.session_state.get("products", [])

# --- Top bar: product count + update button ---
col_info, col_refresh, col_sync = st.columns([4, 1, 1])

with col_info:
    st.markdown(f'<div class="product-count">{len(products)} products loaded</div>', unsafe_allow_html=True)

with col_refresh:
    if st.button("Refresh Sheet"):
        try:
            products = load_products_from_sheet(SPREADSHEET_ID)
            products = assign_eans(products)
            st.session_state["products"] = products
            st.rerun()
        except Exception as e:
            st.error(f"Failed: {e}")

with col_sync:
    if st.button("Sync Shopify"):
        try:
            from shopify_integration import fetch_all_products
            from sync_to_sheet import sync_products_to_sheet
            with st.spinner("Syncing from Shopify..."):
                shopify_products = fetch_all_products()
                shopify_products = assign_eans(shopify_products)
                sync_products_to_sheet(shopify_products)
                products = load_products_from_sheet(SPREADSHEET_ID)
                products = assign_eans(products)
                st.session_state["products"] = products
            st.rerun()
        except Exception as e:
            st.error(f"Sync failed: {e}")

# --- Main: product selection + generation ---
if products:
    product_names = [p.get("product_name", f"Product {i+1}") for i, p in enumerate(products)]

    selected = st.multiselect(
        "Select products",
        options=product_names,
        default=[],
        placeholder="Choose products to generate labels for...",
    )
    selected_products = [p for p, n in zip(products, product_names) if n in selected]

    # Production run fields
    col_a, col_b = st.columns(2)
    with col_a:
        batch_code = st.text_input("Batch Code", placeholder="e.g. BC240318")
    with col_b:
        use_by_date = st.text_input("Use By Date", placeholder="e.g. 25/03/2026")

    # Validation warnings
    if selected_products:
        all_warnings = []
        for p in selected_products:
            w = validate_product(p)
            if w:
                all_warnings.append((p.get("product_name", "Unknown"), w))
        if all_warnings:
            for name, warns in all_warnings:
                st.warning(f"**{name}** — text too long for label area:\n" + "\n".join(f"- {w}" for w in warns))

    # Preview + Generate buttons
    can_generate = batch_code and use_by_date and selected_products
    col_preview, col_generate = st.columns(2)

    with col_preview:
        if st.button("Preview on Label", disabled=not can_generate):
            with st.spinner("Generating preview..."):
                try:
                    preview_pdf = generate_label_pdf(
                        selected_products[0], batch_code, use_by_date,
                        overlay_background=True,
                    )
                    st.download_button(
                        label="Download Preview PDF",
                        data=preview_pdf,
                        file_name=f"{selected_products[0]['product_name'].replace(' ', '_')}_preview.pdf",
                        mime="application/pdf",
                    )
                    st.success("Preview generated — overlaid on the coloured label")
                except Exception as e:
                    st.error(f"Preview failed: {e}")

    with col_generate:
        if st.button("Generate Label(s)", type="primary", disabled=not can_generate):
            with st.spinner("Generating..."):
                try:
                    if len(selected_products) == 1:
                        pdf_bytes = generate_label_pdf(selected_products[0], batch_code, use_by_date)
                        filename = f"{selected_products[0]['product_name'].replace(' ', '_')}_label.pdf"
                    else:
                        pdf_bytes = generate_batch_labels(selected_products, batch_code, use_by_date)
                        filename = f"HomeCooks_labels_batch_{batch_code}.pdf"

                    st.success(f"Generated {len(selected_products)} label(s)!")
                    st.download_button(
                        label="Download PDF",
                        data=pdf_bytes,
                        file_name=filename,
                        mime="application/pdf",
                    )
                except Exception as e:
                    st.error(f"Generation failed: {e}")
                    st.exception(e)

    if not can_generate:
        if not selected_products:
            st.caption("Select at least one product above.")
        elif not batch_code or not use_by_date:
            st.caption("Enter batch code and use by date to enable generation.")

else:
    st.info("No products loaded. Click 'Refresh Sheet' or 'Sync Shopify' above.")

# --- Footer ---
st.divider()
st.caption("HomeCooks D2C Label Tool v1.0")
