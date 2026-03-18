"""Per-portion nutritional calculation from per-100g values."""


# EU reference intakes for adults (used for %RI calculation if needed later)
EU_REFERENCE_INTAKES = {
    "energy_kj": 8400,
    "energy_kcal": 2000,
    "fat": 70,
    "saturates": 20,
    "carbohydrate": 260,
    "sugars": 90,
    "fibre": 30,
    "protein": 50,
    "salt": 6,
}

NUTRITION_FIELDS = [
    "energy_kj",
    "energy_kcal",
    "fat",
    "saturates",
    "carbohydrate",
    "sugars",
    "fibre",
    "protein",
    "salt",
]

NUTRITION_LABELS = {
    "energy_kj": "Energy (kJ)",
    "energy_kcal": "Energy (kcal)",
    "fat": "Fat",
    "saturates": "of which saturates",
    "carbohydrate": "Carbohydrate",
    "sugars": "of which sugars",
    "fibre": "Fibre",
    "protein": "Protein",
    "salt": "Salt",
}

NUTRITION_UNITS = {
    "energy_kj": "kJ",
    "energy_kcal": "kcal",
    "fat": "g",
    "saturates": "g",
    "carbohydrate": "g",
    "sugars": "g",
    "fibre": "g",
    "protein": "g",
    "salt": "g",
}


def calculate_per_portion(per_100g: dict, pack_weight_g: float, servings: int = 1) -> dict:
    """Calculate per-portion values from per-100g data.

    Args:
        per_100g: Dict with nutrition field names as keys and per-100g values.
        pack_weight_g: Total pack weight in grams.
        servings: Number of servings per pack.

    Returns:
        Dict with same keys containing per-portion values rounded appropriately.
    """
    portion_weight = pack_weight_g / servings
    per_portion = {}
    for field in NUTRITION_FIELDS:
        val = per_100g.get(field, 0)
        if val is None:
            val = 0
        raw = float(val) * portion_weight / 100.0
        # Round energy to whole numbers, everything else to 1 decimal
        if field in ("energy_kj", "energy_kcal"):
            per_portion[field] = round(raw)
        else:
            per_portion[field] = round(raw, 1)
    return per_portion


def calculate_ri_percentage(per_portion: dict) -> dict:
    """Calculate %RI (Reference Intake) for per-portion values."""
    ri = {}
    for field in NUTRITION_FIELDS:
        ref = EU_REFERENCE_INTAKES.get(field)
        val = per_portion.get(field, 0)
        if ref and val:
            ri[field] = round(float(val) / ref * 100)
        else:
            ri[field] = None
    return ri


def format_nutrition_rows(per_100g: dict, pack_weight_g: float, servings: int = 1) -> list:
    """Build rows for the nutrition table.

    Returns list of tuples: (label, per_100g_str, per_portion_str)
    """
    per_portion = calculate_per_portion(per_100g, pack_weight_g, servings)
    portion_weight = pack_weight_g / servings

    rows = []
    rows.append(("", "Per 100g", f"Per portion ({round(portion_weight)}g)"))

    for field in NUTRITION_FIELDS:
        label = NUTRITION_LABELS[field]
        unit = NUTRITION_UNITS[field]
        val_100 = per_100g.get(field, 0)
        val_portion = per_portion[field]

        if field in ("energy_kj", "energy_kcal"):
            str_100 = f"{round(float(val_100))} {unit}"
            str_portion = f"{val_portion} {unit}"
        else:
            str_100 = f"{float(val_100):.1f} {unit}"
            str_portion = f"{val_portion:.1f} {unit}"

        rows.append((label, str_100, str_portion))

    return rows
