import math
import numpy as np
import streamlit as st
import plotly.graph_objects as go
from streamlit_plotly_events import plotly_events

# =============================
# Config
# =============================
GRID_UNIT = 10  # bleibt bei dir semantisch, für Export
WID, HEI = 900, 550

A_DEFAULT = 1.0
I_DEFAULT = 1.0
PHI_DEFAULT = 0.0

FX_DEFAULT = 0.0
FY_DEFAULT = -1.0
M_DEFAULT  = 0.0

SUP_UX_DEFAULT = 1
SUP_UY_DEFAULT = 1
SUP_RZ_DEFAULT = 0

# =============================
# Session state init
# =============================
def init_state():
    if "nodes" not in st.session_state:
        st.session_state.nodes = np.zeros((0, 3), dtype=int)          # [id, xg, yg]
        st.session_state.next_node_id = 1

    if "bars" not in st.session_state:
        st.session_state.bars = np.zeros((0, 6), dtype=float)         # [id, n1, n2, A, I, phi_deg]
        st.session_state.next_bar_id = 1

    if "loads" not in st.session_state:
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
