# Runtime components

Xbox-only patch operations use Python's standard library. Keyboard rendering
requires Pillow; the Windows executable includes it.
The Windows executable is built with PyInstaller and includes components of:

- **Python**, Python Software Foundation License:
  https://docs.python.org/3/license.html
- **Tcl/Tk**, Tcl/Tk license terms:
  https://www.tcl-lang.org/software/tcltk/license.html
- **zlib**, zlib license:
  https://zlib.net/zlib_license.html
- **PyInstaller bootloader**, GPL with the PyInstaller exception:
  https://pyinstaller.org/en/stable/license.html

The PyInstaller exception permits distribution of the bundled application
under its own license. Runtime license texts are supplied with the Windows
package under `runtime-licenses/` and embedded in the standalone executable,
accessible through its Licenses button. No game or emulator code is bundled.
`Python-Additional-Notices.txt` includes the bundled Python documentation's
third-party notices, including zlib and libffi. `Tcl-Tk.txt` preserves the
license terms supplied with the installed Tk runtime.


Keyboard artwork uses **Barlow Condensed Bold**, by Jeremy Tribby and
contributors, under the SIL Open Font License 1.1. The original font and license
are bundled in `keyboard-art/font/` and included in the Licenses view.
Source: https://github.com/google/fonts/tree/main/ofl/barlowcondensed

Keyboard rendering uses **Pillow 12.1.0**. Its license and bundled dependency
notices are in `runtime-licenses/Pillow-LICENSE.txt` and the Licenses view.
Source: https://github.com/python-pillow/Pillow
