# Maya Rig Module Builder (v2.2)

## Included
- `rig_module_builder.py` (legacy v1)
- `rig_module_builder_v2.py` (**current recommended version**)

## What’s new in v2.2
- **Adaptive control sizing** from joint lengths + UI multiplier
- **FK aiming** toward next joint in chain
- **Improved pole vector placement** (plane math instead of simple offset)
- **Module hierarchy awareness** (module metadata + auto-parenting)
- **Side auto-detection** from naming (`L_`, `R_`, `left`, `right`)
- **Optional auto-mirror build** for opposite side (when mirrored chain names exist)

## Run in Maya
```python
import rig_module_builder_v2 as rmb
rmb.show_ui()
```

## Basic workflow
1. Select joints in order (root → tip).
2. Choose module button (FK / IK / FKIK / Spine).
3. Adjust **Control Size Multiplier** if controls feel too small/large.
4. Enable **Auto Mirror Build** if your opposite chain naming is consistent.
5. Build parent modules first for cleaner hierarchy parenting.

## Naming tips for mirror support
Use one of these patterns:
- `L_arm_shoulder_jnt` ↔ `R_arm_shoulder_jnt`
- `arm_L_shoulder_jnt` ↔ `arm_R_shoulder_jnt`
- `leftArm_shoulder_jnt` ↔ `rightArm_shoulder_jnt`

Use the UI button **Check mirrored chain for current selection** to validate quickly.

## Notes
- FK/IK modules expect a 3-joint limb selection.
- Spine expects 3+ joints.
- IK leg includes starter attrs: `footRoll`, `toeTap`, `heelPivot`, `bankIn`, `bankOut`.

## Next upgrades
- Side override dropdown in UI
- Space switching (world/chest/hip/hand)
- True mirrored orientation solver for edge naming cases
- Twist joints + volume-preserving stretch
