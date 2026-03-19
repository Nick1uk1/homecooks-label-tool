"""Shopify Admin API integration for pulling product data."""

import os
import re
import requests

try:
    import streamlit as st
    SHOPIFY_DOMAIN = st.secrets.get("SHOPIFY_SHOP_DOMAIN", os.environ.get("SHOPIFY_SHOP_DOMAIN", ""))
    SHOPIFY_TOKEN = st.secrets.get("SHOPIFY_ACCESS_TOKEN", os.environ.get("SHOPIFY_ACCESS_TOKEN", ""))
except Exception:
    SHOPIFY_DOMAIN = os.environ.get("SHOPIFY_SHOP_DOMAIN", "")
    SHOPIFY_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")
API_VERSION = "2024-01"

# Non-food products to exclude from label generation
EXCLUDED_PRODUCTS = {
    "Delivery",
    "HomeCooks Gift Card",
    "Oven Mitts",
    "Too Hot To Handle Hoodie",
}


def _api_get(endpoint: str, params: dict = None) -> dict:
    """Make a GET request to the Shopify Admin API."""
    url = f"https://{SHOPIFY_DOMAIN}/admin/api/{API_VERSION}/{endpoint}"
    headers = {"X-Shopify-Access-Token": SHOPIFY_TOKEN}
    resp = requests.get(url, headers=headers, params=params or {})
    resp.raise_for_status()
    return resp.json()


def _parse_nutrition_text(text: str) -> dict:
    """Parse the nutritional_information metafield into individual values.

    Handles formats like:
        Energy: 340 Kcal
        Fat: 16.8g (Saturates: 3.0g)
        Carbohydrates: 39.3g (Sugars: 12.9g)
        Fibre: 7.0g
        Protein: 9.4g
        Salt: 0.7g
    """
    nutrition = {}

    if not text:
        return nutrition

    # Energy (kJ and/or kcal)
    kj_match = re.search(r'(\d+)\s*kJ', text, re.IGNORECASE)
    kcal_match = re.search(r'Energy[:\s]*(\d+)\s*Kcal', text, re.IGNORECASE)
    if kj_match:
        nutrition["energy_kj"] = float(kj_match.group(1))
    if kcal_match:
        nutrition["energy_kcal"] = float(kcal_match.group(1))

    # Fat and saturates
    fat_match = re.search(r'Fat[:\s]*([\d.]+)\s*g', text, re.IGNORECASE)
    sat_match = re.search(r'Saturates?[:\s]*([\d.]+)\s*g', text, re.IGNORECASE)
    if fat_match:
        nutrition["fat"] = float(fat_match.group(1))
    if sat_match:
        nutrition["saturates"] = float(sat_match.group(1))

    # Carbohydrates and sugars
    carb_match = re.search(r'Carbohydrates?[:\s]*([\d.]+)\s*g', text, re.IGNORECASE)
    sugar_match = re.search(r'Sugars?[:\s]*([\d.]+)\s*g', text, re.IGNORECASE)
    if carb_match:
        nutrition["carbohydrate"] = float(carb_match.group(1))
    if sugar_match:
        nutrition["sugars"] = float(sugar_match.group(1))

    # Fibre
    fibre_match = re.search(r'Fibre[:\s]*([\d.]+)\s*g', text, re.IGNORECASE)
    if fibre_match:
        nutrition["fibre"] = float(fibre_match.group(1))

    # Protein
    protein_match = re.search(r'Protein[:\s]*([\d.]+)\s*g', text, re.IGNORECASE)
    if protein_match:
        nutrition["protein"] = float(protein_match.group(1))

    # Salt
    salt_match = re.search(r'Salt[:\s]*([\d.]+)\s*g', text, re.IGNORECASE)
    if salt_match:
        nutrition["salt"] = float(salt_match.group(1))

    return nutrition


def _get_metafields(product_id: int) -> dict:
    """Fetch all metafields for a product, returned as {key: value}."""
    data = _api_get(f"products/{product_id}/metafields.json")
    meta = {}
    for m in data.get("metafields", []):
        meta[m["key"]] = m["value"]
    return meta


def fetch_all_products() -> list[dict]:
    """Fetch all products from Shopify and map to label tool format.

    Returns:
        List of product dicts with standardised field names.
    """
    products = []
    params = {"limit": 250, "fields": "id,title,variants"}
    page_info = None

    # Paginate through all products
    while True:
        if page_info:
            url = f"https://{SHOPIFY_DOMAIN}/admin/api/{API_VERSION}/products.json"
            headers = {"X-Shopify-Access-Token": SHOPIFY_TOKEN}
            resp = requests.get(url, headers=headers, params={"limit": 250, "page_info": page_info})
            resp.raise_for_status()
            data = resp.json()
        else:
            data = _api_get("products.json", params)

        for p in data.get("products", []):
            if p["title"] in EXCLUDED_PRODUCTS:
                continue
            variant = p["variants"][0] if p.get("variants") else {}
            meta = _get_metafields(p["id"])

            # Parse nutrition from the full text field, with fallbacks to individual metafields
            nutrition = _parse_nutrition_text(meta.get("nutritional_information", ""))

            # Fallback to individual metafields if the text parse missed them
            if "energy_kcal" not in nutrition and meta.get("kcal"):
                try:
                    nutrition["energy_kcal"] = float(meta["kcal"])
                except (ValueError, TypeError):
                    pass
            if "fat" not in nutrition and meta.get("fats"):
                try:
                    nutrition["fat"] = float(meta["fats"])
                except (ValueError, TypeError):
                    pass
            if "carbohydrate" not in nutrition and meta.get("carbs"):
                try:
                    nutrition["carbohydrate"] = float(meta["carbs"])
                except (ValueError, TypeError):
                    pass
            if "protein" not in nutrition and meta.get("dish_protein"):
                try:
                    nutrition["protein"] = float(meta["dish_protein"])
                except (ValueError, TypeError):
                    pass
            if "fibre" not in nutrition and meta.get("fibre"):
                try:
                    nutrition["fibre"] = float(meta["fibre"])
                except (ValueError, TypeError):
                    pass

            # Estimate kJ from kcal if missing (1 kcal ≈ 4.184 kJ)
            if "energy_kj" not in nutrition and "energy_kcal" in nutrition:
                nutrition["energy_kj"] = round(nutrition["energy_kcal"] * 4.184)

            # Parse portion weight from metafield or variant
            pack_weight = 0
            portion_str = meta.get("portion", "")
            if portion_str:
                weight_match = re.search(r'(\d+)', str(portion_str))
                if weight_match:
                    pack_weight = float(weight_match.group(1))
            if not pack_weight and variant.get("grams"):
                pack_weight = float(variant["grams"])

            product = {
                "product_name": p["title"],
                "chef_name": meta.get("chef_name", ""),
                "chef_story": meta.get("chef_food_story", ""),
                "servings": 1,
                "pack_weight_g": pack_weight,
                "ean": variant.get("barcode", "") or "",
                "cooking_instructions_raw": meta.get("heating_instructions", ""),
                "ingredients": meta.get("main_ingredients", ""),
                "storage_instructions": "Keep refrigerated below 5°C. Once opened, consume within 24 hours.",
                "shopify_id": p["id"],
                **nutrition,
            }
            products.append(product)

        # Check for next page — simple approach, break if we got fewer than limit
        if len(data.get("products", [])) < 250:
            break

    return products
