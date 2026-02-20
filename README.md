# Maya Rig Tool - Module Builder (v2)

## Files
- `rig_module_builder.py` (v1)
- `rig_module_builder_v2.py` (**recommended**)

## What v2 adds
- Heavily commented code (module-by-module explanations)
- FK modules (arm/leg/spine)
- IK modules (arm/leg) with optional stretch
- FK/IK switch builder for 3-joint limbs
- Spine FK + optional IK Spline
- Control shape library + color presets
- Utility tools (zero groups, naming helper, simple L/R rename mirror)

## Run in Maya
```python
import rig_module_builder_v2 as rmb
rmb.show_ui()
```

## Suggested workflow
1. Select a clean joint chain (3 joints for arm/leg modules).
2. Build FK, IK, or FK/IK module from UI.
3. Color and organize controls.
4. Extend script with your studio conventions (twist chains, spaces, stretch volume preservation, mirror build).

## Notes
- This is a production-ready starting point, not a full autorigger.
- For best results, ensure proper joint orientation and naming before running modules.
