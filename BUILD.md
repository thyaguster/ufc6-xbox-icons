# Build and verification

The source runs with Python 3.10+; keyboard artwork requires Pillow 12.1.0. Tkinter is needed
for the desktop UI. The Windows v1.1.0 executable was built on Windows x64
with CPython 3.14.2, PyInstaller 6.22.3 and pyinstaller-hooks-contrib 2026.9.

From this directory, with a Windows x64 Python installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt PyInstaller==6.22.3 pyinstaller-hooks-contrib==2026.9
.\.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --exclude-module numpy --exclude-module psutil --exclude-module charset_normalizer --name UFC6-Xbox-Icons --add-data "profiles;profiles" --add-data "LICENSE;." --add-data "THIRD-PARTY-NOTICES.md;." --add-data "runtime-licenses;runtime-licenses" --add-data "keyboard-art;keyboard-art" xbox_icons.py
```

The resulting `dist/UFC6-Xbox-Icons.exe` includes the profile and runtime
license texts. Users can run that file alone; the Licenses button displays
the embedded notices. Keep the source and README available with the release.
If changing the runtime, update its notices. Executable builds are unsigned and are not
claimed to be byte-for-byte reproducible.

## Tests

GitHub Actions builds the single-file Windows executable on pushes and pull
requests, checks the public tests and bundled resources, and uploads a build
artifact. Private game-data integration tests are explicitly skipped in CI.

```powershell
python -m unittest discover -s tests -v
```

Without a private fixture, archive integration tests are explicitly skipped.
To run them, set `UFC6_TEST_GAME` to a **disposable, clean copy** of the supported
game data, with no portable backup already present. The tests deliberately
modify that copy and bypass the running-game check; never use your active game
folder. Do not distribute that fixture or the local backups it creates.

The optional `UFC6_EXPECTED_PACKET` variable points to the maintainer's private
game-tested reference packet for an independent byte comparison. That packet
contains game data and is deliberately excluded from every release.

The original v1.0.x Xbox release passed nine tests: exact reproduction of all 430 verified
edits, title/version rejection, preflight corruption rejection, running-game
refusal, simulated write-failure rollback, install/restore/reinstall, modified
data rejection, backup validation, and path containment. The standalone binary
was also checked against the disposable fixture through its command line,
refused install/restore while UFC 6 was running, and opened and closed its
Tk desktop window successfully.

## Release contents

Only include the public Python source files, launcher, profiles, tests, documentation,
requirements and keyboard font/license,
license files, and (for Windows) the built executable. A gameplay screenshot is
included as `preview.png` for release documentation; it is not patch input.
Exclude caches, development packets, extracted assets, fixtures, local restore
backups, build tools and build intermediates. Publish the ZIPs and their SHA-256
checksums together. The included RELEASE-NOTES.md can serve as the release body.


## Keyboard integration validation

Set `UFC6_KEYBOARD_FIXTURE` to a private, disposable sparse fixture marked with
`.disposable-keyboard-fixture` to run keyboard integration tests. This marker is
required because the tests intentionally patch that fixture. Never point it at
a live game. The maintainer's fixture generator and source bytes are excluded
from the repository and releases.

Keyboard tests cover PORTHEON UTF-16 INI files, empty/default maps, raw and JSON
Kyty maps, script/shortcut parsing without execution, duplicate and modifier
semantics, reserved keys, actual PS5 texture tile addressing, binding-specific
artwork, migration from the legacy Xbox backup, write rollback, binding updates,
style switching, missing-initial-state recovery, unknown modifications, running
game refusal, and consecutive interruptions at state commit and archive writes.

The v1.1 release additionally passed 21 keyboard-specific tests, including
private integration checks, and verified J/I/Q/E prompts visually in-game.
The packaged EXE was tested alone without external profiles or Python.
