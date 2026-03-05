import numpy as np
import math
import os
from ipycanvas import Canvas, hold_canvas
import ipywidgets as W
from IPython.display import display

# =============================
# Config
# =============================
GRID_UNIT = 10
WID, HEI = 900, 550

PICK_R_PX_MIN = 10

A_DEFAULT = 1.0
I_DEFAULT = 1.0
PHI_DEFAULT = 0.0

FX_DEFAULT = 0.0
FY_DEFAULT = -1.0
M_DEFAULT  = 0.0

# Default support (pinned): Ux, Uy fixed; R free
SUP_UX_DEFAULT = 1
SUP_UY_DEFAULT = 1
SUP_RZ_DEFAULT = 0

# --- pixel-constant symbol sizes (independent of zoom) ---
SUP_SIZE_PX   = 18   # Support size
SUP_GAP_PX    = 4
LOAD_LEN_PX   = 40   # Arrow length
LOAD_HEAD_PX  = 10   # Arrow head
MOM_RADIUS_PX = 16   # Moment radius

# =============================
# Data (NumPy)
# =============================
nodes = np.zeros((0, 3), dtype=int)          # [id, xg, yg]
next_node_id = 1

bars = np.zeros((0, 6), dtype=float)         # [id, n1, n2, A, I, phi_deg]
next_bar_id = 1

loads = np.zeros((0, 5), dtype=float)        # [id, nid, Fx, Fy, M]
next_load_id = 1

supports = np.zeros((0, 5), dtype=int)       # [id, nid, ux_fix, uy_fix, rz_fix]
next_sup_id = 1

history = []  # ("add_node", nid) / ("add_bar", bid) / ("add_load", lid) / ("add_sup", sid)

# =============================
# UI (widgets)
# =============================
# --- Tool buttons (no HTML/CSS injection; active = "primary" like Undo)
tool_value = "node"

btn_node = W.Button(description="Node",    button_style="primary")
btn_bar  = W.Button(description="Bar",     button_style="")
btn_load = W.Button(description="Load",    button_style="")
btn_sup  = W.Button(description="Support", button_style="")
btn_pan  = W.Button(description="Ansicht",     button_style="")

for b in [btn_node, btn_bar, btn_load, btn_sup, btn_pan]:
    b.layout = W.Layout(width="140px", height="38px")

tool_grid = W.GridBox(
    children=[btn_node, btn_bar, btn_load, btn_sup, btn_pan],
    layout=W.Layout(
        grid_template_columns="repeat(2, 140px)",
        grid_gap="8px",
        justify_content="flex-start"
    )
)

zoom_px = W.IntSlider(value=25, min=10, max=140, step=5, description="Zoom")

undo_btn   = W.Button(description="Undo", button_style="primary")
clear_btn  = W.Button(description="Clear", button_style="danger")
export_btn = W.Button(description="Export", button_style="success")

# Keep in code but do not show
save_chk   = W.Checkbox(value=True, description="Save txt")
save_chk.layout = W.Layout(display="none")

E_in = W.FloatText(value=2.0e8, description="E-Modul", step=1e6)

# ---- Bar edit widgets
edit_bar_btn = W.Button(description="Edit Bar", button_style="primary", disabled=True)
bar_id_lbl   = W.HTML("<b>Bar:</b> -")
A_in   = W.FloatText(description="A", value=A_DEFAULT, disabled=True)
I_in   = W.FloatText(description="I", value=I_DEFAULT, disabled=True)
phi_in = W.FloatText(description="φ [deg]", value=PHI_DEFAULT, disabled=True)
apply_bar_btn = W.Button(description="Apply", button_style="success", disabled=True)
bar_box = W.VBox(
    [bar_id_lbl, edit_bar_btn, A_in, I_in, phi_in, apply_bar_btn],
    layout=W.Layout(padding="6px", width="100%")
)

# ---- Load edit widgets
edit_load_btn = W.Button(description="Edit Load", button_style="primary", disabled=True)
load_id_lbl   = W.HTML("<b>Load:</b> -")
Fx_in = W.FloatText(description="x_Force", value=FX_DEFAULT, disabled=True)
Fy_in = W.FloatText(description="y_Force", value=FY_DEFAULT, disabled=True)
M_in  = W.FloatText(description="Moment",  value=M_DEFAULT,  disabled=True)
apply_load_btn = W.Button(description="Apply", button_style="success", disabled=True)
load_box = W.VBox(
    [load_id_lbl, edit_load_btn, Fx_in, Fy_in, M_in, apply_load_btn],
    layout=W.Layout(padding="6px", width="100%")
)

# ---- Support edit widgets
edit_sup_btn = W.Button(description="Edit Support", button_style="primary", disabled=True)
sup_id_lbl   = W.HTML("<b>Support:</b> -")
ux_chk = W.Checkbox(value=True,  description="Horizontal Displacement", disabled=True)
uy_chk = W.Checkbox(value=True,  description="Vertical Displacement",   disabled=True)
rz_chk = W.Checkbox(value=False, description="Rotation",                disabled=True)
apply_sup_btn = W.Button(description="Apply", button_style="success", disabled=True)
sup_box = W.VBox(
    [sup_id_lbl, edit_sup_btn, ux_chk, uy_chk, rz_chk, apply_sup_btn],
    layout=W.Layout(padding="6px", width="100%")
)

# ---- Accordion
props_accordion = W.Accordion(children=[bar_box, load_box, sup_box], selected_index=None)
props_accordion.set_title(0, "Bar Properties")
props_accordion.set_title(1, "Load Properties")
props_accordion.set_title(2, "Support Properties")
props_accordion.layout = W.Layout(width="100%")

status = W.HTML("")

# =============================
# UI layout (no HTML for tools)
# =============================
# =============================
# UI layout (tools fixed, body scrolls)
# =============================

# Tool headline bold
tool_label = W.HTML("<b>Tool</b>")
tool_label.layout = W.Layout(margin="0 0 2px 0")

tool_block = W.VBox(
    [tool_label, tool_grid],
    layout=W.Layout(margin="0 0 10px 0")
)

BTN_W = "118px"
BTN_H = "34px"
for b in [undo_btn, clear_btn, export_btn]:
    b.layout = W.Layout(width=BTN_W, height=BTN_H)
undo_btn.layout.margin = "0 8px 0 0"
clear_btn.layout.margin = "0 8px 0 0"
export_btn.layout.margin = "0 0 0 0"

row_actions = W.HBox(
    children=[undo_btn, clear_btn, export_btn],
    layout=W.Layout(justify_content="flex-start", align_items="center", margin="0 0 8px 0")
)

zoom_px.layout = W.Layout(margin="0 0 10px 0")
E_in.layout    = W.Layout(margin="0 0 10px 0")
props_accordion.layout = W.Layout(margin="0 0 12px 0", width="100%")
status.layout = W.Layout(margin="6px 0 0 0")

# Body: only this part scrolls (accordion etc.)
right_body = W.VBox(
    [props_accordion, zoom_px, E_in, row_actions, status],
    layout=W.Layout(
        width="100%",
        overflow="auto",
        max_height=f"calc({HEI}px - 110px)",  # reserve space for tool header/grid
        padding="0 2px 0 0"
    )
)

# Right panel: tools stay visible, body scrolls
right_panel = W.VBox(
    [tool_block, right_body],
    layout=W.Layout(width="430px", padding="6px 8px", max_height=f"{HEI}px")
)

# =============================
# Canvas
# =============================
canvas = Canvas(width=WID, height=HEI)
canvas.layout = W.Layout(
    border="1px solid #444",
    width=f"{WID}px",
    height=f"{HEI}px",
    min_width=f"{WID}px",
    min_height=f"{HEI}px",
    flex="0 0 auto"
)

ui = W.HBox([canvas, right_panel], layout=W.Layout(align_items="flex-start", justify_content="flex-start"))
display(ui)

# =============================
# State
# =============================
state = {
    "hover_node": -1,
    "selected_node": -1,
    "pending_n1": -1,

    "hover_bar": -1,
    "selected_bar": -1,

    "hover_load": -1,
    "selected_load": -1,

    "hover_sup": -1,
    "selected_sup": -1,

    # pan (pixel offsets)
    "pan_x": 0.0,
    "pan_y": 0.0,
    "panning": False,
    "pan_last": (0.0, 0.0),
}

# =============================
# Coordinate transforms (with PAN)
# =============================
def base_y():
    g = int(zoom_px.value)
    return (canvas.height // g) * g

def world_origin_px():
    return float(state["pan_x"]), float(base_y() + state["pan_y"])

def grid_to_px(xg, yg):
    g = int(zoom_px.value)
    x = float(xg * g + state["pan_x"])
    y = float(base_y() - yg * g + state["pan_y"])
    return x, y

def px_to_grid(xp, yp):
    g = int(zoom_px.value)
    xg = int(round((xp - state["pan_x"]) / g))
    yg = int(round((base_y() + state["pan_y"] - yp) / g))
    return xg, yg

def clamp_grid(xg, yg):
    # with pan -> no clamp
    return int(xg), int(yg)

# =============================
# Helpers (nodes)
# =============================
def node_index_by_id(nid):
    if nodes.size == 0:
        return -1
    idx = np.where(nodes[:, 0] == int(nid))[0]
    return int(idx[0]) if idx.size else -1

def find_node_at_grid(xg, yg):
    if nodes.size == 0:
        return -1
    mask = (nodes[:, 1] == int(xg)) & (nodes[:, 2] == int(yg))
    idx = np.where(mask)[0]
    return int(nodes[idx[0], 0]) if idx.size else -1

def pick_node_px(xp, yp):
    if nodes.size == 0:
        return -1
    g = int(zoom_px.value)
    xs = nodes[:, 1].astype(float) * g + state["pan_x"]
    ys = (base_y() - nodes[:, 2].astype(float) * g) + state["pan_y"]
    d = np.sqrt((xs - xp)**2 + (ys - yp)**2)
    j = int(np.argmin(d))
    r = max(PICK_R_PX_MIN, int(0.25 * g))
    return int(nodes[j, 0]) if d[j] <= r else -1

def add_node_grid(xg, yg):
    global nodes, next_node_id
    existing = find_node_at_grid(xg, yg)
    if existing != -1:
        return existing, False
    nid = next_node_id
    row = np.array([[nid, xg, yg]], dtype=int)
    nodes = row if nodes.size == 0 else np.vstack([nodes, row])
    next_node_id += 1
    history.append(("add_node", nid))
    return nid, True

# =============================
# Helpers (bars)
# =============================
def bar_index_by_id(bid):
    if bars.size == 0:
        return -1
    idx = np.where(bars[:, 0].astype(int) == int(bid))[0]
    return int(idx[0]) if idx.size else -1

def bar_exists(n1, n2):
    if bars.size == 0:
        return False
    a = bars[:, 1].astype(int)
    b = bars[:, 2].astype(int)
    return bool(np.any(((a == n1) & (b == n2)) | ((a == n2) & (b == n1))))

def compute_phi_deg(n1, n2):
    i1 = node_index_by_id(n1)
    i2 = node_index_by_id(n2)
    if i1 < 0 or i2 < 0:
        return 0.0
    x1 = float(nodes[i1, 1] * GRID_UNIT)
    y1 = float(nodes[i1, 2] * GRID_UNIT)
    x2 = float(nodes[i2, 1] * GRID_UNIT)
    y2 = float(nodes[i2, 2] * GRID_UNIT)
    return math.degrees(math.atan2(y2 - y1, x2 - x1))

def add_bar(n1, n2):
    global bars, next_bar_id
    if n1 == -1 or n2 == -1 or n1 == n2:
        return -1, False
    if bar_exists(n1, n2):
        return -1, False
    bid = next_bar_id
    phi = compute_phi_deg(n1, n2)
    row = np.array([[bid, n1, n2, A_DEFAULT, I_DEFAULT, phi]], dtype=float)
    bars = row if bars.size == 0 else np.vstack([bars, row])
    next_bar_id += 1
    history.append(("add_bar", bid))
    return bid, True

def remove_bar_by_id(bid):
    global bars
    if bars.size == 0:
        return
    idx = np.where(bars[:, 0].astype(int) == int(bid))[0]
    if idx.size:
        bars = np.delete(bars, int(idx[0]), axis=0)

def point_segment_distance(px, py, x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    vv = vx*vx + vy*vy
    if vv == 0:
        return math.hypot(px - x1, py - y1)
    t = (wx*vx + wy*vy) / vv
    t = max(0.0, min(1.0, t))
    projx = x1 + t * vx
    projy = y1 + t * vy
    return math.hypot(px - projx, py - projy)

def pick_bar_px(xp, yp):
    if bars.size == 0:
        return -1
    g = int(zoom_px.value)
    tol = max(8, int(0.20 * g))
    best_bid, best_d = -1, 1e9
    for r in bars:
        bid = int(r[0])
        n1 = int(r[1]); n2 = int(r[2])
        i1 = node_index_by_id(n1)
        i2 = node_index_by_id(n2)
        if i1 < 0 or i2 < 0:
            continue
        x1, y1 = grid_to_px(int(nodes[i1, 1]), int(nodes[i1, 2]))
        x2, y2 = grid_to_px(int(nodes[i2, 1]), int(nodes[i2, 2]))
        d = point_segment_distance(xp, yp, x1, y1, x2, y2)
        if d < best_d:
            best_d, best_bid = d, bid
    return best_bid if best_d <= tol else -1

# =============================
# Helpers (loads)
# =============================
def load_index_by_id(lid):
    if loads.size == 0:
        return -1
    idx = np.where(loads[:, 0].astype(int) == int(lid))[0]
    return int(idx[0]) if idx.size else -1

def add_load_at_node(nid):
    global loads, next_load_id
    if nid == -1 or node_index_by_id(nid) < 0:
        return -1, False
    lid = next_load_id
    row = np.array([[lid, nid, FX_DEFAULT, FY_DEFAULT, M_DEFAULT]], dtype=float)
    loads = row if loads.size == 0 else np.vstack([loads, row])
    next_load_id += 1
    history.append(("add_load", lid))
    return lid, True

def remove_load_by_id(lid):
    global loads
    if loads.size == 0:
        return
    idx = np.where(loads[:, 0].astype(int) == int(lid))[0]
    if idx.size:
        loads = np.delete(loads, int(idx[0]), axis=0)

def load_anchor_px(lid):
    idx = load_index_by_id(lid)
    if idx < 0:
        return None
    nid = int(loads[idx, 1])
    ni = node_index_by_id(nid)
    if ni < 0:
        return None
    x0, y0 = grid_to_px(int(nodes[ni, 1]), int(nodes[ni, 2]))
    return (x0, y0)  # anchor = node

def pick_load_px(xp, yp):
    if loads.size == 0:
        return -1
    tol = max(12, int(0.6 * LOAD_LEN_PX))
    best_lid, best_d = -1, 1e9
    for r in loads:
        lid = int(r[0])
        anc = load_anchor_px(lid)
        if anc is None:
            continue
        ax, ay = anc
        d = math.hypot(xp - ax, yp - ay)
        if d < best_d:
            best_d, best_lid = d, lid
    return best_lid if best_d <= tol else -1

# =============================
# Helpers (supports)
# =============================
def sup_index_by_id(sid):
    if supports.size == 0:
        return -1
    idx = np.where(supports[:, 0] == int(sid))[0]
    return int(idx[0]) if idx.size else -1

def sup_id_at_node(nid):
    if supports.size == 0:
        return -1
    idx = np.where(supports[:, 1] == int(nid))[0]
    return int(supports[idx[0], 0]) if idx.size else -1

def add_support_at_node(nid):
    global supports, next_sup_id
    if nid == -1 or node_index_by_id(nid) < 0:
        return -1, False
    existing = sup_id_at_node(nid)
    if existing != -1:
        return existing, False
    sid = next_sup_id
    row = np.array([[sid, nid, SUP_UX_DEFAULT, SUP_UY_DEFAULT, SUP_RZ_DEFAULT]], dtype=int)
    supports = row if supports.size == 0 else np.vstack([supports, row])
    next_sup_id += 1
    history.append(("add_sup", sid))
    return sid, True

def remove_support_by_id(sid):
    global supports
    if supports.size == 0:
        return
    idx = np.where(supports[:, 0] == int(sid))[0]
    if idx.size:
        supports = np.delete(supports, int(idx[0]), axis=0)

def support_anchor_px(sid):
    si = sup_index_by_id(sid)
    if si < 0:
        return None
    nid = int(supports[si, 1])
    ni = node_index_by_id(nid)
    if ni < 0:
        return None
    x0, y0 = grid_to_px(int(nodes[ni, 1]), int(nodes[ni, 2]))
    return (x0, y0)  # anchor = node

def pick_support_px(xp, yp):
    if supports.size == 0:
        return -1
    tol = max(14, int(1.3 * SUP_SIZE_PX))
    best_sid, best_d = -1, 1e9
    for r in supports:
        sid = int(r[0])
        anc = support_anchor_px(sid)
        if anc is None:
            continue
        ax, ay = anc
        d = math.hypot(xp - ax, yp - ay)
        if d < best_d:
            best_d, best_sid = d, sid
    return best_sid if best_d <= tol else -1

# =============================
# Consistent delete when removing node
# =============================
def remove_node_and_attached_objects(nid):
    global nodes, bars, loads, supports

    if bars.size:
        n1 = bars[:, 1].astype(int)
        n2 = bars[:, 2].astype(int)
        bars = bars[~((n1 == int(nid)) | (n2 == int(nid)))]

    if loads.size:
        loads = loads[~(loads[:, 1].astype(int) == int(nid))]

    if supports.size:
        supports = supports[~(supports[:, 1] == int(nid))]

    idx = node_index_by_id(nid)
    if idx >= 0:
        nodes = np.delete(nodes, idx, axis=0)

# =============================
# Drawing primitives
# =============================
def draw_arrow(x1, y1, x2, y2, head_len=10, head_ang_deg=25):
    canvas.begin_path()
    canvas.move_to(x1, y1)
    canvas.line_to(x2, y2)
    canvas.stroke()

    ang = math.atan2(y2 - y1, x2 - x1)
    a = math.radians(head_ang_deg)
    hl = head_len

    xh1 = x2 - hl * math.cos(ang - a)
    yh1 = y2 - hl * math.sin(ang - a)
    xh2 = x2 - hl * math.cos(ang + a)
    yh2 = y2 - hl * math.sin(ang + a)

    canvas.begin_path()
    canvas.move_to(x2, y2)
    canvas.line_to(xh1, yh1)
    canvas.line_to(xh2, yh2)
    canvas.line_to(x2, y2)
    canvas.fill()

def draw_moment_symbol(cx, cy, sign=1, radius=14):
    start = 0.3 * math.pi
    end   = 1.8 * math.pi
    if sign < 0:
        start, end = end, start
    canvas.begin_path()
    canvas.arc(cx, cy, radius, start, end)
    canvas.stroke()

    ex = cx + radius * math.cos(end)
    ey = cy + radius * math.sin(end)
    tx = -math.sin(end) * sign
    ty =  math.cos(end) * sign
    hl = 8
    canvas.begin_path()
    canvas.move_to(ex, ey)
    canvas.line_to(ex - hl*(tx + 0.6*math.cos(end)), ey - hl*(ty + 0.6*math.sin(end)))
    canvas.line_to(ex - hl*(tx - 0.6*math.cos(end)), ey - hl*(ty - 0.6*math.sin(end)))
    canvas.line_to(ex, ey)
    canvas.fill()

def draw_support_symbol(sid, selected=False, hovered=False):
    si = sup_index_by_id(sid)
    if si < 0:
        return

    nid = int(supports[si, 1])
    ux = int(supports[si, 2])
    uy = int(supports[si, 3])
    rz = int(supports[si, 4])

    ni = node_index_by_id(nid)
    if ni < 0:
        return

    x0, y0 = grid_to_px(int(nodes[ni, 1]), int(nodes[ni, 2]))

    col = "#2ca02c" if (selected or hovered) else "#228822"
    canvas.stroke_style = col
    canvas.fill_style = col
    canvas.line_width = 3 if (selected or hovered) else 2

    S = SUP_SIZE_PX
    gap = SUP_GAP_PX

    def ground_below(cx, y_base, length=2.2):
        L = length * S
        y = y_base + gap
        canvas.begin_path()
        canvas.move_to(cx - 0.5 * L, y)
        canvas.line_to(cx + 0.5 * L, y)
        canvas.stroke()

    def ground_right(x_base, cy, length=2.2):
        L = length * S
        x = x_base + gap
        canvas.begin_path()
        canvas.move_to(x, cy - 0.5 * L)
        canvas.line_to(x, cy + 0.5 * L)
        canvas.stroke()

    def triangle_tip_up(cx, cy):
        W_ = 0.9 * S
        H_ = 0.7 * S
        canvas.begin_path()
        canvas.move_to(cx, cy)                 # tip at node
        canvas.line_to(cx - W_, cy + H_)
        canvas.line_to(cx + W_, cy + H_)
        canvas.close_path()
        canvas.stroke()
        return cy + H_

    def triangle_tip_left(cx, cy):
        W_ = 0.7 * S
        H_ = 0.9 * S
        canvas.begin_path()
        canvas.move_to(cx, cy)                 # tip at node
        canvas.line_to(cx + H_, cy - W_)
        canvas.line_to(cx + H_, cy + W_)
        canvas.close_path()
        canvas.stroke()
        return cx + H_

    def rect_center(cx, cy):
        W_ = 0.75 * S
        H_ = 0.75 * S
        canvas.begin_path()
        canvas.rect(cx - W_, cy - H_, 2 * W_, 2 * H_)
        canvas.stroke()
        return (cx + W_, cy + H_)

    if rz == 0:
        if ux == 1 and uy == 1:
            triangle_tip_up(x0, y0)
            return
        if uy == 1 and ux == 0:
            yb = triangle_tip_up(x0, y0)
            ground_below(x0, yb)
            return
        if ux == 1 and uy == 0:
            xb = triangle_tip_left(x0, y0)
            ground_right(xb, y0)
            return
        triangle_tip_up(x0, y0)
        return

    if ux == 1 and uy == 1 and rz == 1:
        rect_center(x0, y0)
        return

    xr, yb = rect_center(x0, y0)
    if ux == 1 and uy == 0:
        ground_right(xr, y0)
    else:
        ground_below(x0, yb)

# =============================
# Drawing
# =============================
def fmt_sci_short(x: float) -> str:
    s = f"{float(x):.1e}"
    mant, exp = s.split("e")
    return f"{mant}e{int(exp)}"

def draw_grid():
    g = int(zoom_px.value)

    base_col = "#eeeeee"
    major_col = "#d7d7d7"
    major_every = 5

    # grid shifts with pan
    sx = float(state["pan_x"] % g)
    sy = float(state["pan_y"] % g)

    # vertical
    k0 = int(math.floor((-sx) / g)) - 2
    k1 = int(math.ceil((canvas.width - sx) / g)) + 2
    for k in range(k0, k1 + 1):
        xp = sx + k * g
        is_major = (k % major_every == 0)
        canvas.stroke_style = major_col if is_major else base_col
        canvas.line_width = 1
        canvas.begin_path()
        canvas.move_to(xp, 0)
        canvas.line_to(xp, canvas.height)
        canvas.stroke()

    # horizontal
    j0 = int(math.floor((-sy) / g)) - 2
    j1 = int(math.ceil((canvas.height - sy) / g)) + 2
    for j in range(j0, j1 + 1):
        yp = sy + j * g
        is_major = (j % major_every == 0)
        canvas.stroke_style = major_col if is_major else base_col
        canvas.line_width = 1
        canvas.begin_path()
        canvas.move_to(0, yp)
        canvas.line_to(canvas.width, yp)
        canvas.stroke()

    # axes through world origin
    ox, oy = world_origin_px()
    axis_col = "#555"
    canvas.stroke_style = axis_col
    canvas.line_width = 3

    canvas.begin_path()
    canvas.move_to(0, oy)
    canvas.line_to(canvas.width, oy)
    canvas.stroke()

    canvas.begin_path()
    canvas.move_to(ox, 0)
    canvas.line_to(ox, canvas.height)
    canvas.stroke()

    arrow = 10
    canvas.fill_style = axis_col

    canvas.begin_path()
    canvas.move_to(canvas.width, oy)
    canvas.line_to(canvas.width - arrow, oy - arrow/2)
    canvas.line_to(canvas.width - arrow, oy + arrow/2)
    canvas.close_path()
    canvas.fill()

    canvas.begin_path()
    canvas.move_to(ox, 0)
    canvas.line_to(ox + arrow/2, arrow)
    canvas.line_to(ox - arrow/2, arrow)
    canvas.close_path()
    canvas.fill()

    canvas.fill_style = "#666"
    canvas.font = "12px system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
    
    # Anzeige als "World-Shift" (Grid-Einheiten): x muss negiert werden
    pan_gx = -state["pan_x"] / g
    pan_gy =  state["pan_y"] / g
    canvas.fill_text(
        f"Zoom: {g}px | Grid: {GRID_UNIT} | E: {fmt_sci_short(E_in.value)} | Pan: ({pan_gx:.2f},{pan_gy:.2f})",
        10, 18
    )

def draw_scene(preview_line=None):
    with hold_canvas(canvas):
        canvas.clear()
        draw_grid()

        # bars
        if bars.size:
            for r in bars:
                bid = int(r[0])
                n1 = int(r[1]); n2 = int(r[2])
                i1 = node_index_by_id(n1)
                i2 = node_index_by_id(n2)
                if i1 < 0 or i2 < 0:
                    continue
                x1, y1 = grid_to_px(int(nodes[i1, 1]), int(nodes[i1, 2]))
                x2, y2 = grid_to_px(int(nodes[i2, 1]), int(nodes[i2, 2]))
                is_hover = (state["hover_bar"] == bid)
                is_sel = (state["selected_bar"] == bid)
                canvas.stroke_style = "#1f77b4" if (is_hover or is_sel) else "#111"
                canvas.line_width = 3 if (is_hover or is_sel) else 2
                canvas.begin_path()
                canvas.move_to(x1, y1)
                canvas.line_to(x2, y2)
                canvas.stroke()

        # preview bar
        if preview_line is not None:
            (x1, y1), (x2, y2) = preview_line
            canvas.stroke_style = "#888"
            canvas.line_width = 2
            canvas.set_line_dash([6, 6])
            canvas.begin_path()
            canvas.move_to(x1, y1)
            canvas.line_to(x2, y2)
            canvas.stroke()
            canvas.set_line_dash([])

        # supports
        if supports.size:
            for r in supports:
                sid = int(r[0])
                draw_support_symbol(
                    sid,
                    selected=(state["selected_sup"] == sid),
                    hovered=(state["hover_sup"] == sid),
                )

        # nodes
        for r in nodes:
            nid = int(r[0]); xg = int(r[1]); yg = int(r[2])
            x, y = grid_to_px(xg, yg)
            is_hover = (state["hover_node"] == nid)
            is_sel = (state["selected_node"] == nid)
            is_pending = (state["pending_n1"] == nid)

            if is_pending:
                canvas.fill_style = "#ff7f0e"; rad = 7
            elif is_sel or is_hover:
                canvas.fill_style = "#1f77b4"; rad = 6
            else:
                canvas.fill_style = "#333"; rad = 5

            canvas.begin_path()
            canvas.arc(x, y, rad, 0, 2*math.pi)
            canvas.fill()

            canvas.fill_style = "#555"
            canvas.font = "12px system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
            canvas.fill_text(str(nid), x + 8, y - 8)

        # loads (pixel-constant size)
        if loads.size:
            head_len = LOAD_HEAD_PX
            L = LOAD_LEN_PX
            for r in loads:
                lid = int(r[0]); nid = int(r[1])
                Fx, Fy, M = float(r[2]), float(r[3]), float(r[4])
                ni = node_index_by_id(nid)
                if ni < 0:
                    continue
                ax, ay = grid_to_px(int(nodes[ni, 1]), int(nodes[ni, 2]))

                is_hover = (state["hover_load"] == lid)
                is_sel = (state["selected_load"] == lid)
                canvas.stroke_style = "#d62728" if (is_hover or is_sel) else "#aa0000"
                canvas.fill_style = canvas.stroke_style
                canvas.line_width = 3 if (is_hover or is_sel) else 2

                if abs(Fx) > 1e-12:
                    s = 1 if Fx > 0 else -1
                    draw_arrow(ax, ay, ax + s*L, ay, head_len=head_len)
                if abs(Fy) > 1e-12:
                    s = 1 if Fy > 0 else -1
                    draw_arrow(ax, ay, ax, ay - s*L, head_len=head_len)
                if abs(M) > 1e-12:
                    s = 1 if M > 0 else -1
                    draw_moment_symbol(ax, ay, sign=s, radius=MOM_RADIUS_PX)

                canvas.fill_style = "#aa0000"
                canvas.font = "11px system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif"
                canvas.fill_text(f"L{lid}", ax + 8, ay - 8)

# =============================
# Status + panel sync
# =============================
def update_status():
    if tool_value == "node":
        status.value = "Tool: <b>Knoten</b>. Klick setzt Knoten."
    elif tool_value == "bar":
        status.value = "Tool: <b>Stab</b>. Klick A dann B."
    elif tool_value == "load":
        status.value = "Tool: <b>Einzellast</b>. Klick auf Knoten setzt Last. Klick nahe Knoten selektiert Last."
    elif tool_value == "sup":
        status.value = "Tool: <b>Auflager</b>. Klick auf Knoten setzt Auflager. Klick nahe Knoten selektiert Auflager."
    else:
        status.value = "Tool: <b>Pan</b>. Maus gedrückt halten und ziehen, um die Zeichenfläche zu verschieben."

def sync_bar_panel():
    bid = state["selected_bar"]
    has = (bid != -1 and bar_index_by_id(bid) != -1)
    edit_bar_btn.disabled = not has
    if not has:
        bar_id_lbl.value = "<b>Bar:</b> -"
        A_in.disabled = True; I_in.disabled = True; phi_in.disabled = True
        apply_bar_btn.disabled = True
    else:
        bar_id_lbl.value = f"<b>Bar:</b> {bid} (selektiert)"

def sync_load_panel():
    lid = state["selected_load"]
    has = (lid != -1 and load_index_by_id(lid) != -1)
    edit_load_btn.disabled = not has
    if not has:
        load_id_lbl.value = "<b>Load:</b> -"
        Fx_in.disabled = True; Fy_in.disabled = True; M_in.disabled = True
        apply_load_btn.disabled = True
    else:
        load_id_lbl.value = f"<b>Load:</b> {lid} (selektiert)"

def sync_sup_panel():
    sid = state["selected_sup"]
    has = (sid != -1 and sup_index_by_id(sid) != -1)
    edit_sup_btn.disabled = not has
    if not has:
        sup_id_lbl.value = "<b>Support:</b> -"
        ux_chk.disabled = True; uy_chk.disabled = True; rz_chk.disabled = True
        apply_sup_btn.disabled = True
    else:
        sup_id_lbl.value = f"<b>Support:</b> {sid} (selektiert)"

# =============================
# Tool switching (buttons)
# =============================
def _set_tool(v: str):
    global tool_value
    tool_value = v

    mapping = {
        "node": btn_node,
        "bar":  btn_bar,
        "load": btn_load,
        "sup":  btn_sup,
        "pan":  btn_pan,
    }
    for key, b in mapping.items():
        b.button_style = "primary" if key == v else ""

    state["pending_n1"] = -1
    state["panning"] = False
    update_status()
    draw_scene()

btn_node.on_click(lambda _: _set_tool("node"))
btn_bar.on_click(lambda _: _set_tool("bar"))
btn_load.on_click(lambda _: _set_tool("load"))
btn_sup.on_click(lambda _: _set_tool("sup"))
btn_pan.on_click(lambda _: _set_tool("pan"))

# =============================
# Canvas events
# =============================
def on_mouse_move(xp, yp):
    if tool_value == "pan" and state["panning"]:
        lx, ly = state["pan_last"]
        state["pan_x"] += (xp - lx)
        state["pan_y"] += (yp - ly)
        state["pan_last"] = (xp, yp)
        draw_scene()
        return

    state["hover_node"] = pick_node_px(xp, yp)
    state["hover_sup"]  = pick_support_px(xp, yp)
    state["hover_load"] = pick_load_px(xp, yp)
    state["hover_bar"]  = pick_bar_px(xp, yp)

    preview = None
    if tool_value == "bar" and state["pending_n1"] != -1:
        i1 = node_index_by_id(state["pending_n1"])
        if i1 >= 0:
            x1, y1 = grid_to_px(int(nodes[i1, 1]), int(nodes[i1, 2]))
            if state["hover_node"] != -1:
                i2 = node_index_by_id(state["hover_node"])
                x2, y2 = grid_to_px(int(nodes[i2, 1]), int(nodes[i2, 2]))
            else:
                xg, yg = px_to_grid(xp, yp)
                xg, yg = clamp_grid(xg, yg)
                x2, y2 = grid_to_px(xg, yg)
            preview = ((x1, y1), (x2, y2))

    draw_scene(preview_line=preview)

def on_mouse_down(xp, yp):
    if tool_value == "pan":
        state["panning"] = True
        state["pan_last"] = (xp, yp)
        return

    state["selected_node"] = -1
    state["selected_sup"]  = -1
    state["selected_load"] = -1
    state["selected_bar"]  = -1

    nid = pick_node_px(xp, yp)
    if nid != -1:
        state["selected_node"] = nid

    sid = pick_support_px(xp, yp)
    if sid != -1 and nid == -1:
        state["selected_sup"] = sid

    lid = pick_load_px(xp, yp)
    if lid != -1 and nid == -1 and sid == -1:
        state["selected_load"] = lid

    bid = pick_bar_px(xp, yp)
    if bid != -1 and nid == -1 and sid == -1 and lid == -1:
        state["selected_bar"] = bid

    sync_bar_panel()
    sync_load_panel()
    sync_sup_panel()

    if tool_value == "node":
        xg, yg = px_to_grid(xp, yp)
        xg, yg = clamp_grid(xg, yg)
        nid_new, _ = add_node_grid(xg, yg)
        state["selected_node"] = nid_new
        state["pending_n1"] = -1
        update_status()
        draw_scene()
        return

    if tool_value == "bar":
        if nid == -1:
            draw_scene()
            return
        if state["pending_n1"] == -1:
            state["pending_n1"] = nid
            draw_scene()
            return
        add_bar(state["pending_n1"], nid)
        state["pending_n1"] = -1
        draw_scene()
        return

    if tool_value == "load":
        if nid == -1:
            draw_scene()
            return
        lid_new, _ = add_load_at_node(nid)
        state["selected_load"] = lid_new
        sync_load_panel()
        draw_scene()
        return

    if tool_value == "sup":
        if nid == -1:
            draw_scene()
            return
        sid_new, _ = add_support_at_node(nid)
        state["selected_sup"] = sid_new
        sync_sup_panel()
        draw_scene()
        return

def on_mouse_up(xp, yp):
    state["panning"] = False

canvas.on_mouse_move(on_mouse_move)
canvas.on_mouse_down(on_mouse_down)
try:
    canvas.on_mouse_up(on_mouse_up)
except Exception:
    pass

# =============================
# UI events
# =============================
def on_zoom_change(change):
    draw_scene()

zoom_px.observe(on_zoom_change, "value")

def _fix_canvas_after_layout_change(_=None):
    canvas.width = WID
    canvas.height = HEI
    canvas.layout.width = f"{WID}px"
    canvas.layout.height = f"{HEI}px"
    draw_scene()

props_accordion.observe(lambda c: _fix_canvas_after_layout_change(), "selected_index")

# =============================
# Undo/Clear/Export + Editing
# =============================
def on_undo(_):
    if not history:
        return
    kind, oid = history.pop()

    if kind == "add_bar":
        remove_bar_by_id(oid)
        if state["selected_bar"] == oid:
            state["selected_bar"] = -1

    elif kind == "add_load":
        remove_load_by_id(oid)
        if state["selected_load"] == oid:
            state["selected_load"] = -1

    elif kind == "add_sup":
        remove_support_by_id(oid)
        if state["selected_sup"] == oid:
            state["selected_sup"] = -1

    elif kind == "add_node":
        remove_node_and_attached_objects(oid)
        if state["selected_node"] == oid:
            state["selected_node"] = -1
        if state["pending_n1"] == oid:
            state["pending_n1"] = -1

    sync_bar_panel()
    sync_load_panel()
    sync_sup_panel()
    draw_scene()

def on_clear(_):
    global nodes, bars, loads, supports
    global next_node_id, next_bar_id, next_load_id, next_sup_id

    nodes = np.zeros((0, 3), dtype=int)
    bars  = np.zeros((0, 6), dtype=float)
    loads = np.zeros((0, 5), dtype=float)
    supports = np.zeros((0, 5), dtype=int)

    next_node_id = 1
    next_bar_id = 1
    next_load_id = 1
    next_sup_id = 1
    history.clear()

    # reset state
    state["hover_node"] = -1
    state["selected_node"] = -1
    state["pending_n1"] = -1
    state["hover_bar"] = -1
    state["selected_bar"] = -1
    state["hover_load"] = -1
    state["selected_load"] = -1
    state["hover_sup"] = -1
    state["selected_sup"] = -1
    state["pan_x"] = 0.0
    state["pan_y"] = 0.0
    state["panning"] = False
    state["pan_last"] = (0.0, 0.0)

    sync_bar_panel()
    sync_load_panel()
    sync_sup_panel()
    draw_scene()

def on_edit_bar(_):
    bid = state["selected_bar"]
    idx = bar_index_by_id(bid)
    if idx < 0:
        return
    props_accordion.selected_index = 0
    A_in.disabled = False; I_in.disabled = False; phi_in.disabled = False
    apply_bar_btn.disabled = False
    A_in.value = float(bars[idx, 3])
    I_in.value = float(bars[idx, 4])
    phi_in.value = float(bars[idx, 5])

def on_apply_bar(_):
    bid = state["selected_bar"]
    idx = bar_index_by_id(bid)
    if idx < 0:
        return
    bars[idx, 3] = float(A_in.value)
    bars[idx, 4] = float(I_in.value)
    bars[idx, 5] = float(phi_in.value)
    A_in.disabled = True; I_in.disabled = True; phi_in.disabled = True
    apply_bar_btn.disabled = True
    draw_scene()

def on_edit_load(_):
    lid = state["selected_load"]
    idx = load_index_by_id(lid)
    if idx < 0:
        return
    props_accordion.selected_index = 1
    Fx_in.disabled = False; Fy_in.disabled = False; M_in.disabled = False
    apply_load_btn.disabled = False
    Fx_in.value = float(loads[idx, 2])
    Fy_in.value = float(loads[idx, 3])
    M_in.value  = float(loads[idx, 4])

def on_apply_load(_):
    lid = state["selected_load"]
    idx = load_index_by_id(lid)
    if idx < 0:
        return
    loads[idx, 2] = float(Fx_in.value)
    loads[idx, 3] = float(Fy_in.value)
    loads[idx, 4] = float(M_in.value)
    Fx_in.disabled = True; Fy_in.disabled = True; M_in.disabled = True
    apply_load_btn.disabled = True
    draw_scene()

def on_edit_sup(_):
    sid = state["selected_sup"]
    si = sup_index_by_id(sid)
    if si < 0:
        return
    props_accordion.selected_index = 2
    ux_chk.disabled = False; uy_chk.disabled = False; rz_chk.disabled = False
    apply_sup_btn.disabled = False
    ux_chk.value = bool(supports[si, 2])
    uy_chk.value = bool(supports[si, 3])
    rz_chk.value = bool(supports[si, 4])

def on_apply_sup(_):
    sid = state["selected_sup"]
    si = sup_index_by_id(sid)
    if si < 0:
        return
    supports[si, 2] = 1 if ux_chk.value else 0
    supports[si, 3] = 1 if uy_chk.value else 0
    supports[si, 4] = 1 if rz_chk.value else 0

    ux_chk.disabled = True; uy_chk.disabled = True; rz_chk.disabled = True
    apply_sup_btn.disabled = True
    draw_scene()

def on_export(_):
    print("=== NODES (id, xg, yg) ===")
    print(nodes)

    print("\n=== BARS (id, n1, n2, A, I, phi_deg) ===")
    print(bars)

    print("\n=== LOADS (id, nid, Fx, Fy, M) ===")
    print(loads)

    print("\n=== SUPPORTS (id, nid, ux_fix, uy_fix, rz_fix) ===")
    print(supports)

    if not save_chk.value:
        return

    n_nodes = int(nodes.shape[0])
    n_bars  = int(bars.shape[0])
    n_sups  = int(supports.shape[0])

    nodes_sorted = nodes[np.argsort(nodes[:, 0])] if n_nodes else nodes
    bars_sorted  = bars[np.argsort(bars[:, 0])]   if n_bars  else bars
    sups_sorted  = supports[np.argsort(supports[:, 1])] if n_sups else supports

    lines = []
    lines.append(f"{n_nodes:d}   {n_bars:d}")
    lines.append(f"{n_sups:d}")
    lines.append(f"{float(E_in.value):.6E}")

    for r in nodes_sorted:
        xg = int(r[1]); yg = int(r[2])
        lines.append(f"{xg:d}   {yg:d}")

    for r in bars_sorted:
        bid = int(r[0])
        n1  = int(r[1]); n2 = int(r[2])
        A   = float(r[3]); I = float(r[4])
        phi_deg = float(r[5])
        phi_rad = phi_deg * math.pi / 180.0
        lines.append(f"{bid:d}    {n1:d}     {n2:d}     {A:.6E}   {I:.6E}     {phi_rad:.6g}")

    for r in loads:
        nid = int(r[1])
        Fx  = float(r[2]); Fy = float(r[3]); M = float(r[4])
        lines.append(f"{nid:d}    0    {Fx:.6g}    {Fy:.6g}     {M:.6g}")

    for r in sups_sorted:
        nid = int(r[1])
        uxfix = int(r[2]); uyfix = int(r[3]); rzfix = int(r[4])
        lines.append(f"{nid:d}    {uxfix:d}    {uyfix:d}    {rzfix:d}")

    fname = "System.txt"
    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nSaved: {fname}  (CWD: {os.getcwd()})")

undo_btn.on_click(on_undo)
clear_btn.on_click(on_clear)
export_btn.on_click(on_export)

edit_bar_btn.on_click(on_edit_bar)
apply_bar_btn.on_click(on_apply_bar)

edit_load_btn.on_click(on_edit_load)
apply_load_btn.on_click(on_apply_load)

edit_sup_btn.on_click(on_edit_sup)
apply_sup_btn.on_click(on_apply_sup)

# =============================
# Init
# =============================
_set_tool("node")
sync_bar_panel()
sync_load_panel()
sync_sup_panel()
draw_scene()# =========================================================
# Session State init
# =========================================================
def _init():
    if "nodes" not in st.session_state:
        st.session_state.nodes = np.zeros((0, 3), dtype=int)      # [id, xg, yg]
        st.session_state.next_node_id = 1

    if "bars" not in st.session_state:
        st.session_state.bars = np.zeros((0, 6), dtype=float)     # [id, n1, n2, A, I, phi_deg]
        st.session_state.next_bar_id = 1

    if "loads" not in st.session_state:
        st.session_state.loads = np.zeros((0, 5), dtype=float)    # [id, nid, Fx, Fy, M]
        st.session_state.next_load_id = 1

    if "supports" not in st.session_state:
        st.session_state.supports = np.zeros((0, 5), dtype=int)   # [id, nid, ux_fix, uy_fix, rz_fix]
        st.session_state.next_sup_id = 1

    if "history" not in st.session_state:
        st.session_state.history = []  # ("add_node", nid) etc.

    if "tool" not in st.session_state:
        st.session_state.tool = "node"

    if "pending_n1" not in st.session_state:
        st.session_state.pending_n1 = -1

    if "selected_node" not in st.session_state:
        st.session_state.selected_node = -1
    if "selected_bar" not in st.session_state:
        st.session_state.selected_bar = -1
    if "selected_load" not in st.session_state:
        st.session_state.selected_load = -1
    if "selected_sup" not in st.session_state:
        st.session_state.selected_sup = -1

    if "zoom_px" not in st.session_state:
        st.session_state.zoom_px = 25
    if "E_val" not in st.session_state:
        st.session_state.E_val = 2.0e8

    # edit-mode flags (like your enable/disable)
    if "edit_bar_mode" not in st.session_state:
        st.session_state.edit_bar_mode = False
    if "edit_load_mode" not in st.session_state:
        st.session_state.edit_load_mode = False
    if "edit_sup_mode" not in st.session_state:
        st.session_state.edit_sup_mode = False

_init()

# Short handles
nodes = st.session_state.nodes
bars = st.session_state.bars
loads = st.session_state.loads
supports = st.session_state.supports
history = st.session_state.history


# =========================================================
# Helpers (IDs / indexing)
# =========================================================
def node_index_by_id(nid: int) -> int:
    n = st.session_state.nodes
    if n.size == 0:
        return -1
    idx = np.where(n[:, 0] == int(nid))[0]
    return int(idx[0]) if idx.size else -1

def bar_index_by_id(bid: int) -> int:
    b = st.session_state.bars
    if b.size == 0:
        return -1
    idx = np.where(b[:, 0].astype(int) == int(bid))[0]
    return int(idx[0]) if idx.size else -1

def load_index_by_id(lid: int) -> int:
    l = st.session_state.loads
    if l.size == 0:
        return -1
    idx = np.where(l[:, 0].astype(int) == int(lid))[0]
    return int(idx[0]) if idx.size else -1

def sup_index_by_id(sid: int) -> int:
    s = st.session_state.supports
    if s.size == 0:
        return -1
    idx = np.where(s[:, 0].astype(int) == int(sid))[0]
    return int(idx[0]) if idx.size else -1

def find_node_at_grid(xg: int, yg: int) -> int:
    n = st.session_state.nodes
    if n.size == 0:
        return -1
    mask = (n[:, 1] == int(xg)) & (n[:, 2] == int(yg))
    idx = np.where(mask)[0]
    return int(n[idx[0], 0]) if idx.size else -1


# =========================================================
# Pick functions (in grid-units)
# =========================================================
def pick_node_xy(x: float, y: float) -> int:
    n = st.session_state.nodes
    if n.size == 0:
        return -1
    xs = n[:, 1].astype(float)
    ys = n[:, 2].astype(float)
    d = np.sqrt((xs - x)**2 + (ys - y)**2)
    j = int(np.argmin(d))
    return int(n[j, 0]) if float(d[j]) <= PICK_R_G_MIN else -1

def _point_segment_distance(px, py, x1, y1, x2, y2) -> float:
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    vv = vx*vx + vy*vy
    if vv == 0:
        return math.hypot(px - x1, py - y1)
    t = (wx*vx + wy*vy) / vv
    t = max(0.0, min(1.0, t))
    projx = x1 + t * vx
    projy = y1 + t * vy
    return math.hypot(px - projx, py - projy)

def pick_bar_xy(x: float, y: float) -> int:
    b = st.session_state.bars
    if b.size == 0:
        return -1
    n = st.session_state.nodes
    best_bid, best_d = -1, 1e9
    tol = 0.6
    for r in b:
        bid = int(r[0])
        n1, n2 = int(r[1]), int(r[2])
        i1, i2 = node_index_by_id(n1), node_index_by_id(n2)
        if i1 < 0 or i2 < 0:
            continue
        x1, y1 = float(n[i1, 1]), float(n[i1, 2])
        x2, y2 = float(n[i2, 1]), float(n[i2, 2])
        d = _point_segment_distance(x, y, x1, y1, x2, y2)
        if d < best_d:
            best_d, best_bid = d, bid
    return best_bid if best_d <= tol else -1

def pick_load_xy(x: float, y: float) -> int:
    l = st.session_state.loads
    if l.size == 0:
        return -1
    n = st.session_state.nodes
    best_lid, best_d = -1, 1e9
    tol = 0.8
    for r in l:
        lid = int(r[0]); nid = int(r[1])
        i = node_index_by_id(nid)
        if i < 0:
            continue
        ax, ay = float(n[i, 1]), float(n[i, 2])
        d = math.hypot(x - ax, y - ay)
        if d < best_d:
            best_d, best_lid = d, lid
    return best_lid if best_d <= tol else -1

def pick_support_xy(x: float, y: float) -> int:
    s = st.session_state.supports
    if s.size == 0:
        return -1
    n = st.session_state.nodes
    best_sid, best_d = -1, 1e9
    tol = 0.9
    for r in s:
        sid = int(r[0]); nid = int(r[1])
        i = node_index_by_id(nid)
        if i < 0:
            continue
        ax, ay = float(n[i, 1]), float(n[i, 2])
        d = math.hypot(x - ax, y - ay)
        if d < best_d:
            best_d, best_sid = d, sid
    return best_sid if best_d <= tol else -1


# =========================================================
# Model actions (ported + adapted)
# =========================================================
def add_node_grid(xg: int, yg: int):
    existing = find_node_at_grid(xg, yg)
    if existing != -1:
        return existing, False
    nid = st.session_state.next_node_id
    row = np.array([[nid, xg, yg]], dtype=int)
    n = st.session_state.nodes
    st.session_state.nodes = row if n.size == 0 else np.vstack([n, row])
    st.session_state.next_node_id += 1
    st.session_state.history.append(("add_node", nid))
    return nid, True

def bar_exists(n1: int, n2: int) -> bool:
    b = st.session_state.bars
    if b.size == 0:
        return False
    a = b[:, 1].astype(int)
    c = b[:, 2].astype(int)
    return bool(np.any(((a == n1) & (c == n2)) | ((a == n2) & (c == n1))))

def compute_phi_deg(n1: int, n2: int) -> float:
    n = st.session_state.nodes
    i1 = node_index_by_id(n1)
    i2 = node_index_by_id(n2)
    if i1 < 0 or i2 < 0:
        return 0.0
    x1 = float(n[i1, 1] * GRID_UNIT)
    y1 = float(n[i1, 2] * GRID_UNIT)
    x2 = float(n[i2, 1] * GRID_UNIT)
    y2 = float(n[i2, 2] * GRID_UNIT)
    return math.degrees(math.atan2(y2 - y1, x2 - x1))

def add_bar(n1: int, n2: int):
    if n1 == -1 or n2 == -1 or n1 == n2:
        return -1, False
    if bar_exists(n1, n2):
        return -1, False
    bid = st.session_state.next_bar_id
    phi = compute_phi_deg(n1, n2)
    row = np.array([[bid, n1, n2, A_DEFAULT, I_DEFAULT, phi]], dtype=float)
    b = st.session_state.bars
    st.session_state.bars = row if b.size == 0 else np.vstack([b, row])
    st.session_state.next_bar_id += 1
    st.session_state.history.append(("add_bar", bid))
    return bid, True

def add_load_at_node(nid: int):
    if nid == -1 or node_index_by_id(nid) < 0:
        return -1, False
    lid = st.session_state.next_load_id
    row = np.array([[lid, nid, FX_DEFAULT, FY_DEFAULT, M_DEFAULT]], dtype=float)
    l = st.session_state.loads
    st.session_state.loads = row if l.size == 0 else np.vstack([l, row])
    st.session_state.next_load_id += 1
    st.session_state.history.append(("add_load", lid))
    return lid, True

def sup_id_at_node(nid: int) -> int:
    s = st.session_state.supports
    if s.size == 0:
        return -1
    idx = np.where(s[:, 1] == int(nid))[0]
    return int(s[idx[0], 0]) if idx.size else -1

def add_support_at_node(nid: int):
    if nid == -1 or node_index_by_id(nid) < 0:
        return -1, False
    existing = sup_id_at_node(nid)
    if existing != -1:
        return existing, False
    sid = st.session_state.next_sup_id
    row = np.array([[sid, nid, SUP_UX_DEFAULT, SUP_UY_DEFAULT, SUP_RZ_DEFAULT]], dtype=int)
    s = st.session_state.supports
    st.session_state.supports = row if s.size == 0 else np.vstack([s, row])
    st.session_state.next_sup_id += 1
    st.session_state.history.append(("add_sup", sid))
    return sid, True

def remove_node_and_attached_objects(nid: int):
    # Remove bars, loads, supports attached to nid, then remove node
    n = st.session_state.nodes
    b = st.session_state.bars
    l = st.session_state.loads
    s = st.session_state.supports

    if b.size:
        n1 = b[:, 1].astype(int)
        n2 = b[:, 2].astype(int)
        st.session_state.bars = b[~((n1 == nid) | (n2 == nid))]

    if l.size:
        st.session_state.loads = l[~(l[:, 1].astype(int) == nid)]

    if s.size:
        st.session_state.supports = s[~(s[:, 1].astype(int) == nid)]

    idx = node_index_by_id(nid)
    if idx >= 0:
        st.session_state.nodes = np.delete(n, idx, axis=0)

def remove_bar_by_id(bid: int):
    b = st.session_state.bars
    if b.size == 0:
        return
    idx = np.where(b[:, 0].astype(int) == bid)[0]
    if idx.size:
        st.session_state.bars = np.delete(b, int(idx[0]), axis=0)

def remove_load_by_id(lid: int):
    l = st.session_state.loads
    if l.size == 0:
        return
    idx = np.where(l[:, 0].astype(int) == lid)[0]
    if idx.size:
        st.session_state.loads = np.delete(l, int(idx[0]), axis=0)

def remove_support_by_id(sid: int):
    s = st.session_state.supports
    if s.size == 0:
        return
    idx = np.where(s[:, 0].astype(int) == sid)[0]
    if idx.size:
        st.session_state.supports = np.delete(s, int(idx[0]), axis=0)

def do_undo():
    if not st.session_state.history:
        return
    kind, oid = st.session_state.history.pop()

    if kind == "add_bar":
        remove_bar_by_id(int(oid))
        if st.session_state.selected_bar == int(oid):
            st.session_state.selected_bar = -1

    elif kind == "add_load":
        remove_load_by_id(int(oid))
        if st.session_state.selected_load == int(oid):
            st.session_state.selected_load = -1

    elif kind == "add_sup":
        remove_support_by_id(int(oid))
        if st.session_state.selected_sup == int(oid):
            st.session_state.selected_sup = -1

    elif kind == "add_node":
        remove_node_and_attached_objects(int(oid))
        if st.session_state.selected_node == int(oid):
            st.session_state.selected_node = -1
        if st.session_state.pending_n1 == int(oid):
            st.session_state.pending_n1 = -1

def do_clear():
    for k in [
        "nodes","next_node_id","bars","next_bar_id","loads","next_load_id",
        "supports","next_sup_id","history",
        "pending_n1","selected_node","selected_bar","selected_load","selected_sup",
        "edit_bar_mode","edit_load_mode","edit_sup_mode",
    ]:
        st.session_state.pop(k, None)
    _init()

def fmt_sci_short(x: float) -> str:
    s = f"{float(x):.1e}"
    mant, exp = s.split("e")
    return f"{mant}e{int(exp)}"

def export_system_txt(E_value: float) -> str:
    n = st.session_state.nodes
    b = st.session_state.bars
    l = st.session_state.loads
    s = st.session_state.supports

    n_nodes = int(n.shape[0])
    n_bars  = int(b.shape[0])
    n_sups  = int(s.shape[0])

    nodes_sorted = n[np.argsort(n[:, 0])] if n_nodes else n
    bars_sorted  = b[np.argsort(b[:, 0])] if n_bars else b
    sups_sorted  = s[np.argsort(s[:, 1])] if n_sups else s

    lines = []
    lines.append(f"{n_nodes:d}   {n_bars:d}")
    lines.append(f"{n_sups:d}")
    lines.append(f"{float(E_value):.6E}")

    for r in nodes_sorted:
        xg = int(r[1]); yg = int(r[2])
        lines.append(f"{xg:d}   {yg:d}")

    for r in bars_sorted:
        bid = int(r[0])
        n1  = int(r[1]); n2 = int(r[2])
        A   = float(r[3]); I = float(r[4])
        phi_deg = float(r[5])
        phi_rad = phi_deg * math.pi / 180.0
        lines.append(f"{bid:d}    {n1:d}     {n2:d}     {A:.6E}   {I:.6E}     {phi_rad:.6g}")

    for r in l:
        nid = int(r[1])
        Fx  = float(r[2]); Fy = float(r[3]); M = float(r[4])
        lines.append(f"{nid:d}    0    {Fx:.6g}    {Fy:.6g}     {M:.6g}")

    for r in sups_sorted:
        nid = int(r[1])
        uxfix = int(r[2]); uyfix = int(r[3]); rzfix = int(r[4])
        lines.append(f"{nid:d}    {uxfix:d}    {uyfix:d}    {rzfix:d}")

    return "\n".join(lines) + "\n"


# =========================================================
# UI layout
# =========================================================
col_canvas, col_right = st.columns([2.25, 1.0], gap="large")

# ---------------- Right panel (tools + panels) ----------------
with col_right:
    st.markdown("**Tool**")

    tool_labels = {
        "node": "Node",
        "bar": "Bar",
        "load": "Load",
        "sup": "Support",
        "pan": "Ansicht",
    }

    # Buttons row like your grid (2 columns)
    c1, c2 = st.columns(2, gap="small")
    if c1.button(tool_labels["node"], use_container_width=True,
                 type="primary" if st.session_state.tool=="node" else "secondary"):
        st.session_state.tool="node"; st.session_state.pending_n1=-1
    if c2.button(tool_labels["bar"], use_container_width=True,
                 type="primary" if st.session_state.tool=="bar" else "secondary"):
        st.session_state.tool="bar"; st.session_state.pending_n1=-1
    c3, c4 = st.columns(2, gap="small")
    if c3.button(tool_labels["load"], use_container_width=True,
                 type="primary" if st.session_state.tool=="load" else "secondary"):
        st.session_state.tool="load"; st.session_state.pending_n1=-1
    if c4.button(tool_labels["sup"], use_container_width=True,
                 type="primary" if st.session_state.tool=="sup" else "secondary"):
        st.session_state.tool="sup"; st.session_state.pending_n1=-1
    c5, _ = st.columns([1,1], gap="small")
    if c5.button(tool_labels["pan"], use_container_width=True,
                 type="primary" if st.session_state.tool=="pan" else "secondary"):
        st.session_state.tool="pan"; st.session_state.pending_n1=-1

    st.divider()

    st.session_state.zoom_px = st.slider("Zoom", 10, 140, int(st.session_state.zoom_px), 5)
    st.session_state.E_val = st.number_input("E-Modul", value=float(st.session_state.E_val),
                                             step=1.0e6, format="%.6e")

    st.divider()

    # Action row
    a1, a2, a3 = st.columns([1,1,1], gap="small")
    if a1.button("Undo", use_container_width=True, type="primary"):
        do_undo()
    if a2.button("Clear", use_container_width=True, type="secondary"):
        do_clear()
    # Export is download in streamlit
    txt_out = export_system_txt(st.session_state.E_val)
    a3.download_button("Export", data=txt_out, file_name="System.txt",
                       mime="text/plain", use_container_width=True)

    st.divider()

    # ---------------- Properties (Accordion-like) ----------------
    with st.expander("Bar Properties", expanded=False):
        bid = st.session_state.selected_bar
        idx = bar_index_by_id(bid) if bid != -1 else -1

        st.markdown(f"**Bar:** {bid if idx!=-1 else '-'}")

        can_edit = (idx != -1)
        edit_clicked = st.button("Edit Bar", disabled=not can_edit,
                                 type="primary", use_container_width=True)
        if edit_clicked:
            st.session_state.edit_bar_mode = True
            st.session_state.edit_load_mode = False
            st.session_state.edit_sup_mode = False

        A_val = float(st.session_state.bars[idx, 3]) if idx!=-1 else A_DEFAULT
        I_val = float(st.session_state.bars[idx, 4]) if idx!=-1 else I_DEFAULT
        phi_val = float(st.session_state.bars[idx, 5]) if idx!=-1 else PHI_DEFAULT

        A_in = st.number_input("A", value=A_val, disabled=not (can_edit and st.session_state.edit_bar_mode))
        I_in = st.number_input("I", value=I_val, disabled=not (can_edit and st.session_state.edit_bar_mode))
        phi_in = st.number_input("φ [deg]", value=phi_val, disabled=not (can_edit and st.session_state.edit_bar_mode))

        apply = st.button("Apply", disabled=not (can_edit and st.session_state.edit_bar_mode),
                          type="primary", use_container_width=True)
        if apply and idx!=-1:
            st.session_state.bars[idx, 3] = float(A_in)
            st.session_state.bars[idx, 4] = float(I_in)
            st.session_state.bars[idx, 5] = float(phi_in)
            st.session_state.edit_bar_mode = False

    with st.expander("Load Properties", expanded=False):
        lid = st.session_state.selected_load
        idx = load_index_by_id(lid) if lid != -1 else -1

        st.markdown(f"**Load:** {lid if idx!=-1 else '-'}")

        can_edit = (idx != -1)
        edit_clicked = st.button("Edit Load", disabled=not can_edit,
                                 type="primary", use_container_width=True)
        if edit_clicked:
            st.session_state.edit_load_mode = True
            st.session_state.edit_bar_mode = False
            st.session_state.edit_sup_mode = False

        Fx_val = float(st.session_state.loads[idx, 2]) if idx!=-1 else FX_DEFAULT
        Fy_val = float(st.session_state.loads[idx, 3]) if idx!=-1 else FY_DEFAULT
        M_val  = float(st.session_state.loads[idx, 4]) if idx!=-1 else M_DEFAULT

        Fx_in = st.number_input("x_Force", value=Fx_val, disabled=not (can_edit and st.session_state.edit_load_mode))
        Fy_in = st.number_input("y_Force", value=Fy_val, disabled=not (can_edit and st.session_state.edit_load_mode))
        M_in  = st.number_input("Moment",  value=M_val,  disabled=not (can_edit and st.session_state.edit_load_mode))

        apply = st.button("Apply ", disabled=not (can_edit and st.session_state.edit_load_mode),
                          type="primary", use_container_width=True)
        if apply and idx!=-1:
            st.session_state.loads[idx, 2] = float(Fx_in)
            st.session_state.loads[idx, 3] = float(Fy_in)
            st.session_state.loads[idx, 4] = float(M_in)
            st.session_state.edit_load_mode = False

    with st.expander("Support Properties", expanded=False):
        sid = st.session_state.selected_sup
        idx = sup_index_by_id(sid) if sid != -1 else -1

        st.markdown(f"**Support:** {sid if idx!=-1 else '-'}")

        can_edit = (idx != -1)
        edit_clicked = st.button("Edit Support", disabled=not can_edit,
                                 type="primary", use_container_width=True)
        if edit_clicked:
            st.session_state.edit_sup_mode = True
            st.session_state.edit_bar_mode = False
            st.session_state.edit_load_mode = False

        ux_val = bool(st.session_state.supports[idx, 2]) if idx!=-1 else True
        uy_val = bool(st.session_state.supports[idx, 3]) if idx!=-1 else True
        rz_val = bool(st.session_state.supports[idx, 4]) if idx!=-1 else False

        ux_chk = st.checkbox("Horizontal Displacement", value=ux_val,
                             disabled=not (can_edit and st.session_state.edit_sup_mode))
        uy_chk = st.checkbox("Vertical Displacement", value=uy_val,
                             disabled=not (can_edit and st.session_state.edit_sup_mode))
        rz_chk = st.checkbox("Rotation", value=rz_val,
                             disabled=not (can_edit and st.session_state.edit_sup_mode))

        apply = st.button("Apply  ", disabled=not (can_edit and st.session_state.edit_sup_mode),
                          type="primary", use_container_width=True)
        if apply and idx!=-1:
            st.session_state.supports[idx, 2] = 1 if ux_chk else 0
            st.session_state.supports[idx, 3] = 1 if uy_chk else 0
            st.session_state.supports[idx, 4] = 1 if rz_chk else 0
            st.session_state.edit_sup_mode = False

    st.divider()

    # Status like your "status" HTML
    tool = st.session_state.tool
    if tool == "node":
        st.info("Tool: Knoten. Klick setzt Knoten.")
    elif tool == "bar":
        pending = st.session_state.pending_n1
        if pending == -1:
            st.info("Tool: Stab. Klick A dann B.")
        else:
            st.info(f"Tool: Stab. A = Node {pending}. Jetzt B klicken.")
    elif tool == "load":
        st.info("Tool: Einzellast. Klick auf Knoten setzt Last. Klick nahe Knoten selektiert Last.")
    elif tool == "sup":
        st.info("Tool: Auflager. Klick auf Knoten setzt Auflager. Klick nahe Knoten selektiert Auflager.")
    else:
        st.info("Tool: Ansicht. Nutze Plotly-Pan (Drag) / Zoom (Mausrad).")


# ---------------- Canvas (Plotly) ----------------
with col_canvas:
    # Determine view range from zoom_px (bigger zoom_px => closer view)
    # We map zoom_px to a span in grid-units.
    z = float(st.session_state.zoom_px)
    # heuristic mapping
    span = max(8.0, 60.0 * (25.0 / z))  # zoom 25 -> span ~60
    cx, cy = 0.0, 0.0

    # optionally center on existing nodes
    if st.session_state.nodes.size:
        cx = float(np.mean(st.session_state.nodes[:, 1]))
        cy = float(np.mean(st.session_state.nodes[:, 2]))

    xmin, xmax = cx - span/2, cx + span/2
    ymin, ymax = cy - span/2, cy + span/2

    fig = go.Figure()

    # ---- bars
    if st.session_state.bars.size:
        for r in st.session_state.bars:
            bid = int(r[0])
            n1, n2 = int(r[1]), int(r[2])
            i1, i2 = node_index_by_id(n1), node_index_by_id(n2)
            if i1 < 0 or i2 < 0:
                continue
            x1, y1 = float(st.session_state.nodes[i1, 1]), float(st.session_state.nodes[i1, 2])
            x2, y2 = float(st.session_state.nodes[i2, 1]), float(st.session_state.nodes[i2, 2])

            is_sel = (st.session_state.selected_bar == bid)
            lw = 4 if is_sel else 3
            col = "#1f77b4" if is_sel else "#111"

            fig.add_trace(go.Scatter(
                x=[x1, x2], y=[y1, y2],
                mode="lines",
                line=dict(width=lw, color=col),
                hoverinfo="skip",
                showlegend=False,
                customdata=[f"bar:{bid}", f"bar:{bid}"],
                name=f"bar:{bid}",
            ))

    # ---- supports (marker)
    if st.session_state.supports.size:
        xs, ys, txts, cds = [], [], [], []
        for r in st.session_state.supports:
            sid = int(r[0]); nid = int(r[1])
            i = node_index_by_id(nid)
            if i < 0:
                continue
            x0, y0 = float(st.session_state.nodes[i, 1]), float(st.session_state.nodes[i, 2])
            xs.append(x0); ys.append(y0)
            txts.append(f"S{sid}")
            cds.append(f"sup:{sid}")

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            text=txts,
            textposition="bottom right",
            marker=dict(size=14, symbol="triangle-up", color="#228822"),
            hoverinfo="skip",
            showlegend=False,
            customdata=cds,
            name="supports",
        ))

    # ---- nodes
    if st.session_state.nodes.size:
        xs = st.session_state.nodes[:, 1].astype(float)
        ys = st.session_state.nodes[:, 2].astype(float)
        ids = st.session_state.nodes[:, 0].astype(int)

        # highlight selected node
        colors = ["#333"] * len(ids)
        sizes = [10] * len(ids)
        for i, nid in enumerate(ids):
            if int(nid) == int(st.session_state.selected_node):
                colors[i] = "#1f77b4"; sizes[i] = 12
            if int(nid) == int(st.session_state.pending_n1):
                colors[i] = "#ff7f0e"; sizes[i] = 13

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="markers+text",
            text=[str(i) for i in ids],
            textposition="top right",
            marker=dict(size=sizes, color=colors),
            hoverinfo="skip",
            showlegend=False,
            customdata=[f"node:{int(nid)}" for nid in ids],
            name="nodes",
        ))

    # ---- loads (arrows via annotations + marker label)
    if st.session_state.loads.size:
        # label marker for selection
        xs, ys, txts, cds = [], [], [], []
        for r in st.session_state.loads:
            lid = int(r[0]); nid = int(r[1])
            Fx, Fy, M = float(r[2]), float(r[3]), float(r[4])
            i = node_index_by_id(nid)
            if i < 0:
                continue
            ax, ay = float(st.session_state.nodes[i, 1]), float(st.session_state.nodes[i, 2])

            xs.append(ax); ys.append(ay)
            txts.append(f"L{lid}")
            cds.append(f"load:{lid}")

            col = "#d62728" if st.session_state.selected_load == lid else "#aa0000"
            # Fx arrow
            if abs(Fx) > 1e-12:
                sgn = 1 if Fx > 0 else -1
                fig.add_annotation(
                    x=ax + sgn*LOAD_LEN_G, y=ay,
                    ax=ax, ay=ay,
                    xref="x", yref="y", axref="x", ayref="y",
                    showarrow=True,
                    arrowhead=2,
                    arrowwidth=2,
                    arrowcolor=col,
                )
            # Fy arrow (y-positive up in plot)
            if abs(Fy) > 1e-12:
                sgn = 1 if Fy > 0 else -1
                fig.add_annotation(
                    x=ax, y=ay + sgn*LOAD_LEN_G,
                    ax=ax, ay=ay,
                    xref="x", yref="y", axref="x", ayref="y",
                    showarrow=True,
                    arrowhead=2,
                    arrowwidth=2,
                    arrowcolor=col,
                )
            # Moment: draw a small circle + text sign (approx)
            if abs(M) > 1e-12:
                r0 = MOM_RADIUS_G
                fig.add_shape(type="circle",
                              xref="x", yref="y",
                              x0=ax-r0, y0=ay-r0, x1=ax+r0, y1=ay+r0,
                              line=dict(width=2, color=col))
                fig.add_annotation(x=ax+r0, y=ay+r0, text="⟲" if M>0 else "⟳",
                                   showarrow=False, font=dict(color=col, size=14))

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode="text",
            text=txts,
            textposition="middle right",
            hoverinfo="skip",
            showlegend=False,
            customdata=cds,
            name="loads",
        ))

    # ---- axes / grid styling similar to your canvas
    header_txt = (
        f"Zoom: {int(st.session_state.zoom_px)}px | "
        f"Grid: {GRID_UNIT} | "
        f"E: {fmt_sci_short(st.session_state.E_val)}"
    )
    fig.add_annotation(
        x=xmin + 0.5, y=ymax - 0.5,
        xref="x", yref="y",
        text=header_txt,
        showarrow=False,
        font=dict(size=12, color="#666"),
        bgcolor="rgba(255,255,255,0.6)",
        bordercolor="rgba(0,0,0,0)",
    )

    fig.update_layout(
        height=HEI,
        margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
    )
    fig.update_xaxes(
        range=[xmin, xmax],
        showgrid=True, gridcolor="#eeeeee",
        zeroline=True, zerolinecolor="#555", zerolinewidth=3,
        dtick=1,
        ticks="",
    )
    fig.update_yaxes(
        range=[ymin, ymax],
        showgrid=True, gridcolor="#eeeeee",
        zeroline=True, zerolinecolor="#555", zerolinewidth=3,
        dtick=1,
        scaleanchor="x", scaleratio=1,
        ticks="",
    )

    # Default interaction mode: pan when tool == "pan", else click-oriented
    config = {
        "displayModeBar": True,
        "scrollZoom": True,
        "doubleClick": "reset",
        "modeBarButtonsToAdd": [],
    }
    # This sets the starting dragmode; users can still switch via modebar
    fig.update_layout(dragmode="pan" if st.session_state.tool == "pan" else "zoom")

    clicks = plotly_events(
        fig,
        click_event=True,
        select_event=False,
        hover_event=False,
        key="canvas_plot",
        override_height=HEI,
        override_width=WID,
    )

    def clear_selection():
        st.session_state.selected_node = -1
        st.session_state.selected_bar = -1
        st.session_state.selected_load = -1
        st.session_state.selected_sup = -1
        st.session_state.edit_bar_mode = False
        st.session_state.edit_load_mode = False
        st.session_state.edit_sup_mode = False

    # Handle click
    if clicks:
        x = float(clicks[0]["x"])
        y = float(clicks[0]["y"])
        xg = int(round(x))
        yg = int(round(y))

        # First try select existing objects (priority like your code)
        clear_selection()

        nid = pick_node_xy(x, y)
        if nid != -1:
            st.session_state.selected_node = nid

        sid = pick_support_xy(x, y)
        if sid != -1 and nid == -1:
            st.session_state.selected_sup = sid

        lid = pick_load_xy(x, y)
        if lid != -1 and nid == -1 and sid == -1:
            st.session_state.selected_load = lid

        bid = pick_bar_xy(x, y)
        if bid != -1 and nid == -1 and sid == -1 and lid == -1:
            st.session_state.selected_bar = bid

        # Then perform tool action
        tool = st.session_state.tool

        if tool == "node":
            nid_new, _ = add_node_grid(xg, yg)
            st.session_state.selected_node = nid_new
            st.session_state.pending_n1 = -1
            st.rerun()

        if tool == "bar":
            # must click existing nodes (like your version)
            if nid == -1:
                st.warning("Für Stab: bitte auf existierenden Knoten klicken.")
            else:
                if st.session_state.pending_n1 == -1:
                    st.session_state.pending_n1 = nid
                else:
                    add_bar(st.session_state.pending_n1, nid)
                    st.session_state.pending_n1 = -1
                st.rerun()

        if tool == "load":
            if nid == -1:
                st.warning("Für Last: bitte auf existierenden Knoten klicken.")
            else:
                lid_new, _ = add_load_at_node(nid)
                st.session_state.selected_load = lid_new
                st.rerun()

        if tool == "sup":
            if nid == -1:
                st.warning("Für Auflager: bitte auf existierenden Knoten klicken.")
            else:
                sid_new, _ = add_support_at_node(nid)
                st.session_state.selected_sup = sid_new
                st.rerun()    if "loads" not in st.session_state:
        st.session_state.loads = np.zeros((0, 5), dtype=float)        # [id, nid, Fx, Fy, M]
        st.session_state.next_load_id = 1

    if "supports" not in st.session_state:
        st.session_state.supports = np.zeros((0, 5), dtype=int)       # [id, nid, ux_fix, uy_fix, rz_fix]
        st.session_state.next_sup_id = 1

    if "tool" not in st.session_state:
        st.session_state.tool = "node"

    if "pending_n1" not in st.session_state:
        st.session_state.pending_n1 = -1

init_state()

nodes = st.session_state.nodes
bars = st.session_state.bars
loads = st.session_state.loads
supports = st.session_state.supports

# =============================
# Helpers (ported from your code)
# =============================
def node_index_by_id(nid: int) -> int:
    if nodes.size == 0:
        return -1
    idx = np.where(nodes[:, 0] == int(nid))[0]
    return int(idx[0]) if idx.size else -1

def find_node_at_grid(xg: int, yg: int) -> int:
    if nodes.size == 0:
        return -1
    mask = (nodes[:, 1] == int(xg)) & (nodes[:, 2] == int(yg))
    idx = np.where(mask)[0]
    return int(nodes[idx[0], 0]) if idx.size else -1

def add_node_grid(xg: int, yg: int):
    existing = find_node_at_grid(xg, yg)
    if existing != -1:
        return existing, False
    nid = st.session_state.next_node_id
    row = np.array([[nid, xg, yg]], dtype=int)
    st.session_state.nodes = row if nodes.size == 0 else np.vstack([nodes, row])
    st.session_state.next_node_id += 1
    return nid, True

def compute_phi_deg(n1: int, n2: int) -> float:
    i1 = node_index_by_id(n1)
    i2 = node_index_by_id(n2)
    if i1 < 0 or i2 < 0:
        return 0.0
    x1 = float(st.session_state.nodes[i1, 1] * GRID_UNIT)
    y1 = float(st.session_state.nodes[i1, 2] * GRID_UNIT)
    x2 = float(st.session_state.nodes[i2, 1] * GRID_UNIT)
    y2 = float(st.session_state.nodes[i2, 2] * GRID_UNIT)
    return math.degrees(math.atan2(y2 - y1, x2 - x1))

def bar_exists(n1: int, n2: int) -> bool:
    b = st.session_state.bars
    if b.size == 0:
        return False
    a1 = b[:, 1].astype(int)
    a2 = b[:, 2].astype(int)
    return bool(np.any(((a1 == n1) & (a2 == n2)) | ((a1 == n2) & (a2 == n1))))

def add_bar(n1: int, n2: int):
    if n1 == -1 or n2 == -1 or n1 == n2:
        return -1, False
    if bar_exists(n1, n2):
        return -1, False
    bid = st.session_state.next_bar_id
    phi = compute_phi_deg(n1, n2)
    row = np.array([[bid, n1, n2, A_DEFAULT, I_DEFAULT, phi]], dtype=float)
    b = st.session_state.bars
    st.session_state.bars = row if b.size == 0 else np.vstack([b, row])
    st.session_state.next_bar_id += 1
    return bid, True

def export_system_txt(E_value: float) -> str:
    n = st.session_state.nodes
    b = st.session_state.bars
    l = st.session_state.loads
    s = st.session_state.supports

    n_nodes = int(n.shape[0])
    n_bars  = int(b.shape[0])
    n_sups  = int(s.shape[0])

    nodes_sorted = n[np.argsort(n[:, 0])] if n_nodes else n
    bars_sorted  = b[np.argsort(b[:, 0])] if n_bars else b
    sups_sorted  = s[np.argsort(s[:, 1])] if n_sups else s

    lines = []
    lines.append(f"{n_nodes:d}   {n_bars:d}")
    lines.append(f"{n_sups:d}")
    lines.append(f"{float(E_value):.6E}")

    for r in nodes_sorted:
        xg = int(r[1]); yg = int(r[2])
        lines.append(f"{xg:d}   {yg:d}")

    for r in bars_sorted:
        bid = int(r[0])
        n1  = int(r[1]); n2 = int(r[2])
        A   = float(r[3]); I = float(r[4])
        phi_deg = float(r[5])
        phi_rad = phi_deg * math.pi / 180.0
        lines.append(f"{bid:d}    {n1:d}     {n2:d}     {A:.6E}   {I:.6E}     {phi_rad:.6g}")

    for r in l:
        nid = int(r[1])
        Fx  = float(r[2]); Fy = float(r[3]); M = float(r[4])
        lines.append(f"{nid:d}    0    {Fx:.6g}    {Fy:.6g}     {M:.6g}")

    for r in sups_sorted:
        nid = int(r[1])
        uxfix = int(r[2]); uyfix = int(r[3]); rzfix = int(r[4])
        lines.append(f"{nid:d}    {uxfix:d}    {uyfix:d}    {rzfix:d}")

    return "\n".join(lines) + "\n"

# =============================
# UI
# =============================
st.set_page_config(page_title="System-Generator", layout="wide")
st.title("System-Generator")

col_left, col_right = st.columns([2.2, 1.0])

with col_right:
    st.subheader("Tools")
    st.session_state.tool = st.radio(
        "Tool",
        ["node", "bar"],
        index=["node", "bar"].index(st.session_state.tool),
        label_visibility="collapsed",
    )

    zoom_px = st.slider("Zoom (px pro Grid)", 10, 140, 25, 5)
    E_val = st.number_input("E-Modul", value=2.0e8, step=1.0e6, format="%.6e")

    txt = export_system_txt(E_val)
    st.download_button("System.txt herunterladen", data=txt, file_name="System.txt", mime="text/plain")

    if st.button("Clear", type="secondary"):
        for k in ["nodes","bars","loads","supports","next_node_id","next_bar_id","next_load_id","next_sup_id","pending_n1"]:
            st.session_state.pop(k, None)
        st.rerun()

with col_left:
    # Build plot
    fig = go.Figure()

    # Draw bars
    if st.session_state.bars.size:
        for r in st.session_state.bars:
            n1 = int(r[1]); n2 = int(r[2])
            i1 = node_index_by_id(n1); i2 = node_index_by_id(n2)
            if i1 < 0 or i2 < 0:
                continue
            x1, y1 = st.session_state.nodes[i1, 1], st.session_state.nodes[i1, 2]
            x2, y2 = st.session_state.nodes[i2, 1], st.session_state.nodes[i2, 2]
            fig.add_trace(go.Scatter(x=[x1, x2], y=[y1, y2], mode="lines", name=f"Bar {int(r[0])}", showlegend=False))

    # Draw nodes
    if st.session_state.nodes.size:
        fig.add_trace(go.Scatter(
            x=st.session_state.nodes[:, 1],
            y=st.session_state.nodes[:, 2],
            mode="markers+text",
            text=st.session_state.nodes[:, 0].astype(str),
            textposition="top right",
            showlegend=False
        ))

    # Layout like a grid canvas
    fig.update_layout(
        height=HEI,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(showgrid=True, zeroline=True, dtick=1),
        yaxis=dict(showgrid=True, zeroline=True, dtick=1, scaleanchor="x", scaleratio=1),
    )

    clicks = plotly_events(fig, click_event=True, select_event=False, hover_event=False, key="plot")

    if clicks:
        # plotly returns data coords; take first click
        x = clicks[0]["x"]
        y = clicks[0]["y"]
        xg = int(round(x))
        yg = int(round(y))

        if st.session_state.tool == "node":
            add_node_grid(xg, yg)
            st.rerun()

        if st.session_state.tool == "bar":
            # bar tool: click node A then node B
            nid = find_node_at_grid(xg, yg)
            if nid == -1:
                st.info("Für Stab: erst auf existierenden Knoten klicken.")
            else:
                if st.session_state.pending_n1 == -1:
                    st.session_state.pending_n1 = nid
                else:
                    add_bar(st.session_state.pending_n1, nid)
                    st.session_state.pending_n1 = -1
                st.rerun()
