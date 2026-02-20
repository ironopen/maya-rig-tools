"""
Rig Module Builder v2 for Autodesk Maya
=======================================

What this script gives you:
- FK modules (arms/legs/spine)
- IK limb modules (arms/legs) with optional stretch
- FK/IK switch module for 3-joint limbs (upper/mid/lower)
- IK Spline spine option
- Control shape + color utilities
- Naming helpers + simple left/right rename mirroring

Authoring notes:
- This is a production-friendly *starter* system, not a full autorigger.
- Every major function is commented so you can learn/extend quickly.
- Works best when your selected joint chains are clean and oriented.

Usage in Maya Script Editor (Python):
    import rig_module_builder_v2 as rmb
    rmb.show_ui()
"""

import maya.cmds as cmds

WIN = "rigModuleBuilderV2Win"

# -------------------------------------
# Configuration / Naming / Color Tables
# -------------------------------------

SIDE_COLOR = {
    "L": "blue",
    "R": "red",
    "C": "yellow",
}

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


def format_name(side, part, suffix):
    """Simple naming template: L_arm_IK_CTRL, C_spine_FK_CTRL, etc."""
    return f"{side}_{part}_{suffix}"


# -----------------
# Utility Functions
# -----------------

def safe_parent(child, parent):
    if cmds.objExists(child) and cmds.objExists(parent):
        try:
            cmds.parent(child, parent)
        except Exception:
            pass


def align_to(source, target):
    """Match target transform to source (world matrix)."""
    if not cmds.objExists(source) or not cmds.objExists(target):
        return
    m = cmds.xform(source, q=True, ws=True, m=True)
    cmds.xform(target, ws=True, m=m)


def make_zero_group(node):
    """
    Create a zero group above node to preserve clean animator values.
    Example:
        arm_CTRL
          └── arm_CTRL_ZRO
    """
    if not cmds.objExists(node):
        return None

    zro = cmds.group(em=True, n=f"{node}_ZRO")
    align_to(node, zro)

    parent = cmds.listRelatives(node, p=True) or []
    if parent:
        safe_parent(zro, parent[0])

    safe_parent(node, zro)
    return zro


def freeze_clean(node):
    """Freeze TRS on controls so they start neutral."""
    if not cmds.objExists(node):
        return
    try:
        cmds.makeIdentity(node, apply=True, t=True, r=True, s=True, n=False)
    except Exception:
        pass


def set_ctrl_color(ctrl, color_name="yellow"):
    """Apply viewport color override to all shape nodes under control."""
    if not cmds.objExists(ctrl):
        return

    idx = COLOR_INDEX.get(color_name.lower(), 17)
    shapes = cmds.listRelatives(ctrl, s=True, ni=True) or []
    for s in shapes:
        cmds.setAttr(f"{s}.overrideEnabled", 1)
        cmds.setAttr(f"{s}.overrideColor", idx)


# ----------------------------
# Control Shape Construction
# ----------------------------

def create_control(name, shape="circle", size=1.0, axis="x", color="yellow"):
    """Build a NURBS curve control in common rigging shapes."""
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
        pts = [(-1, 0, 0), (0.2, 0, 0), (0.2, 0, 0.5), (1, 0, 0), (0.2, 0, -0.5), (0.2, 0, 0), (-1, 0, 0)]
        ctrl = cmds.curve(n=name, d=1, p=pts)
        cmds.scale(size, size, size, ctrl, r=True)

    elif shape == "diamond":
        pts = [(0, 1, 0), (1, 0, 0), (0, -1, 0), (-1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0), (0, 0, -1), (-1, 0, 0), (0, 0, 1)]
        ctrl = cmds.curve(n=name, d=1, p=pts)
        cmds.scale(size, size, size, ctrl, r=True)

    else:
        ctrl = cmds.circle(n=name, nr=(1, 0, 0), r=size, ch=False)[0]

    freeze_clean(ctrl)
    set_ctrl_color(ctrl, color)
    return ctrl


# ----------------------------
# Selection / Chain Utilities
# ----------------------------

def selected_joints(min_count=2):
    sel = cmds.ls(sl=True, type="joint") or []
    if len(sel) < min_count:
        cmds.warning(f"Select at least {min_count} joints.")
        return []
    return sel


def duplicate_chain(chain, suffix):
    """Duplicate a joint chain preserving transforms and hierarchy."""
    out = []
    for j in chain:
        out.append(cmds.duplicate(j, po=True, n=f"{j}_{suffix}")[0])
    for i in range(1, len(out)):
        safe_parent(out[i], out[i - 1])
    return out


# -----------------
# FK Module Builder
# -----------------

def build_fk_chain(chain, side="L", color=None, part="limb"):
    """
    Build FK controls for each joint.
    - Creates one control per joint
    - Parent constraints each joint
    - Parents control zero groups hierarchically
    """
    color = color or SIDE_COLOR.get(side, "yellow")
    ctrls = []
    prev = None

    for j in chain:
        ctrl = create_control(f"{j}_FK_CTRL", shape="circle", size=1.4, axis="x", color=color)
        zro = make_zero_group(ctrl)
        align_to(j, zro)

        cmds.parentConstraint(ctrl, j, mo=True)

        if prev:
            safe_parent(zro, prev)

        prev = ctrl
        ctrls.append(ctrl)

    grp = cmds.group(ctrls[0] + "_ZRO", n=format_name(side, part, "FK_GRP")) if ctrls else None
    return {"ctrls": ctrls, "group": grp}


# -----------------
# IK Module Builder
# -----------------

def _distance_between(node_a, node_b, name):
    """Create distanceDimension setup and return (distanceNode, locA, locB)."""
    pa = cmds.xform(node_a, q=True, ws=True, t=True)
    pb = cmds.xform(node_b, q=True, ws=True, t=True)

    dist_shape = cmds.distanceDimension(sp=pa, ep=pb)
    dist = cmds.listRelatives(dist_shape, p=True)[0]
    dist = cmds.rename(dist, name)

    locs = cmds.listConnections(dist_shape, type="locator") or []
    locA = cmds.listRelatives(locs[0], p=True)[0]
    locB = cmds.listRelatives(locs[1], p=True)[0]

    return dist_shape, locA, locB


def add_stretch_to_ik(chain, ik_ctrl, ik_handle, module_name="IK"):
    """
    Simple stretchy IK setup for 3-joint limb:
    - Measure distance from root to IK control
    - Compare to original limb length
    - Scale upper/mid joint X when distance is larger
    """
    if len(chain) < 3:
        cmds.warning("Stretch setup expects at least 3 joints.")
        return

    j0, j1, j2 = chain[0], chain[1], chain[2]

    # Original segment lengths (assumes X is aim axis)
    len1 = abs(cmds.getAttr(f"{j1}.tx"))
    len2 = abs(cmds.getAttr(f"{j2}.tx"))
    original = max(0.001, len1 + len2)

    # Distance setup
    dist_shape, locA, locB = _distance_between(j0, ik_ctrl, f"{module_name}_DIST")
    safe_parent(locA, j0)
    safe_parent(locB, ik_ctrl)

    # Nodes: ratio = currentDist / original
    md = cmds.createNode("multiplyDivide", n=f"{module_name}_stretch_MD")
    cond = cmds.createNode("condition", n=f"{module_name}_stretch_COND")

    cmds.setAttr(f"{md}.operation", 2)  # divide
    cmds.setAttr(f"{md}.input2X", original)
    cmds.connectAttr(f"{dist_shape}.distance", f"{md}.input1X", f=True)

    # if distance > original use ratio else 1
    cmds.setAttr(f"{cond}.operation", 2)  # greater than
    cmds.setAttr(f"{cond}.secondTerm", original)
    cmds.setAttr(f"{cond}.colorIfFalseR", 1.0)
    cmds.connectAttr(f"{dist_shape}.distance", f"{cond}.firstTerm", f=True)
    cmds.connectAttr(f"{md}.outputX", f"{cond}.colorIfTrueR", f=True)

    # drive scales on upper and mid joints
    cmds.connectAttr(f"{cond}.outColorR", f"{j0}.scaleX", f=True)
    cmds.connectAttr(f"{cond}.outColorR", f"{j1}.scaleX", f=True)


def build_ik_limb(chain, side="L", part="arm", color=None, stretchy=False):
    """Build RP IK limb with IK control + pole vector control."""
    if len(chain) < 3:
        cmds.warning("IK limb needs 3 joints: upper, mid, lower.")
        return {}

    color = color or SIDE_COLOR.get(side, "blue")

    upper, mid, lower = chain[0], chain[1], chain[2]
    ikh, _ = cmds.ikHandle(sj=upper, ee=lower, sol="ikRPsolver", n=format_name(side, part, "IK_HDL"))

    ik_ctrl = create_control(format_name(side, part, "IK_CTRL"), shape="cube", size=1.6, color=color)
    ik_zro = make_zero_group(ik_ctrl)
    align_to(lower, ik_zro)
    safe_parent(ikh, ik_ctrl)

    pv_ctrl = create_control(format_name(side, part, "PV_CTRL"), shape="diamond", size=1.1, color=color)
    pv_zro = make_zero_group(pv_ctrl)

    # place PV in front of mid joint (simple heuristic)
    p = cmds.xform(mid, q=True, ws=True, t=True)
    cmds.xform(pv_zro, ws=True, t=(p[0], p[1], p[2] + 10.0))
    cmds.poleVectorConstraint(pv_ctrl, ikh)

    grp = cmds.group([ik_zro, pv_zro], n=format_name(side, part, "IK_GRP"))

    if part == "leg":
        # Add starter foot attributes for future expansion
        for attr in ["footRoll", "toeTap", "heelPivot", "bankIn", "bankOut"]:
            if not cmds.attributeQuery(attr, n=ik_ctrl, exists=True):
                cmds.addAttr(ik_ctrl, ln=attr, at="double", k=True)

    if stretchy:
        add_stretch_to_ik(chain, ik_ctrl, ikh, module_name=f"{side}_{part}")

    return {"ikHandle": ikh, "ikCtrl": ik_ctrl, "pvCtrl": pv_ctrl, "group": grp}


# ---------------------
# FK/IK Switch Builder
# ---------------------

def build_fkik_switch(bind_chain, side="L", part="arm", stretchy_ik=False):
    """
    Build a basic FK/IK switch system:
    1) Duplicate bind chain into FK and IK driver chains
    2) Build FK controls on FK chain
    3) Build IK module on IK chain
    4) Constrain bind joints from FK + IK joints
    5) Add switch attr and wire constraint weights

    Expected chain size: 3 joints for limbs.
    """
    if len(bind_chain) < 3:
        cmds.warning("FK/IK switch requires at least 3 joints selected.")
        return {}

    bind_chain = bind_chain[:3]

    fk_chain = duplicate_chain(bind_chain, "FKDRV")
    ik_chain = duplicate_chain(bind_chain, "IKDRV")

    fk = build_fk_chain(fk_chain, side=side, part=part)
    ik = build_ik_limb(ik_chain, side=side, part=part, stretchy=stretchy_ik)

    settings = create_control(format_name(side, part, "SETTINGS_CTRL"), shape="square", size=1.0, color="white")
    settings_zro = make_zero_group(settings)
    align_to(bind_chain[-1], settings_zro)
    cmds.xform(settings_zro, ws=True, t=[cmds.xform(settings_zro, q=True, ws=True, t=True)[0], cmds.xform(settings_zro, q=True, ws=True, t=True)[1] - 4, cmds.xform(settings_zro, q=True, ws=True, t=True)[2]])

    if not cmds.attributeQuery("fkIk", n=settings, exists=True):
        cmds.addAttr(settings, ln="fkIk", at="double", min=0, max=1, dv=0, k=True)

    rev = cmds.createNode("reverse", n=format_name(side, part, "fkIk_REV"))
    cmds.connectAttr(f"{settings}.fkIk", f"{rev}.inputX", f=True)

    # For each bind joint, blend between FK and IK chain
    for i, bj in enumerate(bind_chain):
        pc = cmds.parentConstraint(fk_chain[i], ik_chain[i], bj, mo=False, n=f"{bj}_fkik_PC")[0]
        w = cmds.parentConstraint(pc, q=True, wal=True)  # weight attrs
        if len(w) >= 2:
            # FK weight = reverse, IK weight = fkIk
            cmds.connectAttr(f"{rev}.outputX", f"{pc}.{w[0]}", f=True)
            cmds.connectAttr(f"{settings}.fkIk", f"{pc}.{w[1]}", f=True)

    # Optional visibility switching for animator clarity
    fk_root_zro = f"{fk['ctrls'][0]}_ZRO" if fk.get("ctrls") else None
    ik_grp = ik.get("group")
    if fk_root_zro and cmds.objExists(fk_root_zro) and ik_grp and cmds.objExists(ik_grp):
        cmds.connectAttr(f"{rev}.outputX", f"{fk_root_zro}.visibility", f=True)
        cmds.connectAttr(f"{settings}.fkIk", f"{ik_grp}.visibility", f=True)

    return {
        "bind": bind_chain,
        "fk": fk,
        "ik": ik,
        "settingsCtrl": settings,
    }


# -----------------
# Spine Module (FK)
# -----------------

def build_spine(chain, ik_spline=False):
    """Build spine FK controls and optional IK spline handle."""
    fk = build_fk_chain(chain, side="C", part="spine", color="yellow")
    out = {"fk": fk}

    if ik_spline and len(chain) >= 3:
        ikh, curve = cmds.ikHandle(
            sj=chain[0], ee=chain[-1],
            sol="ikSplineSolver",
            ccv=False, pcv=False,
            n=format_name("C", "spine", "IK_HDL")
        )
        start_ctrl = create_control(format_name("C", "spineStart", "IK_CTRL"), shape="circle", size=2.0, axis="y", color="yellow")
        end_ctrl = create_control(format_name("C", "spineEnd", "IK_CTRL"), shape="circle", size=2.0, axis="y", color="yellow")
        out.update({"ikHandle": ikh, "curve": curve, "startCtrl": start_ctrl, "endCtrl": end_ctrl})

    return out


# ------------------------
# Additional Rigging Tools
# ------------------------

def mirror_selected_names():
    """
    Rename selected nodes from L_* to R_* or R_* to L_*.
    Useful for quick mirrored control naming pass.
    """
    sel = cmds.ls(sl=True) or []
    for n in sel:
        if n.startswith("L_"):
            cmds.rename(n, "R_" + n[2:])
        elif n.startswith("R_"):
            cmds.rename(n, "L_" + n[2:])


def create_ctrls_for_selection():
    """Create generic controls for selected objects and align them."""
    sel = cmds.ls(sl=True) or []
    if not sel:
        cmds.warning("Select one or more objects.")
        return

    for obj in sel:
        ctrl = create_control(f"{obj}_CTRL", shape="circle", size=1.2, axis="x", color="yellow")
        zro = make_zero_group(ctrl)
        align_to(obj, zro)


def colorize_selection(color):
    sel = cmds.ls(sl=True) or []
    for s in sel:
        set_ctrl_color(s, color)


# --------------------
# UI Button Callbacks
# --------------------

def cb_fk_arm(*_):
    chain = selected_joints(3)
    if chain:
        build_fk_chain(chain[:3], side="L", part="arm")


def cb_ik_arm(*_):
    chain = selected_joints(3)
    if chain:
        stretchy = cmds.checkBox("rmbV2_stretch", q=True, v=True)
        build_ik_limb(chain[:3], side="L", part="arm", stretchy=stretchy)


def cb_fk_leg(*_):
    chain = selected_joints(3)
    if chain:
        build_fk_chain(chain[:3], side="L", part="leg")


def cb_ik_leg(*_):
    chain = selected_joints(3)
    if chain:
        stretchy = cmds.checkBox("rmbV2_stretch", q=True, v=True)
        build_ik_limb(chain[:3], side="L", part="leg", stretchy=stretchy)


def cb_fkik_arm(*_):
    chain = selected_joints(3)
    if chain:
        stretchy = cmds.checkBox("rmbV2_stretch", q=True, v=True)
        build_fkik_switch(chain[:3], side="L", part="arm", stretchy_ik=stretchy)


def cb_fkik_leg(*_):
    chain = selected_joints(3)
    if chain:
        stretchy = cmds.checkBox("rmbV2_stretch", q=True, v=True)
        build_fkik_switch(chain[:3], side="L", part="leg", stretchy_ik=stretchy)


def cb_spine_fk(*_):
    chain = selected_joints(3)
    if chain:
        build_spine(chain, ik_spline=False)


def cb_spine_ik(*_):
    chain = selected_joints(3)
    if chain:
        build_spine(chain, ik_spline=True)


# --------
# Main UI
# --------

def show_ui():
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)

    cmds.window(WIN, title="Rig Module Builder v2", sizeable=False, widthHeight=(390, 610))
    cmds.columnLayout(adj=True, rs=8)

    cmds.text(l="Rig Module Builder v2", fn="boldLabelFont", h=26)
    cmds.text(l="Select joints first, then click module buttons.")
    cmds.separator(h=8, style="in")

    cmds.checkBox("rmbV2_stretch", l="Enable Stretch for IK/FKIK modules", v=True)

    cmds.frameLayout(l="Arms", cl=False, mw=8, mh=8)
    cmds.rowLayout(nc=3, cw3=(125, 125, 125))
    cmds.button(l="FK Arm", c=cb_fk_arm)
    cmds.button(l="IK Arm", c=cb_ik_arm)
    cmds.button(l="FK/IK Arm", c=cb_fkik_arm)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(l="Legs", cl=False, mw=8, mh=8)
    cmds.rowLayout(nc=3, cw3=(125, 125, 125))
    cmds.button(l="FK Leg", c=cb_fk_leg)
    cmds.button(l="IK Leg", c=cb_ik_leg)
    cmds.button(l="FK/IK Leg", c=cb_fkik_leg)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(l="Spine", cl=False, mw=8, mh=8)
    cmds.rowLayout(nc=2, cw2=(188, 188))
    cmds.button(l="Spine FK", c=cb_spine_fk)
    cmds.button(l="Spine IK Spline", c=cb_spine_ik)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(l="Utilities", cl=False, mw=8, mh=8)
    cmds.button(l="Create Controls For Selection", c=lambda *_: create_ctrls_for_selection())
    cmds.button(l="Mirror Selected Names (L_ ↔ R_)", c=lambda *_: mirror_selected_names())

    cmds.text(l="Control Colors")
    cmds.rowLayout(nc=4, cw4=(95, 95, 95, 95))
    cmds.button(l="Red", c=lambda *_: colorize_selection("red"))
    cmds.button(l="Blue", c=lambda *_: colorize_selection("blue"))
    cmds.button(l="Yellow", c=lambda *_: colorize_selection("yellow"))
    cmds.button(l="Green", c=lambda *_: colorize_selection("green"))
    cmds.setParent("..")

    cmds.rowLayout(nc=4, cw4=(95, 95, 95, 95))
    cmds.button(l="Pink", c=lambda *_: colorize_selection("pink"))
    cmds.button(l="Cyan", c=lambda *_: colorize_selection("cyan"))
    cmds.button(l="White", c=lambda *_: colorize_selection("white"))
    cmds.button(l="Orange", c=lambda *_: colorize_selection("orange"))
    cmds.setParent("..")

    cmds.setParent("..")

    cmds.separator(h=10, style="in")
    cmds.text(l="Includes: IK stretch, FK/IK switching, utility controls, and naming helpers.")
    cmds.text(l="Recommended next upgrade: twist joints + space switching + auto mirror build.")

    cmds.showWindow(WIN)


if __name__ == "__main__":
    show_ui()
