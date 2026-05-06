"""Візуальні блок-схеми (SVG):
  1) Організаційна структура роти РРР — org chart
  2) Цикл бойового управління ротою — flowchart
"""
import json

with open('/app/output/structure.json', encoding='utf-8') as f:
    data = json.load(f)


# ============ 1. ORG CHART ============================================
# Стиль: вертикальна ієрархія (ВЦСА/Зелений мілітарі).

W, H = 2600, 1900
node_w, node_h = 220, 70
gap_x, gap_y = 20, 60

def esc(s):
    return (s or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")


# Beautiful military-style theme
THEME = {
    "bg": "#0E1A14",
    "company": {"fill": "#3D5A2C", "stroke": "#A4C26A", "text": "#FFFFFF"},
    "hq":      {"fill": "#5B3A29", "stroke": "#D4A06A", "text": "#FFFFFF"},
    "platoon": {"fill": "#2C4A5E", "stroke": "#7AB8D8", "text": "#FFFFFF"},
    "group":   {"fill": "#4A3D5C", "stroke": "#B8A0D6", "text": "#FFFFFF"},
    "workshop":{"fill": "#5C4A2C", "stroke": "#D8C36A", "text": "#FFFFFF"},
    "squad":   {"fill": "#1F2E22", "stroke": "#8FAA76", "text": "#E8F0D8"},
    "line":    "#7A8B6C",
    "title":   "#E8F0D8",
    "subtitle":"#A4B89A",
}

def style(t):
    return THEME.get(t, THEME["squad"])


# 1) Підрозділи (рівень 2): HQ + Group + Platoons + Workshop
order = data["order"]
# Згрупуємо: HQ окремо зверху, інші — рядом
hq_key = "__HQ__"
others = [k for k in order if k != hq_key]

# Розрахунок ширини
n_others = len(others)
col_w = node_w + gap_x

# Розставимо координати
nodes = []  # {id, x, y, w, h, type, name, sub}

# Title
title_y = 30

# Company root
company_x = (n_others * col_w - gap_x) // 2 - node_w // 2
company_y = 90
nodes.append({"id": "ROOT", "x": company_x, "y": company_y, "w": node_w*1.6, "h": node_h+10,
              "type": "company", "name": data["name"],
              "sub": f"за БЧС: {data['total_personnel']} осіб"})

# HQ — under company root, centered
hq_y = company_y + node_h + 90
hq_x = company_x + (node_w*1.6 - node_w)//2

if hq_key in data["subunits"]:
    sub = data["subunits"][hq_key]
    nodes.append({"id": hq_key, "x": hq_x, "y": hq_y, "w": node_w, "h": node_h,
                  "type": "hq", "name": sub["name"], "sub": f"{sub['count']} осіб"})

# Other subunits row
sub_row_y = hq_y + node_h + 80
for i, k in enumerate(others):
    sub = data["subunits"][k]
    nodes.append({"id": k, "x": i*col_w, "y": sub_row_y, "w": node_w, "h": node_h,
                  "type": sub["type"], "name": sub["name"], "sub": f"{sub['count']} осіб"})

# Squads under each subunit
squad_nodes = {}  # parent_key -> list of squad node ids
sq_y_base = sub_row_y + node_h + 60
max_y = sq_y_base
for k in others:
    sub = data["subunits"][k]
    sub_node = next(n for n in nodes if n["id"] == k)
    squad_keys = [sk for sk in sub["squads"] if sk != "__DIRECT__"]
    if not squad_keys:
        continue
    n_sq = len(squad_keys)
    sq_w = (node_w - (n_sq-1)*8) // n_sq if n_sq > 0 else node_w
    sq_w = max(sq_w, 90)
    for j, sk in enumerate(squad_keys):
        sq = sub["squads"][sk]
        sx = sub_node["x"] + j*(sq_w + 8)
        sy = sq_y_base
        nid = f"{k}::{sk}"
        # short name
        short = sk.replace("Відділення ", "Відд. ").replace("радіорозвідки","РР").replace("радіотехнічної розвідки","РТР")
        nodes.append({"id": nid, "x": sx, "y": sy, "w": sq_w, "h": node_h-10,
                      "type": "squad", "name": short, "sub": f"{len(sq['positions'])} осіб"})
        squad_nodes.setdefault(k, []).append(nid)
        max_y = max(max_y, sy + node_h)

# Розрахунок розміру SVG
total_w = max(n["x"] + n["w"] for n in nodes) + 60
total_h = max_y + 240  # для легенди

# === Build edges ===
edges = []
edges.append(("ROOT", hq_key))
for k in others:
    edges.append(("ROOT", k))
    if k in squad_nodes:
        for sn in squad_nodes[k]:
            edges.append((k, sn))

# Index node by id
N = {n["id"]: n for n in nodes}

def cx(n): return n["x"] + n["w"]/2
def cy_top(n): return n["y"]
def cy_bot(n): return n["y"] + n["h"]


svg = []
svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w} {total_h}" font-family="Arial, sans-serif">')
svg.append(f'<rect width="100%" height="100%" fill="{THEME["bg"]}"/>')

# Background grid pattern
svg.append('<defs>')
svg.append('  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">')
svg.append('    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1A2A1F" stroke-width="0.5"/>')
svg.append('  </pattern>')
# Drop shadow
svg.append('  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">')
svg.append('    <feDropShadow dx="0" dy="3" stdDeviation="3" flood-opacity="0.4"/>')
svg.append('  </filter>')
svg.append('</defs>')
svg.append(f'<rect width="100%" height="100%" fill="url(#grid)"/>')

# Header
svg.append(f'<text x="{total_w//2}" y="36" text-anchor="middle" font-size="22" font-weight="bold" fill="{THEME["title"]}">БЛОК-СХЕМА УПРАВЛІННЯ РОТОЮ — ОРГАНІЗАЦІЙНА СТРУКТУРА</text>')
svg.append(f'<text x="{total_w//2}" y="60" text-anchor="middle" font-size="13" fill="{THEME["subtitle"]}">{esc(data["battalion"])}  •  {esc(data["name"])}  •  всього: {data["total_personnel"]} осіб  •  станом на 02.05.2026</text>')

# Edges (orthogonal: down -> horizontal -> down)
for src_id, dst_id in edges:
    s = N[src_id]; d = N[dst_id]
    sx_, sy_ = cx(s), cy_bot(s)
    dx_, dy_ = cx(d), cy_top(d)
    midy = (sy_ + dy_) / 2
    path = f"M {sx_} {sy_} L {sx_} {midy} L {dx_} {midy} L {dx_} {dy_}"
    svg.append(f'<path d="{path}" stroke="{THEME["line"]}" stroke-width="1.6" fill="none"/>')

# Nodes
for n in nodes:
    st = style(n["type"])
    svg.append(f'<g filter="url(#shadow)">')
    svg.append(f'<rect x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="{n["h"]}" rx="8" ry="8" fill="{st["fill"]}" stroke="{st["stroke"]}" stroke-width="1.5"/>')
    # Тонка верхня смужка
    svg.append(f'<rect x="{n["x"]}" y="{n["y"]}" width="{n["w"]}" height="4" fill="{st["stroke"]}" rx="8" ry="8"/>')
    # Текст
    name = esc(n["name"])
    sub = esc(n.get("sub",""))
    # Перенос довгих
    max_chars = int(n["w"]/8)
    lines = []
    cur = ""
    for w in name.split():
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            lines.append(cur); cur = w
    if cur: lines.append(cur)
    if len(lines) > 2: lines = [lines[0], " ".join(lines[1:])[:max_chars-1] + "…"]
    fz = 12 if n["type"] == "company" else (11 if n["type"] in ("hq","platoon","group","workshop") else 10)
    fy = n["y"] + 22
    for line in lines:
        svg.append(f'<text x="{n["x"]+n["w"]/2}" y="{fy}" text-anchor="middle" font-size="{fz}" font-weight="bold" fill="{st["text"]}">{line}</text>')
        fy += fz + 2
    if sub:
        svg.append(f'<text x="{n["x"]+n["w"]/2}" y="{n["y"]+n["h"]-12}" text-anchor="middle" font-size="9" fill="{st["text"]}" opacity="0.85">{sub}</text>')
    svg.append('</g>')

# Легенда
ly = max_y + 60
svg.append(f'<text x="20" y="{ly}" font-size="13" font-weight="bold" fill="{THEME["title"]}">УМОВНІ ПОЗНАЧЕННЯ:</text>')
legend = [
    ("company",  "Рота"),
    ("hq",       "Управління"),
    ("group",    "Група"),
    ("platoon",  "Взвод"),
    ("workshop", "Майстерня"),
    ("squad",    "Відділення"),
]
lx = 20
ly += 20
for t, lbl in legend:
    st = style(t)
    svg.append(f'<rect x="{lx}" y="{ly}" width="22" height="14" rx="3" fill="{st["fill"]}" stroke="{st["stroke"]}"/>')
    svg.append(f'<text x="{lx+30}" y="{ly+11}" font-size="11" fill="{THEME["subtitle"]}">{lbl}</text>')
    lx += 160

svg.append('</svg>')

with open('/app/output/Блок-схема - Організаційна структура.svg', 'w', encoding='utf-8') as f:
    f.write("\n".join(svg))
print("OK: Org chart SVG")


# ============ 2. CHAIN OF COMMAND / COMBAT MGMT ========================
# Цикл бойового управління — flowchart
phases = [
    ("I. Підготовка управління", "#3D5A2C", [
        "1. Отримання бойового завдання від КБ",
        "2. З'ясування завдання, виділення задач",
        "3. Орієнтування заступників і КВ",
        "4. Розрахунок часу"
    ]),
    ("II. Оцінка обстановки", "#2C4A5E", [
        "5. Противник",
        "6. Свої сили та засоби",
        "7. Район дій, маршрути",
        "8. Час, метеоумови",
        "9. Тил, медицина, психологія"
    ]),
    ("III. Прийняття рішення", "#5B3A29", [
        "10. Формування задуму",
        "11. Визначення задач і взаємодії",
        "12. Доповідь рішення командиру батальйону"
    ]),
    ("IV. Постановка задач", "#4A3D5C", [
        "13. Бойовий наказ по роті",
        "14. ГОІ",
        "15. 1 Взвод РР",
        "16. 2 Взвод РР",
        "17. Взвод РЕР",
        "18. Взвод БпАК",
        "19. РМО"
    ]),
    ("V. Забезпечення та взаємодія", "#5C4A2C", [
        "20. Розвід.-інф. обмін",
        "21. Зв'язок та управління",
        "22. Тил, ЗІП, ПММ, харчування",
        "23. Медичне забезпечення",
        "24. Психологічна підтримка"
    ]),
    ("VI. Контроль і виконання", "#3D5A2C", [
        "25. Контроль готовності",
        "26. Виконання БЗ — ведення розвідки",
        "27. Поточний контроль і коригування"
    ]),
    ("VII. Доповіді та підсумки", "#2C4A5E", [
        "28. Поточні доповіді до КБ",
        "29. Підсумкова доповідь за добу",
        "30. Постановка задач на наст. добу"
    ]),
]

W2 = 2400
node_w2 = 230
node_h2 = 50
phase_h = 36
gap2 = 14
margin = 30
title_h = 90

# Розрахунок висоти
phase_y_list = []
y = title_h + 30
for ph_name, color, items in phases:
    phase_y_list.append(y)
    y += phase_h + 14 + len(items)*(node_h2+gap2) + 30
H2 = y + 30

svg2 = []
svg2.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W2} {H2}" font-family="Arial, sans-serif">')
svg2.append(f'<rect width="100%" height="100%" fill="{THEME["bg"]}"/>')
svg2.append('<defs>')
svg2.append('  <pattern id="grid2" width="40" height="40" patternUnits="userSpaceOnUse">')
svg2.append('    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1A2A1F" stroke-width="0.5"/>')
svg2.append('  </pattern>')
svg2.append('  <filter id="sh2" x="-20%" y="-20%" width="140%" height="140%">')
svg2.append('    <feDropShadow dx="0" dy="3" stdDeviation="3" flood-opacity="0.4"/>')
svg2.append('  </filter>')
svg2.append('  <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">')
svg2.append(f'    <path d="M 0 0 L 10 5 L 0 10 z" fill="{THEME["line"]}"/>')
svg2.append('  </marker>')
svg2.append('</defs>')
svg2.append('<rect width="100%" height="100%" fill="url(#grid2)"/>')

# Title
svg2.append(f'<text x="{W2//2}" y="40" text-anchor="middle" font-size="24" font-weight="bold" fill="{THEME["title"]}">БЛОК-СХЕМА БОЙОВОГО УПРАВЛІННЯ РОТОЮ РРР</text>')
svg2.append(f'<text x="{W2//2}" y="68" text-anchor="middle" font-size="13" fill="{THEME["subtitle"]}">Цикл управління (24 год) • {esc(data["name"])} • {esc(data["battalion"])}</text>')

# Render phases
prev_phase_last_node = None
node_id_counter = 0
all_nodes = {}  # id -> (cx, cy)
for ph_idx, (ph_name, color, items) in enumerate(phases):
    py = phase_y_list[ph_idx]
    # Phase header band
    svg2.append(f'<rect x="{margin}" y="{py}" width="{W2-2*margin}" height="{phase_h}" rx="6" ry="6" fill="{color}" opacity="0.92" filter="url(#sh2)"/>')
    svg2.append(f'<text x="{margin+18}" y="{py+phase_h*0.66}" font-size="14" font-weight="bold" fill="#FFFFFF">{esc(ph_name)}</text>')

    # Items: arranged in columns inside the phase band
    n = len(items)
    cols = min(n, 5)
    # if more than 5 — wrap
    rows = (n + cols - 1)//cols
    col_w_p = (W2 - 2*margin - (cols-1)*gap2) // cols
    iy0 = py + phase_h + 16
    last_in_phase = []
    first_in_phase = []
    for idx, item in enumerate(items):
        r = idx // cols
        c = idx % cols
        ix = margin + c * (col_w_p + gap2)
        iy = iy0 + r * (node_h2 + gap2)
        nid = f"P{ph_idx}-{idx}"
        all_nodes[nid] = (ix, iy, col_w_p, node_h2)

        # Draw node
        svg2.append(f'<g filter="url(#sh2)">')
        svg2.append(f'<rect x="{ix}" y="{iy}" width="{col_w_p}" height="{node_h2}" rx="6" ry="6" fill="#1F2E22" stroke="{color}" stroke-width="1.8"/>')
        svg2.append(f'<rect x="{ix}" y="{iy}" width="6" height="{node_h2}" fill="{color}" rx="6" ry="6"/>')
        # Item text — wrap to 2 lines if needed
        max_chars = max(int(col_w_p/7), 14)
        words = item.split()
        lines = []
        cur = ""
        for w in words:
            if len(cur)+len(w)+1 <= max_chars:
                cur = (cur+" "+w).strip()
            else:
                lines.append(cur); cur = w
        if cur: lines.append(cur)
        if len(lines)>2: lines = [lines[0], " ".join(lines[1:])]
        fy = iy + (node_h2 - len(lines)*14)/2 + 12
        for line in lines:
            svg2.append(f'<text x="{ix+15}" y="{fy}" font-size="11" fill="#E8F0D8">{esc(line)}</text>')
            fy += 14
        svg2.append('</g>')
        if idx == 0: first_in_phase.append(nid)
        if idx == len(items)-1: last_in_phase.append(nid)

        # Стрілки в межах фази (послідовність)
        if idx > 0:
            prev_id = f"P{ph_idx}-{idx-1}"
            px, py_, pw, ph_h = all_nodes[prev_id]
            # якщо в одному рядку — горизонтальна
            if py_ == iy:
                x1 = px + pw; y1 = py_ + ph_h/2
                x2 = ix; y2 = iy + node_h2/2
                svg2.append(f'<path d="M {x1} {y1} L {x2-5} {y2}" stroke="{THEME["line"]}" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>')
            else:
                # перехід на новий рядок — округла
                x1 = px + pw/2; y1 = py_ + ph_h
                x2 = ix + col_w_p/2; y2 = iy
                svg2.append(f'<path d="M {x1} {y1} L {x1} {y1+8} L {x2} {y1+8} L {x2} {y2-2}" stroke="{THEME["line"]}" stroke-width="1.5" fill="none" marker-end="url(#arr)"/>')

    # Стрілка від попередньої фази → перша задача поточної
    if prev_phase_last_node:
        px, py_, pw, ph_h = all_nodes[prev_phase_last_node]
        fid = first_in_phase[0]
        fx, fy_, fw, fh = all_nodes[fid]
        # Велика стрілка
        x1 = px + pw/2; y1 = py_ + ph_h
        x2 = fx + fw/2; y2 = fy_
        midy = (y1 + y2) / 2
        svg2.append(f'<path d="M {x1} {y1} L {x1} {midy} L {x2} {midy} L {x2} {y2-2}" stroke="{THEME["line"]}" stroke-width="2.5" fill="none" marker-end="url(#arr)" stroke-dasharray="6,3"/>')
    prev_phase_last_node = last_in_phase[-1]

# Cycle return arrow (від останнього → до першого)
fid = "P0-0"
lid = prev_phase_last_node
fx, fy_, fw, fh = all_nodes[fid]
lx, ly_, lw, lh = all_nodes[lid]
# Велика дуга справа
svg2.append(f'<path d="M {lx+lw} {ly_+lh/2} L {W2-15} {ly_+lh/2} L {W2-15} {fy_+fh/2} L {fx+fw} {fy_+fh/2}" stroke="#D4A06A" stroke-width="2" fill="none" marker-end="url(#arr)" stroke-dasharray="4,4" opacity="0.8"/>')
svg2.append(f'<text x="{W2-22}" y="{(ly_+fy_)/2 + fh/2}" font-size="10" fill="#D4A06A" text-anchor="end">наступна доба</text>')

svg2.append('</svg>')

with open('/app/output/Блок-схема - Бойове управління.svg', 'w', encoding='utf-8') as f:
    f.write("\n".join(svg2))
print("OK: Combat mgmt SVG")
