"""Auto-generate sequential EAN-13 barcodes for new SKUs."""

# Base prefix (first 12 digits of the starting EAN, before check digit)
EAN_BASE_PREFIX = "506502120954"  # From 5065021209547 (check digit 7)


def calculate_check_digit(first_12: str) -> int:
    """Calculate EAN-13 check digit from the first 12 digits."""
    digits = [int(d) for d in first_12]
    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    return (10 - (total % 10)) % 10


def make_ean13(first_12: str) -> str:
    """Return a full EAN-13 with check digit."""
    check = calculate_check_digit(first_12)
    return first_12 + str(check)


def next_ean(existing_eans: list[str]) -> str:
    """Generate the next EAN-13 in sequence.

    Looks at all existing EANs, finds the highest base number,
    and returns the next one with a valid check digit.

    Args:
        existing_eans: List of existing EAN-13 strings.

    Returns:
        Next EAN-13 as string.
    """
    if not existing_eans:
        # First EAN is the starting one
        return make_ean13(EAN_BASE_PREFIX)

    # Find the highest existing base (first 12 digits)
    max_base = 0
    for ean in existing_eans:
        ean_clean = str(ean).strip().replace(" ", "").replace("-", "")
        if len(ean_clean) == 13 and ean_clean.isdigit():
            base = int(ean_clean[:12])
            if base > max_base:
                max_base = base

    if max_base == 0:
        return make_ean13(EAN_BASE_PREFIX)

    # Increment
    next_base = str(max_base + 1)
    return make_ean13(next_base)


def assign_eans(products: list[dict]) -> list[dict]:
    """Assign EANs to any products that don't have one.

    Args:
        products: List of product dicts. Products with an existing
                  'ean' value are left unchanged.

    Returns:
        Same list with EANs filled in.
    """
    # Collect existing EANs
    existing = [str(p["ean"]) for p in products if p.get("ean") and str(p["ean"]).strip()]

    for product in products:
        ean = str(product.get("ean", "")).strip()
        if not ean:
            new_ean = next_ean(existing)
            product["ean"] = new_ean
            existing.append(new_ean)

    return products
