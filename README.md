# Maya Rig Module Builder (v2.1)

This tool is a modular rigging starter for Maya focused on quick FK/IK setup with practical animator controls.

## Included files
- `rig_module_builder.py` (legacy v1)
- `rig_module_builder_v2.py` (**current recommended version**)

## What v2.1 improves
1. **Adaptive control sizing**
   - Control sizes are derived from selected joint lengths.
   - You can tune globally with **Control Size Multiplier** in the UI.

2. **Control orientation toward next joint**
   - FK control zero groups aim toward the next joint in the selected chain.
   - Better control readability on limbs.

3. **Module parent/child awareness**
   - Modules are tagged with metadata in-scene.
   - Child modules can auto-parent under detected parent module when built in order.
   - Root module container: `RMB_MODULES_GRP`.

4. **Commented code**
   - Main sections and core methods are documented so you can extend safely.

---

## How to run
In Maya Script Editor (Python tab):

```python
import rig_module_builder_v2 as rmb
rmb.show_ui()
```

---

## Recommended workflow
1. Build your skeleton with clean orientation.
2. Select joints in order (root → tip).
3. Build modules:
   - Arms: FK / IK / FKIK (3 joints)
   - Legs: FK / IK / FKIK (3 joints)
   - Spine: FK or IK Spline (3+ joints)
4. Adjust control scale with **Control Size Multiplier** if needed.
5. Build parent modules before child modules for cleaner automatic module parenting.

---

## Notes
- FK/IK builder duplicates driver chains and blends them into selected bind joints.
- IK stretch is optional and controlled by the checkbox in UI.
- Leg IK includes starter foot attributes:
  - `footRoll`, `toeTap`, `heelPivot`, `bankIn`, `bankOut`

---

## Next suggested upgrades
- Side auto-detection (L/R/C from names)
- Auto mirror build (left to right)
- Space switching (world/chest/hip/hand)
- Twist joints + volume-preserving stretch
- Better pole-vector placement from plane math
