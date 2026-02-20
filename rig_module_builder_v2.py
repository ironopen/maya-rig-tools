"""
Rig Module Builder v2.2 (Maya)
------------------------------
Upgrades in this version:
1) Adaptive control sizing based on joint lengths (+ global size multiplier in UI)
2) FK controls orient toward the next joint in chain when possible
3) Basic parent/child module awareness via module metadata + automatic parenting
4) Better pole-vector placement using plane math
5) Side auto-detection (L/R/C) + optional auto-mirror build
6) Clear comments for learning and extension

Run:
    import rig_module_builder_v2 as rmb
    rmb.show_ui()
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om

WIN = "rigModuleBuilderV2Win"
ROOT_GRP = "RMB_MODULES_GRP"

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

SIDE_COLOR = {"L": "blue", "R": "red", "C": "yellow"}


# -----------------------------
# Scene/module metadata helpers
# -----------------------------

def ensure_root_group():
    if not cmds.objExists(ROOT_GRP):
        cmds.group(em=True, n=ROOT_GRP)
    return ROOT_GRP


def add_str_attr(node, attr, value=""):
    if not cmds.objExists(node):
        return
    if not cmds.attributeQuery(attr, n=node, exists=True):
        cmds.addAttr(node, ln=attr, dt="string")
    cmds.setAttr(f"{node}.{attr}", value, type="string")


def get_str_attr(node, attr):
    if not cmds.objExists(node):
        return ""
    if not cmds.attributeQuery(attr, n=node, exists=True):
        return ""
    try:
        return cmds.getAttr(f"{node}.{attr}") or ""
    except Exception:
        return ""


def tag_chain_module(chain, module_id):
    """Tag each joint in a chain with module id for parent/child discovery."""
    for j in chain:
        if cmds.objExists(j):
            add_str_attr(j, "rmb_module_id", module_id)


def infer_parent_module_from_chain(chain):
    """
    Parent module detection:
    - Check parent joint of root joint
    - If parent joint has rmb_module_id, use that as parent module
    """
    if not chain:
        return ""
    root = chain[0]
    parent = cmds.listRelatives(root, p=True, type="joint") or []
    if not parent:
        return ""
    return get_str_attr(parent[0], "rmb_module_id")


def find_module_group(module_id):
    all_transforms = cmds.ls(type="transform") or []
    for n in all_transforms:
        if get_str_attr(n, "rmb_module_id") == module_id:
            return n
    return ""


# -----------------
# General utilities
# -----------------

def safe_parent(child, parent):
    if cmds.objExists(child) and cmds.objExists(parent):
        try:
            cmds.parent(child, parent)
        except Exception:
            pass


def align_matrix(source, target):
    if not cmds.objExists(source) or not cmds.objExists(target):
        return
    m = cmds.xform(source, q=True, ws=True, m=True)
    cmds.xform(target, ws=True, m=m)


def make_zero(node):
    if not cmds.objExists(node):
        return None
    z = cmds.group(em=True, n=f"{node}_ZRO")
    align_matrix(node, z)
    p = cmds.listRelatives(node, p=True) or []
    if p:
        safe_parent(z, p[0])
    safe_parent(node, z)
    return z


def set_ctrl_color(ctrl, color):
    idx = COLOR_INDEX.get(color.lower(), 17)
    for s in (cmds.listRelatives(ctrl, s=True, ni=True) or []):
        cmds.setAttr(f"{s}.overrideEnabled", 1)
        cmds.setAttr(f"{s}.overrideColor", idx)


def joint_length_to_child(joint):
    """Get distance from joint to first child joint; fallback to tx magnitude."""
    kids = cmds.listRelatives(joint, c=True, type="joint") or []
    if kids:
        a = cmds.xform(joint, q=True, ws=True, t=True)
        b = cmds.xform(kids[0], q=True, ws=True, t=True)
        return ((b[0]-a[0])**2 + (b[1]-a[1])**2 + (b[2]-a[2])**2) ** 0.5
    try:
        return abs(cmds.getAttr(f"{joint}.tx"))
    except Exception:
        return 1.0


def chain_avg_length(chain):
    vals = [joint_length_to_child(j) for j in chain]
    vals = [v for v in vals if v > 0.0001]
    return sum(vals)/len(vals) if vals else 1.0


def adaptive_size(chain, factor=0.45, min_size=0.2, max_size=8.0):
    mul = 1.0
    if cmds.floatSliderGrp("rmb_sizeMul", exists=True):
        mul = cmds.floatSliderGrp("rmb_sizeMul", q=True, v=True)
    s = chain_avg_length(chain) * factor * mul
    return max(min_size, min(max_size, s))


def detect_side_from_chain(chain):
    """Infer side from joint names. Defaults to C if unknown."""
    text = " ".join(chain).lower()
    if "l_" in text or "_l" in text or "left" in text:
        return "L"
    if "r_" in text or "_r" in text or "right" in text:
        return "R"
    return "C"


def opposite_side(side):
    if side == "L":
        return "R"
    if side == "R":
        return "L"
    return "C"


def mirrored_name(name):
    swaps = [("L_", "R_"), ("_L", "_R"), ("left", "right"), ("Left", "Right")]
    for a, b in swaps:
        if a in name:
            return name.replace(a, b)
    swaps_rev = [("R_", "L_"), ("_R", "_L"), ("right", "left"), ("Right", "Left")]
    for a, b in swaps_rev:
        if a in name:
            return name.replace(a, b)
    return ""


def mirrored_chain_by_name(chain):
    out = []
    for j in chain:
        candidate = mirrored_name(j)
        if not candidate or not cmds.objExists(candidate):
            return []
        out.append(candidate)
    return out


def _v(pos):
    return om.MVector(pos[0], pos[1], pos[2])


def compute_pv_position(upper, mid, lower, distance_scale=1.5):
    """Plane-based pole vector position from 3-joint limb."""
    p0 = _v(cmds.xform(upper, q=True, ws=True, t=True))
    p1 = _v(cmds.xform(mid, q=True, ws=True, t=True))
    p2 = _v(cmds.xform(lower, q=True, ws=True, t=True))

    line = p2 - p0
    line_len = max(line.length(), 0.001)
    line_dir = line / line_len

    proj_len = (p1 - p0) * line_dir
    proj = p0 + line_dir * proj_len
    arrow = p1 - proj

    if arrow.length() < 0.001:
        # fallback if chain is perfectly straight
        arrow = om.MVector(0, 0, 1)

    dist = max((p1 - p0).length(), (p2 - p1).length()) * distance_scale
    pv = p1 + arrow.normal() * dist
    return [pv.x, pv.y, pv.z]


# ----------------
# Control creation
# ----------------

def create_ctrl(name, shape="circle", size=1.0, axis="x", color="yellow"):
    shape = shape.lower()

    if shape == "circle":
        nr = (1, 0, 0) if axis == "x" else (0, 1, 0) if axis == "y" else (0, 0, 1)
        ctrl = cmds.circle(n=name, nr=nr, r=size, ch=False)[0]

    elif shape == "square":
        pts = [(-1,0,-1),(-1,0,1),(1,0,1),(1,0,-1),(-1,0,-1)]
        ctrl = cmds.curve(n=name, d=1, p=pts)
        cmds.scale(size, size, size, ctrl, r=True)

    elif shape == "cube":
        pts = [(-1,-1,-1),(1,-1,-1),(1,-1,1),(-1,-1,1),(-1,-1,-1),(-1,1,-1),(1,1,-1),(1,-1,-1),(1,1,-1),(1,1,1),(1,-1,1),(1,1,1),(-1,1,1),(-1,-1,1),(-1,1,1),(-1,1,-1)]
        ctrl = cmds.curve(n=name, d=1, p=pts)
        cmds.scale(size, size, size, ctrl, r=True)

    elif shape == "arrow":
        pts = [(-1,0,0),(0.2,0,0),(0.2,0,0.4),(1,0,0),(0.2,0,-0.4),(0.2,0,0),(-1,0,0)]
        ctrl = cmds.curve(n=name, d=1, p=pts)
        cmds.scale(size, size, size, ctrl, r=True)

    else:  # diamond fallback
        pts = [(0,1,0),(1,0,0),(0,-1,0),(-1,0,0),(0,1,0),(0,0,1),(1,0,0),(0,0,-1),(-1,0,0),(0,0,1)]
        ctrl = cmds.curve(n=name, d=1, p=pts)
        cmds.scale(size, size, size, ctrl, r=True)

    set_ctrl_color(ctrl, color)
    return ctrl


def orient_zro_to_next_joint(zro, current_joint, next_joint):
    """
    Aim the control zero group X-axis toward the next joint.
    This improves readability and animator experience on limbs.
    """
    if not (cmds.objExists(zro) and cmds.objExists(current_joint) and cmds.objExists(next_joint)):
        return False
    try:
        con = cmds.aimConstraint(next_joint, zro, aim=(1,0,0), u=(0,1,0), wut="scene")[0]
        cmds.delete(con)
        # keep translate at current joint
        t = cmds.xform(current_joint, q=True, ws=True, t=True)
        cmds.xform(zro, ws=True, t=t)
        return True
    except Exception:
        return False


# ------------
# FK builder
# ------------

def build_fk(chain, side="L", part="arm"):
    color = SIDE_COLOR.get(side, "yellow")
    size = adaptive_size(chain, factor=0.45)
    ctrls = []
    prev = None

    module_id = f"{side}_{part}_FK"

    for i, j in enumerate(chain):
        ctrl = create_ctrl(f"{j}_FK_CTRL", shape="circle", size=size, axis="x", color=color)
        zro = make_zero(ctrl)

        # position/orient zro
        next_joint = chain[i+1] if i+1 < len(chain) else None
        aimed = False
        if next_joint:
            t = cmds.xform(j, q=True, ws=True, t=True)
            cmds.xform(zro, ws=True, t=t)
            aimed = orient_zro_to_next_joint(zro, j, next_joint)
        if not aimed:
            align_matrix(j, zro)

        cmds.parentConstraint(ctrl, j, mo=True)

        if prev:
            safe_parent(zro, prev)
        prev = ctrl
        ctrls.append(ctrl)

    root_zro = f"{ctrls[0]}_ZRO"
    module_grp = cmds.group(root_zro, n=f"{module_id}_GRP")
    add_str_attr(module_grp, "rmb_module_id", module_id)
    add_str_attr(module_grp, "rmb_module_type", "FK")

    # parent-child module awareness
    ensure_root_group()
    parent_module_id = infer_parent_module_from_chain(chain)
    add_str_attr(module_grp, "rmb_parent_module", parent_module_id)
    if parent_module_id:
        pgrp = find_module_group(parent_module_id)
        if pgrp:
            safe_parent(module_grp, pgrp)
        else:
            safe_parent(module_grp, ROOT_GRP)
    else:
        safe_parent(module_grp, ROOT_GRP)

    tag_chain_module(chain, module_id)

    return {"ctrls": ctrls, "group": module_grp, "module_id": module_id}


# ------------
# IK builder
# ------------

def _make_distance(node_a, node_b, name):
    pa = cmds.xform(node_a, q=True, ws=True, t=True)
    pb = cmds.xform(node_b, q=True, ws=True, t=True)
    shape = cmds.distanceDimension(sp=pa, ep=pb)
    tr = cmds.listRelatives(shape, p=True)[0]
    tr = cmds.rename(tr, name)
    locs = cmds.listConnections(shape, type="locator") or []
    a = cmds.listRelatives(locs[0], p=True)[0]
    b = cmds.listRelatives(locs[1], p=True)[0]
    return shape, a, b


def add_stretch(chain, ik_ctrl, prefix):
    if len(chain) < 3:
        return
    j0, j1, j2 = chain[:3]
    len1 = abs(cmds.getAttr(f"{j1}.tx"))
    len2 = abs(cmds.getAttr(f"{j2}.tx"))
    original = max(0.001, len1 + len2)

    dist_shape, loc_a, loc_b = _make_distance(j0, ik_ctrl, f"{prefix}_DIST")
    safe_parent(loc_a, j0)
    safe_parent(loc_b, ik_ctrl)

    md = cmds.createNode("multiplyDivide", n=f"{prefix}_stretch_MD")
    cond = cmds.createNode("condition", n=f"{prefix}_stretch_COND")

    cmds.setAttr(f"{md}.operation", 2)
    cmds.setAttr(f"{md}.input2X", original)
    cmds.connectAttr(f"{dist_shape}.distance", f"{md}.input1X", f=True)

    cmds.setAttr(f"{cond}.operation", 2)
    cmds.setAttr(f"{cond}.secondTerm", original)
    cmds.setAttr(f"{cond}.colorIfFalseR", 1.0)
    cmds.connectAttr(f"{dist_shape}.distance", f"{cond}.firstTerm", f=True)
    cmds.connectAttr(f"{md}.outputX", f"{cond}.colorIfTrueR", f=True)

    cmds.connectAttr(f"{cond}.outColorR", f"{j0}.scaleX", f=True)
    cmds.connectAttr(f"{cond}.outColorR", f"{j1}.scaleX", f=True)


def build_ik(chain, side="L", part="arm", stretchy=True):
    if len(chain) < 3:
        cmds.warning("Need 3 joints selected for IK limb.")
        return {}

    color = SIDE_COLOR.get(side, "blue")
    size = adaptive_size(chain, factor=0.5)

    upper, mid, lower = chain[:3]
    ikh, _ = cmds.ikHandle(sj=upper, ee=lower, sol="ikRPsolver", n=f"{side}_{part}_IK_HDL")

    ik_ctrl = create_ctrl(f"{side}_{part}_IK_CTRL", shape="cube", size=size, color=color)
    ik_z = make_zero(ik_ctrl)
    align_matrix(lower, ik_z)
    safe_parent(ikh, ik_ctrl)

    pv = create_ctrl(f"{side}_{part}_PV_CTRL", shape="arrow", size=size*0.7, color=color)
    pv_z = make_zero(pv)
    pv_pos = compute_pv_position(upper, mid, lower, distance_scale=1.6)
    cmds.xform(pv_z, ws=True, t=pv_pos)
    cmds.poleVectorConstraint(pv, ikh)

    module_id = f"{side}_{part}_IK"
    grp = cmds.group([ik_z, pv_z], n=f"{module_id}_GRP")
    add_str_attr(grp, "rmb_module_id", module_id)
    add_str_attr(grp, "rmb_module_type", "IK")

    ensure_root_group()
    parent_module_id = infer_parent_module_from_chain(chain)
    add_str_attr(grp, "rmb_parent_module", parent_module_id)
    if parent_module_id:
        pgrp = find_module_group(parent_module_id)
        if pgrp:
            safe_parent(grp, pgrp)
        else:
            safe_parent(grp, ROOT_GRP)
    else:
        safe_parent(grp, ROOT_GRP)

    if part == "leg":
        for attr in ["footRoll", "toeTap", "heelPivot", "bankIn", "bankOut"]:
            if not cmds.attributeQuery(attr, n=ik_ctrl, exists=True):
                cmds.addAttr(ik_ctrl, ln=attr, at="double", k=True)

    if stretchy:
        add_stretch(chain, ik_ctrl, f"{side}_{part}")

    tag_chain_module(chain, module_id)
    return {"ikCtrl": ik_ctrl, "pvCtrl": pv, "ikHandle": ikh, "group": grp, "module_id": module_id}


# -------------------
# FK/IK switch module
# -------------------

def dup_chain(chain, suffix):
    out = []
    for j in chain:
        out.append(cmds.duplicate(j, po=True, n=f"{j}_{suffix}")[0])
    for i in range(1, len(out)):
        safe_parent(out[i], out[i-1])
    return out


def build_fkik(chain, side="L", part="arm", stretchy=True):
    if len(chain) < 3:
        cmds.warning("Need 3 joints selected for FK/IK module.")
        return {}

    bind = chain[:3]
    fk_chain = dup_chain(bind, "FKDRV")
    ik_chain = dup_chain(bind, "IKDRV")

    fk = build_fk(fk_chain, side=side, part=f"{part}FK")
    ik = build_ik(ik_chain, side=side, part=f"{part}IK", stretchy=stretchy)

    settings_size = adaptive_size(bind, factor=0.35)
    settings = create_ctrl(f"{side}_{part}_SETTINGS_CTRL", shape="square", size=settings_size, color="white")
    settings_z = make_zero(settings)
    align_matrix(bind[-1], settings_z)
    pos = cmds.xform(settings_z, q=True, ws=True, t=True)
    cmds.xform(settings_z, ws=True, t=(pos[0], pos[1] - settings_size * 3, pos[2]))

    if not cmds.attributeQuery("fkIk", n=settings, exists=True):
        cmds.addAttr(settings, ln="fkIk", at="double", min=0, max=1, dv=0, k=True)

    rev = cmds.createNode("reverse", n=f"{side}_{part}_fkik_REV")
    cmds.connectAttr(f"{settings}.fkIk", f"{rev}.inputX", f=True)

    for i, bj in enumerate(bind):
        pc = cmds.parentConstraint(fk_chain[i], ik_chain[i], bj, mo=False, n=f"{bj}_fkik_PC")[0]
        w = cmds.parentConstraint(pc, q=True, wal=True)
        if len(w) >= 2:
            cmds.connectAttr(f"{rev}.outputX", f"{pc}.{w[0]}", f=True)
            cmds.connectAttr(f"{settings}.fkIk", f"{pc}.{w[1]}", f=True)

    fk_root = fk.get("group")
    ik_root = ik.get("group")
    if fk_root and ik_root:
        try:
            cmds.connectAttr(f"{rev}.outputX", f"{fk_root}.visibility", f=True)
            cmds.connectAttr(f"{settings}.fkIk", f"{ik_root}.visibility", f=True)
        except Exception:
            pass

    module_id = f"{side}_{part}_FKIK"
    mod_grp = cmds.group([fk_root, ik_root, settings_z], n=f"{module_id}_GRP")
    add_str_attr(mod_grp, "rmb_module_id", module_id)
    add_str_attr(mod_grp, "rmb_module_type", "FKIK")

    ensure_root_group()
    parent_module_id = infer_parent_module_from_chain(bind)
    add_str_attr(mod_grp, "rmb_parent_module", parent_module_id)
    if parent_module_id:
        pgrp = find_module_group(parent_module_id)
        if pgrp:
            safe_parent(mod_grp, pgrp)
        else:
            safe_parent(mod_grp, ROOT_GRP)
    else:
        safe_parent(mod_grp, ROOT_GRP)

    tag_chain_module(bind, module_id)
    return {"group": mod_grp, "settings": settings, "module_id": module_id}


# -------
# Spine
# -------

def build_spine(chain, ik_spline=False):
    fk = build_fk(chain, side="C", part="spine")
    out = {"fk": fk}

    if ik_spline and len(chain) >= 3:
        ikh, curve = cmds.ikHandle(sj=chain[0], ee=chain[-1], sol="ikSplineSolver", ccv=False, pcv=False, n="C_spine_IK_HDL")
        s = adaptive_size(chain, factor=0.6)
        start = create_ctrl("C_spineStart_IK_CTRL", shape="circle", size=s, axis="y", color="yellow")
        end = create_ctrl("C_spineEnd_IK_CTRL", shape="circle", size=s, axis="y", color="yellow")
        out.update({"ikHandle": ikh, "curve": curve, "start": start, "end": end})

    return out


# -------------
# UI callbacks
# -------------

def _sel3():
    s = cmds.ls(sl=True, type="joint") or []
    if len(s) < 3:
        cmds.warning("Select at least 3 joints.")
        return []
    return s


def _auto_mirror_enabled():
    return cmds.checkBox("rmb_autoMirror", exists=True) and cmds.checkBox("rmb_autoMirror", q=True, v=True)


def cb_fk_arm(*_):
    s = _sel3()
    if s:
        side = detect_side_from_chain(s[:3])
        build_fk(s[:3], side=side, part="arm")
        if _auto_mirror_enabled() and side in ("L", "R"):
            m = mirrored_chain_by_name(s[:3])
            if m:
                build_fk(m, side=opposite_side(side), part="arm")


def cb_ik_arm(*_):
    s = _sel3()
    if s:
        side = detect_side_from_chain(s[:3])
        st = cmds.checkBox("rmb_stretch", q=True, v=True)
        build_ik(s[:3], side=side, part="arm", stretchy=st)
        if _auto_mirror_enabled() and side in ("L", "R"):
            m = mirrored_chain_by_name(s[:3])
            if m:
                build_ik(m, side=opposite_side(side), part="arm", stretchy=st)


def cb_fkik_arm(*_):
    s = _sel3()
    if s:
        side = detect_side_from_chain(s[:3])
        st = cmds.checkBox("rmb_stretch", q=True, v=True)
        build_fkik(s[:3], side=side, part="arm", stretchy=st)
        if _auto_mirror_enabled() and side in ("L", "R"):
            m = mirrored_chain_by_name(s[:3])
            if m:
                build_fkik(m, side=opposite_side(side), part="arm", stretchy=st)


def cb_fk_leg(*_):
    s = _sel3()
    if s:
        side = detect_side_from_chain(s[:3])
        build_fk(s[:3], side=side, part="leg")
        if _auto_mirror_enabled() and side in ("L", "R"):
            m = mirrored_chain_by_name(s[:3])
            if m:
                build_fk(m, side=opposite_side(side), part="leg")


def cb_ik_leg(*_):
    s = _sel3()
    if s:
        side = detect_side_from_chain(s[:3])
        st = cmds.checkBox("rmb_stretch", q=True, v=True)
        build_ik(s[:3], side=side, part="leg", stretchy=st)
        if _auto_mirror_enabled() and side in ("L", "R"):
            m = mirrored_chain_by_name(s[:3])
            if m:
                build_ik(m, side=opposite_side(side), part="leg", stretchy=st)


def cb_fkik_leg(*_):
    s = _sel3()
    if s:
        side = detect_side_from_chain(s[:3])
        st = cmds.checkBox("rmb_stretch", q=True, v=True)
        build_fkik(s[:3], side=side, part="leg", stretchy=st)
        if _auto_mirror_enabled() and side in ("L", "R"):
            m = mirrored_chain_by_name(s[:3])
            if m:
                build_fkik(m, side=opposite_side(side), part="leg", stretchy=st)


def cb_spine_fk(*_):
    s = cmds.ls(sl=True, type="joint") or []
    if len(s) < 3:
        cmds.warning("Select 3+ spine joints.")
        return
    build_spine(s, ik_spline=False)


def cb_spine_ik(*_):
    s = cmds.ls(sl=True, type="joint") or []
    if len(s) < 3:
        cmds.warning("Select 3+ spine joints.")
        return
    build_spine(s, ik_spline=True)


def cb_color(color):
    sel = cmds.ls(sl=True) or []
    for n in sel:
        set_ctrl_color(n, color)


def cb_mirror_name_hint(*_):
    s = _sel3()
    if not s:
        return
    m = mirrored_chain_by_name(s[:3])
    if m:
        cmds.inViewMessage(amg=f"Mirror chain found: <hl>{', '.join(m)}</hl>", pos='midCenterTop', fade=True)
    else:
        cmds.warning("Could not resolve mirrored chain by naming. Use L_/R_ or left/right naming.")


# -----
# UI
# -----

def show_ui():
    if cmds.window(WIN, exists=True):
        cmds.deleteUI(WIN)

    cmds.window(WIN, title="Rig Module Builder v2.2", sizeable=False, widthHeight=(400, 680))
    cmds.columnLayout(adj=True, rs=8)

    cmds.text(l="Rig Module Builder v2.2", fn="boldLabelFont", h=24)
    cmds.text(l="Adaptive size + aiming + hierarchy + side detect + auto mirror")
    cmds.separator(h=8, style="in")

    cmds.floatSliderGrp("rmb_sizeMul", l="Control Size Multiplier", field=True, min=0.2, max=3.0, v=1.0)
    cmds.checkBox("rmb_stretch", l="Enable Stretch for IK/FKIK", v=True)
    cmds.checkBox("rmb_autoMirror", l="Auto Mirror Build (requires mirrored L/R chain names)", v=False)
    cmds.button(l="Check mirrored chain for current selection", c=cb_mirror_name_hint)

    cmds.frameLayout(l="Arms", cl=False, mw=8, mh=8)
    cmds.rowLayout(nc=3, cw3=(130, 130, 130))
    cmds.button(l="FK Arm", c=cb_fk_arm)
    cmds.button(l="IK Arm", c=cb_ik_arm)
    cmds.button(l="FK/IK Arm", c=cb_fkik_arm)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(l="Legs", cl=False, mw=8, mh=8)
    cmds.rowLayout(nc=3, cw3=(130, 130, 130))
    cmds.button(l="FK Leg", c=cb_fk_leg)
    cmds.button(l="IK Leg", c=cb_ik_leg)
    cmds.button(l="FK/IK Leg", c=cb_fkik_leg)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(l="Spine", cl=False, mw=8, mh=8)
    cmds.rowLayout(nc=2, cw2=(195, 195))
    cmds.button(l="Spine FK", c=cb_spine_fk)
    cmds.button(l="Spine IK Spline", c=cb_spine_ik)
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.frameLayout(l="Color Utilities", cl=False, mw=8, mh=8)
    cmds.rowLayout(nc=4, cw4=(98,98,98,98))
    cmds.button(l="Red", c=lambda *_: cb_color("red"))
    cmds.button(l="Blue", c=lambda *_: cb_color("blue"))
    cmds.button(l="Yellow", c=lambda *_: cb_color("yellow"))
    cmds.button(l="Green", c=lambda *_: cb_color("green"))
    cmds.setParent("..")
    cmds.rowLayout(nc=4, cw4=(98,98,98,98))
    cmds.button(l="Pink", c=lambda *_: cb_color("pink"))
    cmds.button(l="Cyan", c=lambda *_: cb_color("cyan"))
    cmds.button(l="White", c=lambda *_: cb_color("white"))
    cmds.button(l="Orange", c=lambda *_: cb_color("orange"))
    cmds.setParent("..")
    cmds.setParent("..")

    cmds.separator(h=10, style="in")
    cmds.text(l="Tip: Build parent module first, then child module for clean module parenting.")

    cmds.showWindow(WIN)


if __name__ == "__main__":
    show_ui()
