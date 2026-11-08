# Runtime components

The Python source patcher has no dependencies outside Python's standard library.
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
