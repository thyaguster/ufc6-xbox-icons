# UFC 6 Controller Icons v1.1.0

Adds keyboard/mouse icon installation and controller button remapping alongside Xbox and original PlayStation.
Supports **PPSA23566**.

- Visual button-icon selector cards (**PlayStation**, **Xbox**, **Keyboard & Mouse**) and separate Controller & Keyboard Layout Editor window.
- Remap controller (`Pad:`) or keyboard/mouse bindings (including one-click **Swap A↔B / ✕↔○** and **Swap X↔Y / □↔△** presets).
- Load PORTHEON's UFC6.ini, standalone Kyty keymap JSON, launch scripts or shortcuts.
- Review/edit bindings, preview labels, export settings or copy a Kyty argument.
- Original flat monochrome keycaps generated from the selected bindings.
- Keyboard mode generates 328 texture prompts and 110 Flash bitmaps while
  preserving ActionScript, sprite placements, file sizes and input code.
- Switch between keyboard, Xbox and original icons without losing originals.
- Imports verified v1.0.x Xbox restore backups automatically.
- Unified backup and a durable state journal support interrupted-write recovery.

The EXE includes Pillow, the open font, profiles and notices. Source users need
Python 3.10+, Tkinter and `python -m pip install -r requirements.txt`.

Imports never modify launcher settings. If you edit bindings here, use the
matching exported --keymap argument in standalone Kyty. After changing launcher
bindings, reinstall keyboard icons. Prompts do not switch automatically when a
controller is used. Older Xbox-only tools should be used only after switching
back to Xbox or original icons with this release.

Close UFC 6 before installing/restoring and retain both local unified backup
files. No extracted game assets or executables are included in the release.

Verified in-game: J Select/Cancel, I Restart/Simulate, Q/E tabs, and Ctrl.
No week was advanced and no fight was started during the visual checks.
