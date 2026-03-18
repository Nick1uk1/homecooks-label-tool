"""Sync product data from Shopify to the D2C label tool Google Sheet."""

import os
import requests

SPREADSHEET_ID = "1WFiAzrT4lrKQjIsXQDjf2K8HF01eOBz0X3MFWaFDLKM"
SHEET_API_KEY = None  # Uses public "anyone with link" edit access

# Column order matching the sheet headers
COLUMNS = [
    "product_name",
    "chef_name",
    "chef_story",
    "servings",
    "pack_weight_g",
    "ean",
    "cooking_microwave_chilled",
    "cooking_microwave_frozen",
    "cooking_oven_chilled",
    "cooking_oven_frozen",
    "ingredients",
    "energy_kj",
    "energy_kcal",
    "fat",
    "saturates",
    "carbohydrate",
    "sugars",
    "fibre",
    "protein",
    "salt",
    "storage_instructions",
]


def _parse_cooking_instructions(raw: str) -> dict:
    """Parse the free-text heating_instructions into separate fields.

    Looks for sections like 'MICROWAVE:', 'HOB:', 'OVEN:' and
    'FROM CHILLED' / 'FROM FROZEN' context.
    """
    result = {
        "cooking_microwave_chilled": "",
        "cooking_microwave_frozen": "",
        "cooking_oven_chilled": "",
        "cooking_oven_frozen": "",
    }

    if not raw:
        return result

    # Split into chilled/frozen sections
    lines = raw.split("\n")
    current_temp = "chilled"  # default

    for line in lines:
        line_stripped = line.strip()
        upper = line_stripped.upper()

        # Detect temperature context
        if "FROM FROZEN" in upper:
            current_temp = "frozen"
            continue
        if "FROM CHILLED" in upper:
            current_temp = "chilled"
            continue

        # Skip empty lines and the intro line
        if not line_stripped or "hand-made" in line_stripped.lower() or line_stripped.startswith("As our"):
            continue

        # Detect method
        if upper.startswith("MICROWAVE:") or upper.startswith("MICROWAVE -"):
            instruction = line_stripped.split(":", 1)[-1].strip() if ":" in line_stripped else line_stripped.split("-", 1)[-1].strip()
            key = f"cooking_microwave_{current_temp}"
            result[key] = instruction
        elif upper.startswith("HOB:") or upper.startswith("HOB -"):
            # Map hob to oven field as a fallback
            instruction = line_stripped.split(":", 1)[-1].strip() if ":" in line_stripped else line_stripped.split("-", 1)[-1].strip()
            # Only use hob if no oven instruction exists
            key = f"cooking_oven_{current_temp}"
            if not result[key]:
                result[key] = f"Hob: {instruction}"
        elif upper.startswith("OVEN:") or upper.startswith("OVEN -"):
            instruction = line_stripped.split(":", 1)[-1].strip() if ":" in line_stripped else line_stripped.split("-", 1)[-1].strip()
            key = f"cooking_oven_{current_temp}"
            result[key] = instruction

    return result


def product_to_row(product: dict) -> list[str]:
    """Convert a product dict to a sheet row."""
    # Parse cooking instructions if we have raw text
    cooking = _parse_cooking_instructions(product.get("cooking_instructions_raw", ""))
    # Merge — don't overwrite if product already has parsed values
    for key, val in cooking.items():
        if not product.get(key):
            product[key] = val

    row = []
    for col in COLUMNS:
        val = product.get(col, "")
        if val is None:
            val = ""
        row.append(str(val))
    return row


def sync_products_to_sheet(products: list[dict], spreadsheet_id: str = None) -> int:
    """Write all products to the Google Sheet, replacing existing data.

    Keeps the header row (row 1) and writes product data from row 2 onwards.

    Args:
        products: List of product dicts.
        spreadsheet_id: Override spreadsheet ID.

    Returns:
        Number of rows written.
    """
    sid = spreadsheet_id or SPREADSHEET_ID

    rows = []
    for product in products:
        rows.append(product_to_row(product))

    # Sort by product name for consistency
    rows.sort(key=lambda r: r[0].lower())

    # We need to use the Sheets API directly since this runs outside Streamlit
    # Use gspread if available, otherwise fall back to REST API
    import gspread
    from google.oauth2.service_account import Credentials
    import json

    # Try service account file first, then Streamlit secrets
    sa_path = os.path.join(os.path.dirname(__file__), "..", "homecooks-claude-agents", "service-account.json")
    sa_path = os.path.normpath(sa_path)
    # Also check home directory
    sa_path_alt = os.path.expanduser("~/homecooks-claude-agents/service-account.json")

    creds_dict = None
    for path in [sa_path, sa_path_alt]:
        if os.path.exists(path):
            with open(path) as f:
                creds_dict = json.load(f)
            break

    if not creds_dict:
        try:
            import streamlit as st
            creds_dict = dict(st.secrets["gcp_service_account"])
        except Exception:
            raise RuntimeError(
                "No Google service account credentials found. "
                "Place service-account.json in the project or configure Streamlit secrets."
            )

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(sid).sheet1

    # Clear existing data (keep header)
    sheet.batch_clear(["A2:U1000"])

    # Sheet stores full text — truncation happens at label generation time

    # Write new data
    if rows:
        sheet.update(values=rows, range_name=f"A2:U{1 + len(rows)}")

    return len(rows)


