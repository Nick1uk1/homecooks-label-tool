"""EAN barcode generation using python-barcode."""

import io
import barcode
from barcode.writer import ImageWriter
from PIL import Image


def generate_ean_barcode(ean_number: str, width_mm: float = 40, height_mm: float = 18) -> Image.Image:
    """Generate an EAN barcode as a PIL Image.

    Args:
        ean_number: EAN-13 barcode number as string.
        width_mm: Target width in mm (approximate).
        height_mm: Target height in mm (approximate).

    Returns:
        PIL Image of the barcode.
    """
    # Clean the input — remove spaces and dashes
    ean_clean = ean_number.strip().replace(" ", "").replace("-", "")

    # Determine barcode type based on length
    if len(ean_clean) == 13:
        barcode_class = barcode.get_barcode_class("ean13")
    elif len(ean_clean) == 8:
        barcode_class = barcode.get_barcode_class("ean8")
    else:
        raise ValueError(f"EAN must be 8 or 13 digits, got {len(ean_clean)}: {ean_clean}")

    # Generate barcode to a bytes buffer
    writer = ImageWriter()
    ean = barcode_class(ean_clean, writer=writer)

    buffer = io.BytesIO()
    ean.write(buffer, options={
        "module_width": 0.3,
        "module_height": 10,
        "font_size": 0,
        "text_distance": 0,
        "quiet_zone": 2,
    })
    buffer.seek(0)

    img = Image.open(buffer)
    return img


def generate_ean_barcode_bytes(ean_number: str, format: str = "PNG") -> bytes:
    """Generate an EAN barcode and return as bytes."""
    img = generate_ean_barcode(ean_number)
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    return buffer.getvalue()
