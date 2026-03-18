"""Google Sheets integration for pulling product data."""

import json
import streamlit as st

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False


# Expected column headers in the sheet (case-insensitive matching)
EXPECTED_COLUMNS = {
    "product_name": ["product name", "product", "name"],
    "chef_name": ["chef name", "chef"],
    "chef_story": ["chef story", "story", "chef bio"],
    "servings": ["servings", "serves", "portions"],
    "pack_weight_g": ["pack weight", "pack weight (g)", "weight", "weight (g)", "pack weight g"],
    "ean": ["ean", "ean barcode", "barcode", "ean number", "ean13"],
    "cooking_microwave_chilled": ["microwave chilled", "micro chilled", "cooking microwave chilled"],
    "cooking_microwave_frozen": ["microwave frozen", "micro frozen", "cooking microwave frozen"],
    "cooking_oven_chilled": ["oven chilled", "cooking oven chilled"],
    "cooking_oven_frozen": ["oven frozen", "cooking oven frozen"],
    "ingredients": ["ingredients", "ingredients list"],
    "energy_kj": ["energy kj", "energy (kj)", "kj"],
    "energy_kcal": ["energy kcal", "energy (kcal)", "kcal"],
    "fat": ["fat", "fat (g)"],
    "saturates": ["saturates", "of which saturates", "saturates (g)"],
    "carbohydrate": ["carbohydrate", "carbs", "carbohydrate (g)"],
    "sugars": ["sugars", "of which sugars", "sugars (g)"],
    "fibre": ["fibre", "fiber", "fibre (g)"],
    "protein": ["protein", "protein (g)"],
    "salt": ["salt", "salt (g)"],
    "storage_instructions": ["storage", "storage instructions"],
}


def _match_column(header: str, mapping: dict) -> str | None:
    """Match a sheet column header to our internal field name."""
    header_lower = header.strip().lower()
    for field, variants in mapping.items():
        if header_lower in variants:
            return field
    return None


def connect_to_sheet(sheet_name: str, worksheet_name: str, credentials_json: dict) -> list[dict]:
    """Connect to a Google Sheet and return rows as list of dicts.

    Args:
        sheet_name: Name of the Google Spreadsheet.
        worksheet_name: Name of the worksheet/tab.
        credentials_json: Service account credentials as dict.

    Returns:
        List of dicts, one per product row, with standardised keys.
    """
    if not GSPREAD_AVAILABLE:
        raise ImportError("gspread is not installed. Run: pip install gspread google-auth")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(credentials_json, scopes=scopes)
    client = gspread.authorize(creds)

    spreadsheet = client.open(sheet_name)
    worksheet = spreadsheet.worksheet(worksheet_name)
    raw_data = worksheet.get_all_records()

    # Map columns to standard field names
    if not raw_data:
        return []

    products = []
    for row in raw_data:
        product = {}
        for original_key, value in row.items():
            mapped_key = _match_column(original_key, EXPECTED_COLUMNS)
            if mapped_key:
                product[mapped_key] = value
        # Only include rows that have a product name
        if product.get("product_name"):
            products.append(product)

    return products


def load_products_from_sheet(sheet_name: str, worksheet_name: str) -> list[dict]:
    """Load products using Streamlit secrets for credentials.

    Expects st.secrets["gcp_service_account"] to contain the service account JSON.
    """
    try:
        creds = dict(st.secrets["gcp_service_account"])
        return connect_to_sheet(sheet_name, worksheet_name, creds)
    except Exception as e:
        st.error(f"Failed to connect to Google Sheet: {e}")
        return []


def parse_manual_product(data: dict) -> dict:
    """Normalise a manually-entered product dict to the standard format."""
    product = {}
    for key, value in data.items():
        mapped = _match_column(key, EXPECTED_COLUMNS)
        product[mapped or key] = value
    return product
