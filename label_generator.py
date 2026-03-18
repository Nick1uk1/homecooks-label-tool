"""PDF overprint label generation — aligned to HomeCooks colour label.

Coordinate system: design uses top-left (0,0), PDF uses bottom-left.
All element positions from design spec.
Text is optically centred within containers (slightly below true centre).
"""

import io
import json
import os
import re
import tempfile

from reportlab.lib.pagesizes import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from reportlab.pdfgen import canvas
from reportlab.lib import colors

from nutrition_calculator import format_nutrition_rows, NUTRITION_FIELDS
from barcode_generator import generate_ean_barcode

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "templates", "label_config.json")
BACKGROUND_PATH = os.path.join(os.path.dirname(__file__), "assets", "background.pdf")

PAGE_W = 105.0
PAGE_H = 200.0
Y_OFFSET_PT = 8.04

# Optical centering bias: text sits this many mm below true vertical centre
OPTICAL_BIAS = 0.3


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def pt(val_mm):
    return val_mm * mm


def dy(design_y):
    """Convert design Y (top-left origin) to PDF Y (bottom-left origin)."""
    return PAGE_H - design_y


def _cap_height_mm(font_size_pt):
    """Approximate cap height in mm for a given font size in points."""
    return font_size_pt * 0.7 * 0.353


def _optical_centre_baseline(container_bottom_mm, container_height_mm, font_size_pt):
    """Calculate baseline Y (mm) to optically centre single-line text in a container.
    Slightly below true centre (OPTICAL_BIAS)."""
    cap_h = _cap_height_mm(font_size_pt)
    true_centre = container_bottom_mm + container_height_mm / 2
    baseline = true_centre - cap_h / 2 - OPTICAL_BIAS
    return baseline


def _allergen_html(text):
    text = re.sub(r'(\w)\[', r'\1 [', text)
    return re.sub(r'\[([^\]]+)\]', lambda m: f"<b>{m.group(1)}</b>", text)


def _wrap(c, text, font, size, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if c.stringWidth(test, font, size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _truncate(c, lines, max_lines, font, size, max_w):
    if len(lines) <= max_lines:
        return lines
    out = lines[:max_lines]
    last = out[-1]
    while c.stringWidth(last + "...", font, size) > max_w and " " in last:
        last = last.rsplit(" ", 1)[0]
    out[-1] = last + "..."
    return out


# ======================================================================
# DESIGN SPEC — exact element positions (top-left origin, mm)
# ======================================================================
TITLE_PANEL = {"x": 5.6, "y": 14.6, "w": 59.4, "h": 20.6}
PROTEIN_PILL = {"x": 71.1, "y": 28.3, "w": 13.1, "h": 7.1}
CALORIES_PILL = {"x": 87.1, "y": 28.2, "w": 13.1, "h": 7.1}
MICROWAVE_BLOCK = {"x": 4.1, "y": 47.3, "w": 13.8, "h": 14.5}
OVEN_BLOCK = {"x": 57.0, "y": 52.7, "w": 11.9, "h": 11.9}
QR_BOX = {"x": 6.6, "y": 94.6, "w": 26.9, "h": 18.5}
NUTRITION_TABLE = {"x": 37.7, "y": 89.9, "w": 60.3, "h": 27.6}
STORAGE_STRIP = {"x": 6.4, "y": 171.2, "w": 92.3, "h": 7.0}
BOTTOM_BOX_1 = {"x": 6.2, "y": 180.9, "w": 20.5, "h": 7.1}
BOTTOM_BOX_2 = {"x": 30.3, "y": 180.9, "w": 20.5, "h": 7.1}
BOTTOM_BOX_3 = {"x": 54.3, "y": 180.9, "w": 20.5, "h": 7.1}
USE_BY_BOX = {"x": 78.4, "y": 180.9, "w": 20.5, "h": 7.1}


def generate_label_pdf(product, batch_code, use_by_date, config=None, overlay_background=False):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Register Roboto fonts
    fonts_dir = os.path.join(os.path.dirname(__file__), "assets", "fonts")
    roboto_regular = os.path.join(fonts_dir, "Roboto-Regular.ttf")
    roboto_bold = os.path.join(fonts_dir, "Roboto-Bold.ttf")
    if os.path.exists(roboto_regular):
        try:
            pdfmetrics.registerFont(TTFont("Roboto", roboto_regular))
            pdfmetrics.registerFont(TTFont("Roboto-Bold", roboto_bold))
        except Exception:
            pass

    W = pt(PAGE_W)
    H = pt(PAGE_H)
    FR = "Helvetica"
    FB = "Helvetica-Bold"
    # Roboto for chef story
    FR_STORY = "Roboto" if os.path.exists(roboto_regular) else FR

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H + Y_OFFSET_PT))
    c.translate(0, Y_OFFSET_PT)

    PAD = 1.5  # mm

    # ==============================================================
    # PRODUCT NAME — centred above title panel
    # Title area: from top of page to top of title panel
    # ==============================================================
    name = str(product.get("product_name", ""))
    name_size = 18
    while c.stringWidth(name, FB, name_size) > pt(PAGE_W - 10) and name_size > 10:
        name_size -= 0.5
    c.setFont(FB, name_size)
    # Title area: from ~y=3mm (design top) to y=14.6mm (panel top)
    title_area_bottom = dy(TITLE_PANEL["y"])  # PDF
    title_area_top = dy(3)  # ~3mm from top of page
    title_area_h = title_area_top - title_area_bottom
    name_y = _optical_centre_baseline(title_area_bottom, title_area_h, name_size)
    c.drawCentredString(W / 2, pt(name_y), name)

    # ==============================================================
    # TITLE PANEL — chef story optically centred within turquoise box
    # ==============================================================
    tp = TITLE_PANEL
    tp_pdf_top = dy(tp["y"])
    tp_pdf_bottom = dy(tp["y"] + tp["h"])
    tp_pdf_left = tp["x"]
    tp_inner_w = tp["w"] - PAD * 2
    tp_h = tp["h"]

    story = str(product.get("chef_story", ""))
    if story:
        story_w_mm = tp_inner_w
        usable_h = tp_h - 5  # reserve 5mm for chef name
        story_w = pt(story_w_mm)

        # Roboto size 7, strictly contained within the green box
        story_size = 7
        story_font = FR_STORY
        c.setFont(story_font, story_size)
        lines = _wrap(c, story, story_font, story_size, story_w)

        # Strict box limits: text must stay inside green panel
        panel_top_y = tp_pdf_top - PAD - 1.0   # 2.5mm below top edge (shifted down 1mm)
        panel_bottom_y = dy(tp["y"] + tp["h"]) + 5  # 5mm above bottom edge (chef name area)
        usable_h_strict = panel_top_y - panel_bottom_y

        leading_pt = story_size * 0.92
        leading_mm = leading_pt * 0.353
        max_lines = int(usable_h_strict / leading_mm)
        lines = _truncate(c, lines, max_lines, story_font, story_size, story_w)

        # Position: top-anchored within panel, never goes below panel_bottom_y
        sy = pt(panel_top_y)
        for line in lines:
            if sy < pt(panel_bottom_y):
                break
            c.drawString(pt(tp_pdf_left + PAD), sy, line)
            sy -= leading_pt

    # Chef name — optically centred in the reserved bottom area of panel
    chef = str(product.get("chef_name", ""))
    if chef:
        c.setFont(FB, 10)
        # Chef name in bottom 6mm of panel
        chef_area_bottom = tp_pdf_bottom
        chef_area_h = 6  # mm
        chef_y = _optical_centre_baseline(chef_area_bottom, chef_area_h, 10)
        c.drawString(pt(tp_pdf_left + PAD + 2), pt(chef_y), chef)

    # ==============================================================
    # PROTEIN PILL — optically centred within pill
    # ==============================================================
    pp = PROTEIN_PILL
    pp_cx = pp["x"] + pp["w"] / 2
    pp_bottom = dy(pp["y"] + pp["h"])

    protein = product.get("protein", 0)
    try:
        protein_val = f"{float(protein):.1f}g" if protein else ""
    except (ValueError, TypeError):
        protein_val = ""
    if protein_val:
        badge_size = 9
        while c.stringWidth(protein_val, FB, badge_size) > pt(pp["w"] - 2) and badge_size > 5:
            badge_size -= 0.5
        c.setFont(FB, badge_size)
        pp_y = _optical_centre_baseline(pp_bottom, pp["h"], badge_size)
        c.drawCentredString(pt(pp_cx), pt(pp_y), protein_val)

    # ==============================================================
    # CALORIES PILL — optically centred within pill
    # ==============================================================
    cp = CALORIES_PILL
    cp_cx = cp["x"] + cp["w"] / 2
    cp_bottom = dy(cp["y"] + cp["h"])

    kcal = product.get("energy_kcal", 0)
    try:
        kcal_val = f"{int(float(kcal))}kcal" if kcal else ""
    except (ValueError, TypeError):
        kcal_val = ""
    if kcal_val:
        badge_size = 9
        while c.stringWidth(kcal_val, FB, badge_size) > pt(cp["w"] - 2) and badge_size > 5:
            badge_size -= 0.5
        c.setFont(FB, badge_size)
        cp_y = _optical_centre_baseline(cp_bottom, cp["h"], badge_size)
        c.drawCentredString(pt(cp_cx), pt(cp_y), kcal_val)

    # ==============================================================
    # COOKING INSTRUCTIONS — centred within available cooking area
    # ==============================================================
    mb = MICROWAVE_BLOCK
    ob = OVEN_BLOCK
    cook_area_top = min(dy(mb["y"] + mb["h"]), dy(ob["y"] + ob["h"])) - 1
    cook_area_bottom = dy(NUTRITION_TABLE["y"] - 1)
    cook_area_h = cook_area_top - cook_area_bottom

    micro_x = pt(mb["x"])
    micro_w = pt(48)
    oven_x = pt(ob["x"])
    oven_w = pt(PAGE_W - ob["x"] - 3)

    micro_chilled = str(product.get("cooking_microwave_chilled", "")).strip()
    micro_frozen = str(product.get("cooking_microwave_frozen", "")).strip()
    oven_chilled = str(product.get("cooking_oven_chilled", "")).strip()
    oven_frozen = str(product.get("cooking_oven_frozen", "")).strip()

    def _count_lines(chilled, frozen, font, size, width):
        n = 0
        if chilled:
            n += 1 + len(_wrap(c, chilled, font, size, width)) + 1
        if frozen:
            n += 1 + len(_wrap(c, frozen, font, size, width))
        return n

    cook_size = 5.5
    for sz in [5.5, 5.0, 4.5, 4.0, 3.5, 3.0]:
        cook_size = sz
        c.setFont(FR, cook_size)
        ml = max(
            _count_lines(micro_chilled, micro_frozen, FR, cook_size, micro_w),
            _count_lines(oven_chilled, oven_frozen, FR, cook_size, oven_w),
        )
        if ml * (sz * 0.91) / mm <= cook_area_h:
            break

    cook_leading = cook_size * 0.91  # 91% line height, tight

    # Calculate total lines for vertical centering
    max_cook_lines = max(
        _count_lines(micro_chilled, micro_frozen, FR, cook_size, micro_w),
        _count_lines(oven_chilled, oven_frozen, FR, cook_size, oven_w),
    )
    total_cook_h_mm = max_cook_lines * cook_size * 0.91 * 0.353
    cook_start_y = cook_area_top - (cook_area_h - total_cook_h_mm) / 2 - OPTICAL_BIAS

    def _draw_cook(x, w, chilled, frozen, start_y):
        y = start_y
        if chilled:
            c.setFont(FB, cook_size)
            c.drawString(x, y, "From Chilled:")
            y -= cook_leading
            c.setFont(FR, cook_size)
            for line in _wrap(c, chilled, FR, cook_size, w):
                c.drawString(x, y, line)
                y -= cook_leading
            y -= cook_leading
        if frozen:
            c.setFont(FB, cook_size)
            c.drawString(x, y, "From Frozen:")
            y -= cook_leading
            c.setFont(FR, cook_size)
            for line in _wrap(c, frozen, FR, cook_size, w):
                c.drawString(x, y, line)
                y -= cook_leading

    _draw_cook(micro_x, micro_w, micro_chilled, micro_frozen, pt(cook_start_y))
    _draw_cook(oven_x, oven_w, oven_chilled, oven_frozen, pt(cook_start_y))

    # ==============================================================
    # NUTRITION TABLE — ABSOLUTE POSITIONING
    # 9 rows in grid: 1 header (pre-printed) + 8 data rows.
    # Energy kJ/kcal combined into one row.
    # Each cell is its own text object. Exact Y coordinates.
    # ==============================================================

    # Data row Y positions (design coords, mm from top)
    # Row 1 (91.4) = header, pre-printed — skip
    # Rows 2-9 = 8 data rows
    NT_DATA_Y = [95.5, 98.6, 101.7, 104.8, 107.9, 110.5, 113.1, 116.2]

    # Column x anchors
    C1_X = pt(NUTRITION_TABLE["x"] + PAD)
    C2_X = pt(61.5)
    C3_X = pt(84.0)

    NT_FONT = 5.5

    pack_weight = float(product.get("pack_weight_g", 0) or 0)
    servings_count = int(product.get("servings", 1) or 1)
    nt_bottom_mm = dy(NUTRITION_TABLE["y"] + NUTRITION_TABLE["h"])

    per_100g = {}
    for field in NUTRITION_FIELDS:
        val = product.get(field, 0)
        try:
            per_100g[field] = float(val) if val else 0
        except (ValueError, TypeError):
            per_100g[field] = 0

    if pack_weight > 0:
        from nutrition_calculator import calculate_per_portion, NUTRITION_UNITS, NUTRITION_LABELS
        per_portion = calculate_per_portion(per_100g, pack_weight, servings_count)

        # Build 8 data rows: Energy combined, then Fat through Salt
        # Row 1: Energy — "kJ/kcal" combined
        kj_100 = round(per_100g.get("energy_kj", 0))
        kcal_100 = round(per_100g.get("energy_kcal", 0))
        kj_p = per_portion.get("energy_kj", 0)
        kcal_p = per_portion.get("energy_kcal", 0)

        data_rows = [
            ("Energy", f"{kj_100}kJ/{kcal_100}kcal", f"{kj_p}kJ/{kcal_p}kcal"),
            ("Fat", f"{per_100g.get('fat', 0):.1f}g", f"{per_portion.get('fat', 0):.1f}g"),
            ("-of which saturates", f"{per_100g.get('saturates', 0):.1f}g", f"{per_portion.get('saturates', 0):.1f}g"),
            ("Carbohydrate", f"{per_100g.get('carbohydrate', 0):.1f}g", f"{per_portion.get('carbohydrate', 0):.1f}g"),
            ("-of which sugars", f"{per_100g.get('sugars', 0):.1f}g", f"{per_portion.get('sugars', 0):.1f}g"),
            ("Fibre", f"{per_100g.get('fibre', 0):.1f}g", f"{per_portion.get('fibre', 0):.1f}g"),
            ("Protein", f"{per_100g.get('protein', 0):.1f}g", f"{per_portion.get('protein', 0):.1f}g"),
            ("Salt", f"{per_100g.get('salt', 0):.1f}g", f"{per_portion.get('salt', 0):.1f}g"),
        ]

        # Place 8 data rows at exact Y positions
        for i, (label, val_100, val_portion) in enumerate(data_rows):
            by = pt(dy(NT_DATA_Y[i]))

            is_sub = label.startswith("-of which")

            # CELL: nutrient label
            c.setFont(FB if not is_sub else FR, NT_FONT)
            c.drawString(C1_X, by, label)

            # CELL: per 100g value
            c.setFont(FR, NT_FONT)
            c2_shift = pt(2.5) if i == 0 else 0  # energy row col 2 shift right 2.5mm total
            c3_shift = pt(1.5) if i == 0 else 0  # energy row col 3 shift right 1.5mm
            c.drawCentredString(C2_X + c2_shift, by, val_100)

            # CELL: per serving value
            c.drawCentredString(C3_X + c3_shift, by, val_portion)

    # ==============================================================
    # INGREDIENTS — below nutrition table
    # ==============================================================
    ingredients_raw = str(product.get("ingredients", ""))
    if ingredients_raw:
        ing_size = 5.5
        ing_html = _allergen_html(ingredients_raw)
        style = ParagraphStyle(
            "ingredients", fontName=FR, fontSize=ing_size,
            leading=ing_size * 0.92,  # 92% tight line height
        )
        para = Paragraph(ing_html, style)
        ing_w = pt(PAGE_W - 10)
        pw, ph = para.wrap(ing_w, pt(30))
        para.drawOn(c, pt(5), pt(nt_bottom_mm - 2) - ph)

    # ==============================================================
    # BOTTOM BOXES — text optically centred, slightly below midpoint
    # ==============================================================
    box_specs = [
        (BOTTOM_BOX_1, batch_code),
        (BOTTOM_BOX_2, str(servings_count)),
        (BOTTOM_BOX_3, f"{int(pack_weight)}g" if pack_weight else ""),
        (USE_BY_BOX, use_by_date),
    ]

    box_font_size = 8
    for box, value in box_specs:
        cx = box["x"] + box["w"] / 2
        box_bottom = dy(box["y"] + box["h"])
        by = _optical_centre_baseline(box_bottom, box["h"], box_font_size)
        c.setFont(FB, box_font_size)
        c.drawCentredString(pt(cx), pt(by), value)

    # ==============================================================
    # BARCODE — inside the QR/white box left of nutrition table
    # QR_BOX: x=6.6, y=94.6, w=26.9, h=18.5
    # ==============================================================
    qb = QR_BOX
    ean = str(product.get("ean", "")).strip()
    if ean:
        try:
            barcode_img = generate_ean_barcode(ean)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                barcode_img.save(tmp, format="PNG")
                tmp_path = tmp.name
            # Fit barcode inside the QR box with padding
            bc_w = pt(qb["w"] - 2)
            bc_h = pt(qb["h"] - 7)  # leave room for number below
            bc_x = pt(qb["x"] + 1)
            bc_y = pt(dy(qb["y"] + qb["h"]) + 5)  # raised to make room for number
            c.drawImage(tmp_path, bc_x, bc_y, width=bc_w, height=bc_h)
            os.unlink(tmp_path)
            # EAN number below barcode, smaller font, centred
            c.setFont(FR, 4)
            num_x = pt(qb["x"] + qb["w"] / 2)
            num_y = pt(dy(qb["y"] + qb["h"]) + 2)
            c.drawCentredString(num_x, num_y, ean)
        except Exception:
            pass

    c.showPage()
    c.save()
    buf.seek(0)
    pdf_bytes = buf.getvalue()

    if overlay_background and os.path.exists(BACKGROUND_PATH):
        pdf_bytes = _overlay_on_background(pdf_bytes)

    return pdf_bytes


def _overlay_on_background(overprint_bytes):
    try:
        from pypdf import PdfReader, PdfWriter
        bg = PdfReader(BACKGROUND_PATH)
        fg = PdfReader(io.BytesIO(overprint_bytes))
        writer = PdfWriter()
        page = bg.pages[0]
        page.merge_page(fg.pages[0])
        writer.add_page(page)
        out = io.BytesIO()
        writer.write(out)
        out.seek(0)
        return out.getvalue()
    except ImportError:
        return overprint_bytes


def generate_batch_labels(products, batch_code, use_by_date, config=None):
    if config is None:
        config = load_config()
    if len(products) == 1:
        return generate_label_pdf(products[0], batch_code, use_by_date, config)
    from io import BytesIO
    pdfs = [generate_label_pdf(p, batch_code, use_by_date, config) for p in products]
    try:
        from pypdf import PdfMerger
        merger = PdfMerger()
        for pdf in pdfs:
            merger.append(BytesIO(pdf))
        output = BytesIO()
        merger.write(output)
        merger.close()
        output.seek(0)
        return output.getvalue()
    except ImportError:
        return pdfs[0]
