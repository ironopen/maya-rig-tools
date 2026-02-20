"""
Rig Module Builder for Autodesk Maya
-----------------------------------
A starter rigging utility with:
- IK Arm module
- FK Arm module
- IK Leg module
- FK Leg module
- Spine (FK + optional IK spline)
- Control shape library
- Color presets / override tools
- Extra quality-of-life helpers (freeze, zero groups, mirror names)

Usage:
1) In Maya Script Editor (Python tab):
   import rig_module_builder as rmb
   rmb.show_ui()

2) Or run directly after dragging into Maya and executing:
   import rig_module_builder
   rig_module_builder.show_ui()
"""

import maya.cmds as cmds

WIN = "rigModuleBuilderWin"

# -------------------------
# Naming + Color Utilities
# -------------------------

COLOR_INDEX = {
    "red": 13,
    "blue": 6,
    "yellow": 17,
    "green": 14,
    "pink": 9,
    "cyan": 18,
    "white": 16,
    "orange": 21,
}


def safe_parent(child, parent):
    if cmds.objExists(child) and cmds.objExists(parent):
        try:
            cmds.parent(child, parent)
        except Exception:
            pass


def make_zero_group(node):
    """Create a zero group above node and keep transforms."""
    if not cmds.objExists(node):
        return None
    grp = cmds.group(em=True, n=f"{node}_ZRO")
    m = cmds.xform(node, q=True, ws=True, m=True)
    cmds.xform(grp, ws=True, m=m)
    parent = cmds.listRelatives(node, p=True)
    if parent:
        safe_parent(grp, parent[0])
    safe_parent(node, grp)
    return grp


def set_ctrl_color(ctrl, color_name="yellow"):
    if not cmds.objExists(ctrl):
        return
    shapes = cmds.listRelatives(ctrl, s=True, ni=True) or []
    idx = COLOR_INDEX.get(color_name.lower(), 17)
    for s in shapes:
        cmds.setAttr(f"{s}.overrideEnabled", 1)
        cmds.setAttr(f"{s}.overrideColor", idx)


def freeze_and_clean(node):
    if not cmds.objExists(node):
        return
    try:
        cmds.makeIdentity(node, apply=True, t=True, r=True, s=True, n=False)
    except Exception:
        pass


# -------------------------
# Control Shape Library
# -------------------------

def create_control(name, shape="circle", size=1.0, axis="x", color="yellow"):
    shape = shape.lower()

    if shape == "circle":
        normal = (1, 0, 0) if axis == "x" else (0, 1, 0) if axis == "y" else (0, 0, 1)
        ctrl = cmds.circle(n=name, nr=normal, r=size, ch=False)[0]

    elif shape == "square":
        pts = [(-1, 0, -1), (-1, 0, 1), (1, 0, 1), (1, 0, -1), (-1, 0, -1)]
        ctrl = cmds.curve(n=name, d=1, p=pts)
        cmds.scale(size, size, size, ctrl, r=True)

    elif shape == "cube":
        pts = [
            (-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1), (-1, -1, -1),
            (-1, 1, -1), (1, 1, -1), (1, -1, -1), (1, 1, -1), (1, 1, 1),
            (1, -1, 1), (1, 1, 1), (-1, 1, 1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)
        ]
        ctrl = cmds.curve(n=name, d=1, p=pts)
        cmds.scale(size, size, size, ctrl, r=True)

    elif shape == "arrow":
        pts = [(-1, 0, 0), (0.2, 0, 0), (0.2, 0, 0.4), (1, 0, 0), (0.2, 0, -0.4), (0.2, 0, 0), (-1, 0, 0)]
        ctrl = cmds.curve(n=name, d=1, p=pts)
        cmds.scale(size, size, size, ctrl, r=True)

    else:  # fallback
        ctrl = cmds.circle(n=name, nr=(1, 0, 0), r=size, ch=False)[0]

    freeze_and_clean(ctrl)
    set_ctrl_color(ctrl, color)
    return ctrl


# -------------------------
# Rig Module Builders
# -------------------------

def duplicate_chain(chain, suffix):
    new = []
    for j in chain:
        dup = cmds.duplicate(j, po=True, n=f"{j}_{suffix}")[0]
        new.append(dup)
    for i in range(1, len(new)):
        safe_parent(new[i], new[i - 1])
    return new


def create_fk_module(joints, side="L", color="blue"):
    ctrls = []
    prev_ctrl = None
    for j in joints:
        c = create_control(f"{j}_FK_CTRL", shape="circle", size=1.5, axis="x", color=color)
        z = make_zero_group(c)
        m = cmds.xform(j, q=True, ws=True, m=True)
        cmds.xform(z, ws=True, m=m)
        cmds.parentConstraint(c, j, mo=True)
        if prev_ctrl:
            safe_parent(z, prev_ctrl)
        prev_ctrl = c
        ctrls.append(c)
    return ctrls


def create_ik_arm_module(shoulder, elbow, wrist, side="L", color="blue"):
    ikh, eff = cmds.ikHandle(sj=shoulder, ee=wrist, sol='ikRPsolver', n=f"{side}_arm_IK_HDL")
    pv = create_control(f"{side}_arm_PV_CTRL", shape="diamond", size=1.0, color=color)
    # diamond fallback if missing
    if not cmds.objExists(pv):
        pv = create_control(f"{side}_arm_PV_CTRL", shape="arrow", size=1.0, color=color)
    ik_ctrl = create_control(f"{side}_arm_IK_CTRL", shape="cube", size=1.6, color=color)

    # snap IK ctrl to wrist
    m = cmds.xform(wrist, q=True, ws=True, m=True)
    z = make_zero_group(ik_ctrl)
    cmds.xform(z, ws=True, m=m)
    safe_parent(ikh, ik_ctrl)

    # place pole vector roughly in front of elbow
    pos = cmds.xform(elbow, q=True, ws=True, t=True)
    pv_z = make_zero_group(pv)
    cmds.xform(pv_z, ws=True, t=(pos[0], pos[1], pos[2] + 8))
    cmds.poleVectorConstraint(pv, ikh)

    return {"ikHandle": ikh, "ikCtrl": ik_ctrl, "pvCtrl": pv}


def create_ik_leg_module(hip, knee, ankle, side="L", color="blue"):
    ikh, eff = cmds.ikHandle(sj=hip, ee=ankle, sol='ikRPsolver', n=f"{side}_leg_IK_HDL")
    ik_ctrl = create_control(f"{side}_leg_IK_CTRL", shape="cube", size=1.8, color=color)
    z = make_zero_group(ik_ctrl)
    m = cmds.xform(ankle, q=True, ws=True, m=True)
    cmds.xform(z, ws=True, m=m)
    safe_parent(ikh, ik_ctrl)

    pv = create_control(f"{side}_leg_PV_CTRL", shape="arrow", size=1.2, color=color)
    pv_z = make_zero_group(pv)
    pos = cmds.xform(knee, q=True, ws=True, t=True)
    cmds.xform(pv_z, ws=True, t=(pos[0], pos[1], pos[2] + 10))
    cmds.poleVectorConstraint(pv, ikh)

    # Foot roll attrs
    for attr in ["footRoll", "toeTap", "heelPivot", "bankIn", "bankOut"]:
        if not cmds.attributeQuery(attr, n=ik_ctrl, exists=True):
            cmds.addAttr(ik_ctrl, ln=attr, at='double', k=True)

    return {"ikHandle": ikh, "ikCtrl": ik_ctrl, "pvCtrl": pv}


def create_spine_module(spine_joints, color="yellow", ik_spline=False):
    fk_ctrls = create_fk_module(spine_joints, side="C", color=color)
    out = {"fkCtrls": fk_ctrls}

    if ik_spline and len(spine_joints) >= 3:
        ikh, curve = cmds.ikHandle(sj=spine_joints[0], ee=spine_joints[-1], sol='ikSplineSolver', ccv=False, pcv=False, n="C_spine_IK_HDL")
        start = create_control("C_spineStart_IK_CTRL", shape="circle", size=2.0, axis="y", color=color)
        end = create_control("C_spineEnd_IK_CTRL", shape="circle", size=2.0, axis="y", color=color)
        out.update({"ikHandle": ikh, "curve": curve, "startCtrl": start, "endCtrl": end})

    return out


# -------------------------
# Module from Selection
# -------------------------

def _selected_joints(min_count=2):
    sel = cmds.ls(sl=True, type='joint') or []
    if len(sel) < min_count:
        cmds.warning(f"Select at least {min_count} joints.")
        return []
    return sel


def build_fk_arm(*_):
    j = _selected_joints(3)
    if not j:
        return
    create_fk_module(j[:3], side="L", color="blue")


def build_ik_arm(*_):
    j = _selected_joints(3)
    if not j:
        return
    create_ik_arm_module(j[0], j[1], j[2], side="L", color="blue")


def build_fk_leg(*_):
    j = _selected_joints(3)
    if not j:
        return
    create_fk_module(j[:3], side="L", color="blue")


def build_ik_leg(*_):
    j = _selected_joints(3)
    if not j:
        return
    create_ik_leg_module(j[0], j[1], j[2], side="L", color="blue")


def build_spine(*_):
    j = _selected_joints(3)
    if not j:
        return
    create_spine_module(j, color="yellow", ik_spline=False)


def add_controls_to_selection(*_):
    sel = cmds.ls(sl=True) or []
    if not sel:
        cmds.warning("Select one or more objects.")
        return
    for obj in sel:
        c = create_control(f"{obj}_CTRL", shape="circle", size=1.2, axis="x", color="yellow")
        z = make_zero_group(c)
        m = cmds.xform(obj, q=True, ws=True, m=True)
        cmds.xform(z, ws=True, m=m)


def colorize_selection(color):
    sel = cmds.ls(sl=True) or []
    for s in sel:
        set_ctrl_color(s, color)


# -------------------------
# UI
# -------------------------

def show_ui():
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)

    cmds.window(WIN, title="Rig Module Builder", sizeable=False, widthHeight=(360, 520))
    cmds.columnLayout(adj=True, rs=8)

    cmds.text(l="Rig Module Builder (Maya)", fn="boldLabelFont", h=24)
    cmds.separator(h=8, style='in')
    cmds.text(l="Select relevant joints before creating modules.")

    cmds.frameLayout(l="Arm Modules", collapsable=True, cl=False, mw=8, mh=8)
    cmds.rowLayout(nc=2, cw2=(170, 170), adjustableColumn=2)
    cmds.button(l="Build FK Arm", c=build_fk_arm)
    cmds.button(l="Build IK Arm", c=build_ik_arm)
    cmds.setParent('..')
    cmds.setParent('..')

    cmds.frameLayout(l="Leg Modules", collapsable=True, cl=False, mw=8, mh=8)
    cmds.rowLayout(nc=2, cw2=(170, 170), adjustableColumn=2)
    cmds.button(l="Build FK Leg", c=build_fk_leg)
    cmds.button(l="Build IK Leg", c=build_ik_leg)
    cmds.setParent('..')
    cmds.setParent('..')

    cmds.frameLayout(l="Spine", collapsable=True, cl=False, mw=8, mh=8)
    cmds.button(l="Build Spine (FK)", c=build_spine)
    cmds.setParent('..')

    cmds.frameLayout(l="Control Utilities", collapsable=True, cl=False, mw=8, mh=8)
    cmds.button(l="Create Controls For Selection", c=add_controls_to_selection)

    cmds.rowLayout(nc=4, cw4=(85, 85, 85, 85))
    cmds.button(l="Red", c=lambda *_: colorize_selection("red"))
    cmds.button(l="Blue", c=lambda *_: colorize_selection("blue"))
    cmds.button(l="Yellow", c=lambda *_: colorize_selection("yellow"))
    cmds.button(l="Green", c=lambda *_: colorize_selection("green"))
    cmds.setParent('..')

    cmds.rowLayout(nc=4, cw4=(85, 85, 85, 85))
    cmds.button(l="Pink", c=lambda *_: colorize_selection("pink"))
    cmds.button(l="Cyan", c=lambda *_: colorize_selection("cyan"))
    cmds.button(l="White", c=lambda *_: colorize_selection("white"))
    cmds.button(l="Orange", c=lambda *_: colorize_selection("orange"))
    cmds.setParent('..')

    cmds.setParent('..')

    cmds.separator(h=10, style='in')
    cmds.text(l="Extra ideas included: foot roll attrs, zero groups, color tools.")
    cmds.text(l="Tip: duplicate deformation chain for clean game/film rig layers.")

    cmds.showWindow(WIN)


if __name__ == "__main__":
    show_ui()
