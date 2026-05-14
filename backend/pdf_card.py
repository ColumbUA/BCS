"""Генерація PDF особової картки солдата.

Використовує reportlab з шрифтом FreeSans (підтримка кирилиці).
Однопоточна верстка: 1-2 сторінки A4.
"""
import io
import datetime
from pathlib import Path
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from deps import DOCUMENT_TYPES, DOC_STATUS_LABELS, LOCATION_STATUSES

# ============================ FONT REGISTRATION ============================

_FONT_REG = "PDFCardFont"
_FONT_BOLD = "PDFCardFontBold"

_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/freefont/FreeSans.ttf",
     "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
]


def _ensure_fonts():
    """Зареєструвати шрифти один раз."""
    if _FONT_REG in pdfmetrics.getRegisteredFontNames():
        return
    for reg, bld in _FONT_CANDIDATES:
        if Path(reg).exists() and Path(bld).exists():
            pdfmetrics.registerFont(TTFont(_FONT_REG, reg))
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, bld))
            return
    # Fallback: вбудовані Vera-шрифти reportlab — для кирилиці погано, але хоч щось
    pdfmetrics.registerFont(TTFont(_FONT_REG, "Vera.ttf"))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, "VeraBd.ttf"))


# ============================ HELPERS ============================

PAGE_W, PAGE_H = A4
MARGIN_L = 18 * mm
MARGIN_R = 18 * mm
MARGIN_T = 18 * mm
MARGIN_B = 18 * mm


def _wrap(c: canvas.Canvas, text: str, max_width: float, font: str, size: int) -> list[str]:
    """Простий wrap по ширині (без перенесення слова)."""
    if not text:
        return [""]
    words = text.split(" ")
    lines = []
    cur = ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if c.stringWidth(cand, font, size) <= max_width:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines or [""]


# ============================ MAIN ============================

def render_soldier_pdf(soldier: dict,
                       settings: Optional[dict] = None,
                       company_name: str = "",
                       transfers: Optional[list] = None,
                       documents: Optional[list] = None) -> tuple[io.BytesIO, str]:
    """Згенерувати PDF особову картку солдата.

    Returns (BytesIO, filename).
    """
    _ensure_fonts()
    settings = settings or {}
    transfers = transfers or []
    documents = documents or []

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Особова картка — {soldier.get('fio', '')}")

    # Шапка
    y = PAGE_H - MARGIN_T

    c.setFont(_FONT_BOLD, 7)
    c.drawString(MARGIN_L, y, "CONFIDENTIAL — DSTU/НСД")
    c.drawRightString(PAGE_W - MARGIN_R, y, datetime.date.today().strftime("%Y-%m-%d"))
    y -= 6

    # Лінія
    c.setStrokeColorRGB(0.3, 0.4, 0.25)
    c.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)
    y -= 10

    # Назва частини
    c.setFont(_FONT_REG, 9)
    if settings.get("unit_short_name") or settings.get("unit_name"):
        c.drawString(MARGIN_L, y, settings.get("unit_short_name") or settings.get("unit_name", ""))
        y -= 10
    if company_name:
        c.setFont(_FONT_BOLD, 11)
        c.drawString(MARGIN_L, y, company_name)
        y -= 14

    # Title
    c.setFont(_FONT_BOLD, 16)
    c.drawString(MARGIN_L, y, "ОСОБОВА КАРТКА")
    y -= 18

    # FIO + callsign + rank
    c.setFont(_FONT_BOLD, 13)
    fio = soldier.get("fio", "")
    callsign = soldier.get("callsign", "")
    name_line = fio + (f"  «{callsign}»" if callsign else "")
    c.drawString(MARGIN_L, y, name_line)
    y -= 14

    c.setFont(_FONT_REG, 10)
    pos_rank = " • ".join(filter(None, [
        soldier.get("rank", ""),
        soldier.get("position", ""),
        soldier.get("node_path", ""),
    ]))
    for line in _wrap(c, pos_rank, PAGE_W - MARGIN_L - MARGIN_R, _FONT_REG, 10):
        c.drawString(MARGIN_L, y, line)
        y -= 12
    y -= 4

    # Розділ "Дані"
    def section_title(text):
        nonlocal y
        c.setStrokeColorRGB(0.5, 0.6, 0.4)
        c.setFont(_FONT_BOLD, 9)
        c.setFillColorRGB(0.32, 0.4, 0.25)
        c.drawString(MARGIN_L, y, text.upper())
        c.setFillColorRGB(0, 0, 0)
        y -= 4
        c.line(MARGIN_L, y, PAGE_W - MARGIN_R, y)
        y -= 10

    def row(label, value):
        nonlocal y
        c.setFont(_FONT_BOLD, 9)
        c.drawString(MARGIN_L, y, f"{label}:")
        c.setFont(_FONT_REG, 9)
        lab_w = c.stringWidth(f"{label}:  ", _FONT_BOLD, 9)
        max_w = PAGE_W - MARGIN_L - MARGIN_R - lab_w
        lines = _wrap(c, str(value or "—"), max_w, _FONT_REG, 9)
        for i, ln in enumerate(lines):
            x = MARGIN_L + lab_w if i == 0 else MARGIN_L + lab_w
            c.drawString(x, y, ln)
            y -= 11
        y -= 2

    section_title("Загальні дані")
    row("Дата народження", soldier.get("birth_date", ""))
    row("Дата мобілізації", soldier.get("mobilized_at", ""))
    row("Група крові", soldier.get("blood_group", ""))
    row("Водійське посвідчення", "так" if soldier.get("has_driver_license") else "ні")

    section_title("Підготовка")
    row("БЗВП пройдено", soldier.get("bzvp_passed_at", ""))
    row("КТЗ пройдено", soldier.get("ktz_passed_at", ""))

    section_title("Локація")
    row("Стан", soldier.get("location_status", "—"))
    row("Місце", soldier.get("location_place", "—"))
    row("Оновлено", soldier.get("location_updated_at", "")[:19].replace("T", " "))

    # Освіта
    edu = soldier.get("education") or []
    if edu:
        section_title("Освіта")
        for e in edu:
            txt = " • ".join(filter(None, [
                e.get("degree", ""), e.get("institution", ""),
                e.get("year", ""), e.get("specialty", ""),
            ]))
            row("—", txt)

    # Сертифікати
    certs = soldier.get("certificates") or []
    if certs:
        section_title("Сертифікати")
        for cert in certs:
            txt = " • ".join(filter(None, [
                cert.get("name", ""), cert.get("issued_at", ""), cert.get("issuer", ""),
            ]))
            row("—", txt)

    # Документи
    if documents:
        section_title("Документи")
        for d in documents:
            t_lbl = DOCUMENT_TYPES.get(d.get("type", ""), d.get("type", "Інше"))
            st = DOC_STATUS_LABELS.get(d.get("status", ""), d.get("status", ""))
            txt = f"{t_lbl} • {d.get('filename', '')[:60]} • [{st}]"
            row("—", txt)

    # Переміщення
    if transfers:
        if y < MARGIN_B + 100:
            c.showPage()
            y = PAGE_H - MARGIN_T
            c.setFont(_FONT_BOLD, 11)
            c.drawString(MARGIN_L, y, f"Продовження картки — {fio}")
            y -= 18
        section_title("Переміщення")
        for t in transfers[:20]:
            txt = " • ".join(filter(None, [
                t.get("effective_date") or t.get("created_at", "")[:10],
                t.get("transfer_type", ""),
                f"{t.get('from_node_path', '?')} → {t.get('to_node_path', '?')}",
                f"[{t.get('status', '')}]",
            ]))
            row("—", txt)

    if soldier.get("notes"):
        section_title("Примітки")
        c.setFont(_FONT_REG, 9)
        for line in _wrap(c, soldier["notes"], PAGE_W - MARGIN_L - MARGIN_R, _FONT_REG, 9):
            c.drawString(MARGIN_L, y, line)
            y -= 11

    # Footer
    c.setFont(_FONT_REG, 7)
    c.setFillColorRGB(0.5, 0.5, 0.5)
    footer = f"Сформовано автоматично • {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} • {settings.get('unit_short_name', '') or company_name}"
    c.drawCentredString(PAGE_W / 2, MARGIN_B / 2, footer)

    c.showPage()
    c.save()
    buf.seek(0)

    safe_fio = fio.replace(" ", "_").replace("/", "-")
    filename = f"Особова_картка_{safe_fio}_{datetime.date.today().strftime('%Y-%m-%d')}.pdf"
    return buf, filename
