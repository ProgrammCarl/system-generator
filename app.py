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
draw_scene()
