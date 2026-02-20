# Maya Rig Module Builder (v2.3)

## Included
- `rig_module_builder.py` (legacy v1)
- `rig_module_builder_v2.py` (**current recommended version**)

## What’s new in v2.3
- **Side override mode in UI** (`Auto / L / R / C`)
- **More intuitive in-tool instructions** (Quick Start panel)
- **Status feedback line** (shows what module was just built)
- Keeps v2.2 upgrades:
  - adaptive control sizing
  - FK aiming toward next joint
  - improved pole vector plane math
  - module hierarchy awareness
  - side auto-detection + auto-mirror option

## Run in Maya
```python
import rig_module_builder_v2 as rmb
rmb.show_ui()
```

## Recommended workflow
1. Select joints in order (root → tip).
2. Choose **Side Mode**:
   - `Auto` (detect from naming)
   - `L` / `R` / `C` to force side manually
3. Pick module button:
   - Arms: FK / IK / FKIK (3 joints)
   - Legs: FK / IK / FKIK (3 joints)
   - Spine: FK or IK Spline (3+ joints)
4. Optional: enable **Auto Mirror Build**.
5. Tune **Control Size Multiplier** if needed.
6. Watch **Status** text at bottom for confirmation.

## Naming tips for mirror support
Preferred patterns:
- `L_arm_shoulder_jnt` ↔ `R_arm_shoulder_jnt`
- `arm_L_shoulder_jnt` ↔ `arm_R_shoulder_jnt`
- `leftArm_shoulder_jnt` ↔ `rightArm_shoulder_jnt`

Use button: **Check mirrored chain for current selection**.

## Notes
- FK/IK expects 3-joint limb selection.
- Spine expects 3+ joints.
- Leg IK includes starter attrs: `footRoll`, `toeTap`, `heelPivot`, `bankIn`, `bankOut`.
