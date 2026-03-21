"""
Generates a minimal eDCR-ready DXF shell with plot boundary,
building footprint, setback lines, and key annotation.
"""

import io
import ezdxf
from io import StringIO
from ezdxf import colors
from ezdxf.enums import TextEntityAlignment


def generate_compliance_shell_dxf(params: dict) -> bytes:
    """
    Returns DXF bytes containing:
    - Layer PLOT_BOUNDARY  — outer plot rectangle
    - Layer BUILDING_FOOTPRINT — building footprint (setbacks applied)
    - Layer SETBACK_LINES  — dashed setback offset lines
    - Layer DIMENSIONS     — annotated dimensions
    - Layer NOTES          — title block and disclaimer

    Coordinate system: origin at plot SW corner, units = metres.
    """
    plot_w_ft = float(params.get("plot_width_ft", 30))
    plot_d_ft = float(params.get("plot_depth_ft", 40))
    plot_w = round(plot_w_ft * 0.3048, 3)   # ft → m
    plot_d = round(plot_d_ft * 0.3048, 3)

    front_m  = float(params.get("provided_front_m", 3.0))
    rear_m   = float(params.get("provided_rear_m", 1.5))
    side_m   = float(params.get("provided_side_m", 1.5))

    zone     = params.get("zone_type", "residential_R1")
    road_w   = params.get("road_width_ft", 20)
    owner    = params.get("owner_name", "Owner")
    floors   = params.get("floors", 2)
    height_m = params.get("proposed_height_m", 7.0)

    # Building footprint corners
    bld_x0 = side_m
    bld_y0 = rear_m
    bld_x1 = plot_w - side_m
    bld_y1 = plot_d - front_m

    doc = ezdxf.new(dxfversion="R2010")
    doc.units = 6  # metres

    msp = doc.modelspace()

    # ── Layers ────────────────────────────────────────────────────────────────
    for name, color, ltype in [
        ("PLOT_BOUNDARY",      colors.WHITE,   "CONTINUOUS"),
        ("BUILDING_FOOTPRINT", colors.CYAN,    "CONTINUOUS"),
        ("SETBACK_LINES",      colors.YELLOW,  "DASHED"),
        ("DIMENSIONS",         colors.GREEN,   "CONTINUOUS"),
        ("NOTES",              colors.RED,     "CONTINUOUS"),
    ]:
        layer = doc.layers.new(name)
        layer.color = color
        if ltype != "CONTINUOUS":
            try:
                doc.linetypes.get(ltype)
            except Exception:
                doc.linetypes.new(ltype, dxfattribs={"description": ltype, "pattern": [0.5, 0.25, -0.25]})
            layer.linetype = ltype

    # ── Plot boundary ─────────────────────────────────────────────────────────
    msp.add_lwpolyline(
        [(0, 0), (plot_w, 0), (plot_w, plot_d), (0, plot_d)],
        close=True,
        dxfattribs={"layer": "PLOT_BOUNDARY", "lineweight": 50},
    )

    # ── Building footprint ────────────────────────────────────────────────────
    if bld_x1 > bld_x0 and bld_y1 > bld_y0:
        msp.add_lwpolyline(
            [(bld_x0, bld_y0), (bld_x1, bld_y0), (bld_x1, bld_y1), (bld_x0, bld_y1)],
            close=True,
            dxfattribs={"layer": "BUILDING_FOOTPRINT", "lineweight": 35},
        )

    # ── Setback reference lines (dashed) ──────────────────────────────────────
    # Front setback line
    msp.add_line((0, plot_d - front_m), (plot_w, plot_d - front_m),
                 dxfattribs={"layer": "SETBACK_LINES"})
    # Rear setback line
    msp.add_line((0, rear_m), (plot_w, rear_m),
                 dxfattribs={"layer": "SETBACK_LINES"})
    # Side setback lines
    msp.add_line((side_m, 0), (side_m, plot_d),
                 dxfattribs={"layer": "SETBACK_LINES"})
    msp.add_line((plot_w - side_m, 0), (plot_w - side_m, plot_d),
                 dxfattribs={"layer": "SETBACK_LINES"})

    # ── Dimension annotations ─────────────────────────────────────────────────
    txt_h = 0.18
    mid_w = plot_w / 2
    mid_d = plot_d / 2

    # Plot width label (bottom)
    msp.add_text(
        f"Plot Width: {plot_w:.2f}m ({plot_w_ft:.0f}ft)",
        dxfattribs={"layer": "DIMENSIONS", "height": txt_h,
                    "insert": (mid_w, -0.5), "halign": 4},
    ).set_placement((mid_w, -0.5), align=TextEntityAlignment.MIDDLE_CENTER)

    # Plot depth label (left side)
    msp.add_text(
        f"Plot Depth: {plot_d:.2f}m ({plot_d_ft:.0f}ft)",
        dxfattribs={"layer": "DIMENSIONS", "height": txt_h,
                    "insert": (-0.6, mid_d), "rotation": 90},
    ).set_placement((-0.6, mid_d), align=TextEntityAlignment.MIDDLE_CENTER)

    # Front setback label
    msp.add_text(
        f"Front: {front_m}m",
        dxfattribs={"layer": "DIMENSIONS", "height": txt_h * 0.85,
                    "insert": (mid_w, plot_d - front_m / 2)},
    ).set_placement((mid_w, plot_d - front_m / 2), align=TextEntityAlignment.MIDDLE_CENTER)

    # Rear setback label
    msp.add_text(
        f"Rear: {rear_m}m",
        dxfattribs={"layer": "DIMENSIONS", "height": txt_h * 0.85,
                    "insert": (mid_w, rear_m / 2)},
    ).set_placement((mid_w, rear_m / 2), align=TextEntityAlignment.MIDDLE_CENTER)

    # ── Title block ───────────────────────────────────────────────────────────
    notes = [
        ("DRAFT — NOT FOR SUBMISSION", 0.30),
        (f"Owner: {owner}", 0.20),
        (f"Zone: {zone}  |  Road: {road_w}ft  |  Floors: {floors}  |  Ht: {height_m}m", 0.16),
        ("Rules: TNCDBR 2019 + G.O.Ms.No.70 (Mar 2024)", 0.14),
        ("Generated by BuildIQ — Architect must verify all dimensions", 0.14),
    ]
    y_cursor = plot_d + 1.2
    for text, h in notes:
        msp.add_text(
            text,
            dxfattribs={"layer": "NOTES", "height": h, "insert": (0, y_cursor)},
        )
        y_cursor += h + 0.08

    buf = StringIO()
    doc.write(buf)
    return buf.getvalue().encode("utf-8")
