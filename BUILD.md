# Build and verification

The source runs with Python 3.10+ and its standard library. Tkinter is needed
for the desktop UI. The Windows v1.0.1 executable was built on Windows x64
with CPython 3.14.2, PyInstaller 6.22.3 and pyinstaller-hooks-contrib 2026.9.

From this directory, with a Windows x64 Python installation:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install PyInstaller==6.22.3 pyinstaller-hooks-contrib==2026.9
.\.venv\Scripts\python -m PyInstaller --noconfirm --clean --onefile --windowed --name UFC6-Xbox-Icons --add-data "profiles;profiles" --add-data "LICENSE;." --add-data "THIRD-PARTY-NOTICES.md;." --add-data "runtime-licenses;runtime-licenses" xbox_icons.py
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

Release validation passed nine tests: exact reproduction of all 430 verified
edits, title/version rejection, preflight corruption rejection, running-game
refusal, simulated write-failure rollback, install/restore/reinstall, modified
data rejection, backup validation, and path containment. The standalone binary
was also checked against the disposable fixture through its command line,
refused install/restore while UFC 6 was running, and opened and closed its
Tk desktop window successfully.

## Release contents

Only include the two Python source files, launcher, profile, tests, documentation,
license files, and (for Windows) the built executable. A gameplay screenshot is
included as `preview.png` for release documentation; it is not patch input.
Exclude caches, development packets, extracted assets, fixtures, local restore
backups, build tools and build intermediates. Publish the ZIPs and their SHA-256
checksums together. The included RELEASE-NOTES.md can serve as the release body.
