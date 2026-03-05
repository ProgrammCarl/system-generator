import math
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events

# =========================================================
# Config (close to your original)
# =========================================================
GRID_UNIT = 10
WID, HEI = 900, 550

PICK_R_G_MIN = 0.6  # pick radius in "grid units" (for selection)

A_DEFAULT = 1.0
I_DEFAULT = 1.0
PHI_DEFAULT = 0.0

FX_DEFAULT = 0.0
FY_DEFAULT = -1.0
M_DEFAULT  = 0.0

SUP_UX_DEFAULT = 1
SUP_UY_DEFAULT = 1
SUP_RZ_DEFAULT = 0

# “pixel constant” look (approx; in Plotly it's not truly pixel constant)
LOAD_LEN_G = 1.8
MOM_RADIUS_G = 0.9

# =========================================================
# Streamlit setup
# =========================================================
st.set_page_config(page_title="System-Generator", layout="wide")
st.title("System-Generator")

# =========================================================
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
