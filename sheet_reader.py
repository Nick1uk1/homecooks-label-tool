"""Read product data from the D2C label tool Google Sheet."""

import json
import os

import gspread
from google.oauth2.service_account import Credentials

# Service account path
SA_PATHS = [
    os.path.expanduser("~/homecooks-claude-agents/service-account.json"),
    os.path.join(os.path.dirname(__file__), "service-account.json"),
]

# Column headers → internal field names
COLUMN_MAP = {
    "product name": "product_name",
    "chef name": "chef_name",
    "chef story": "chef_story",
    "servings": "servings",
    "pack weight (g)": "pack_weight_g",
    "ean barcode": "ean",
    "microwave chilled": "cooking_microwave_chilled",
    "microwave frozen": "cooking_microwave_frozen",
    "oven chilled": "cooking_oven_chilled",
    "oven frozen": "cooking_oven_frozen",
    "ingredients": "ingredients",
    "energy (kj)": "energy_kj",
    "energy (kcal)": "energy_kcal",
    "fat": "fat",
    "saturates": "saturates",
    "carbohydrate": "carbohydrate",
    "sugars": "sugars",
    "fibre": "fibre",
    "protein": "protein",
    "salt": "salt",
    "storage instructions": "storage_instructions",
}


def _get_client():
    """Get an authorised gspread client."""
    creds_dict = None
    for path in SA_PATHS:
        if os.path.exists(path):
            with open(path) as f:
                creds_dict = json.load(f)
            break

    if not creds_dict:
        raise RuntimeError("No service account credentials found.")

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.readonly",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)


def load_products_from_sheet(spreadsheet_id: str, worksheet_name: str = "Sheet1") -> list[dict]:
    """Load all products from the Google Sheet.

    Args:
        spreadsheet_id: The Google Spreadsheet ID.
        worksheet_name: Tab name to read from.

    Returns:
        List of product dicts with standardised field names.
    """
    client = _get_client()
    sheet = client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
    rows = sheet.get_all_records()

    products = []
    for row in rows:
        product = {}
        for col_header, value in row.items():
            field = COLUMN_MAP.get(col_header.strip().lower())
            if field:
                product[field] = value
        # Skip empty rows
        if product.get("product_name"):
            products.append(product)

    return products
