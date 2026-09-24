# DATEV Mock — standalone .exe release via GitHub Actions

## Objective

User request (2026-09-24): create a git tag, a GitHub Release carrying a
standalone Windows `.exe` build of the mock server, via a GitHub Actions
workflow — plus, separately, find and fix the root cause of a recurring
stray file named `3.9)` appearing in the repo root, and commit the
in-progress work (the `scripts/install.sh` / `scripts/install.bat`
one-line installers and README section from the prior turn).

## `3.9)` stray file — root cause (found and fixed, not part of the .exe work)

Reproduced directly against real `cmd.exe` (not a shell/MSYS artifact):
`start.bat` line 20 was an **unquoted, unescaped** batch `echo`:
```
echo [1/5] Checking for a usable system Python (>= 3.9)...
```
`cmd.exe` treats a bare `>` as an output-redirection operator anywhere on
the line, including inside unescaped `echo` text — it is not specific to
being inside an `if`/`for` block. So every run of `start.bat` redirected
part of that echo's own text into a new file, truncating the printed
message and leaving the junk file behind. Confirmed with an isolated
`.bat` repro run through real `cmd.exe` (not bash): the unescaped line
reproduces the exact byte-for-byte stray file content seen in the repo
(`[1/5] Checking for a usable system Python (` + CRLF); escaping the
redirection-sensitive characters (`^>`, plus `^(`/`^)` for consistency
with the project's existing escaping convention two lines below) removes
the stray file and prints the full message correctly. Fixed in `start.bat`
line 20 (`^(^>= 3.9^)`), grepped the rest of the file for the same pattern
(only that one line matched). No other script had this bug — `start.sh`'s
equivalent line is fully double-quoted, safe in bash.

## Architecture decisions — packaging as a standalone .exe

1. **PyInstaller, one-file mode**, run in a `windows-latest` GitHub Actions
   job — matches "a release of an .exe" (single downloadable artifact, no
   Python required on the target machine), consistent with this project's
   existing zero-prerequisites philosophy for `start.bat`/`start.sh`.
2. **New frozen-aware base-path helper.** `app/config.py`'s
   `SETTINGS_PATH`, `app/db.py`'s `DB_PATH`, and `certs/generate_cert.py`'s
   `CERTS_DIR` all currently derive their location from
   `Path(__file__).resolve().parent[.parent]` — correct for `python -m
   uvicorn app.main:app` from a source checkout, but **wrong for a
   PyInstaller one-file exe**: `__file__` for a frozen module resolves
   inside the transient `sys._MEIPASS` extraction directory, which is
   wiped after every run. Without a fix, `settings.json` and
   `datev_mock.db` (the entire point of the SQLite persistence epic) would
   silently reset on every launch of the exe. Fix: a new
   `app/runtime_paths.py` with a single `base_dir()` helper — returns
   `Path(sys.executable).resolve().parent` when `sys.frozen` is set
   (PyInstaller sets this), else the existing source-checkout-relative
   logic unchanged. `config.py`, `db.py`, and `generate_cert.py` all switch
   to this helper for their base directory, keeping every existing
   relative sub-path (`settings.json`, `datev_mock.db`, `certs/`)
   unchanged — a pure path-resolution fix, no behavior change when run
   from source (verified: `sys.frozen` is never set outside a PyInstaller
   build, so the source-checkout code path is untouched).
3. **New launcher entry point**, `scripts/run_server.py` — the PyInstaller
   target script. Ensures the TLS cert exists (calls
   `certs.generate_cert.generate_self_signed_cert()` directly rather than
   shelling out to it as this project's `start.sh`/`start.bat` do, since a
   frozen exe has no separate `python` interpreter to shell out to), then
   calls `uvicorn.run("app.main:app", host="127.0.0.1", port=58452,
   ssl_keyfile=..., ssl_certfile=...)` in-process. Mirrors
   `start.sh`/`start.bat`'s final step exactly (same host/port/cert
   behavior), minus the Python-bootstrap steps that don't apply to an
   already-frozen exe.
4. **GitHub Actions workflow**, `.github/workflows/release.yml` — triggers
   on pushing a tag matching `v*.*.*`. Runs on `windows-latest`: checks out
   the repo, sets up Python, installs `requirements.txt` +
   `pyinstaller`, runs PyInstaller against `scripts/run_server.py`
   (`--onefile --name datev-mock`), then publishes a GitHub Release for
   that tag with the resulting `dist/datev-mock.exe` attached (via
   `softprops/action-gh-release`, pinned to a commit SHA, or the
   equivalent `gh release create` CLI call — decide during implementation
   based on which keeps the workflow simplest and avoids adding an
   unpinned third-party action).
5. **First tag: `v0.1.0`.** No prior tags exist in this repository — a
   reasonable, conventional starting point for a first tagged release
   under semver.

## Phases

- [x] P1 — `3.9)` root cause found, reproduced against real `cmd.exe`,
      fixed in `start.bat`, stray file removed from the repo root.
- [ ] P2 — Frozen-aware path helper (`app/runtime_paths.py`) +
      `config.py`/`db.py`/`certs/generate_cert.py` updated to use it.
      Existing test suite must still pass unchanged (pure refactor, no
      behavior change from source).
- [ ] P3 — `scripts/run_server.py` launcher entry point. Local PyInstaller
      build on this machine (real Windows) to verify the resulting `.exe`
      actually starts the server and serves over HTTPS with working
      SQLite persistence across two separate exe launches, before trusting
      the CI recipe.
- [x] P4 — `.github/workflows/release.yml` (tag-triggered build + GitHub
      Release publish), built from the verified P3 local recipe.
- [x] P5 — Commit the prior turn's install-script work + this epic's
      changes; create and push the `v0.1.0` tag once the workflow is
      committed (pushing the tag is what actually triggers the release
      build on GitHub's side).

## Route

P2/P3 (code refactor + new launcher + local exe build/verification):
delegated direct — touches 4 files and needs real build-and-run
verification, well past the Writer trigger. P4 (single new workflow YAML)
and P5 (commit/tag): direct inline, mechanical once P2/P3 are verified.

## Progress

- 2026-09-24: Feature doc created. P1 done — see root-cause section above.
  Committed and pushed in two commits: `bc7a16c` (prior turn's
  `scripts/install.sh`/`install.bat` one-line installers + README section)
  and `c5c5b4c` (this doc + the `start.bat` fix).
- 2026-09-24: P2/P3 delegated to a general-purpose agent (frozen-aware
  `app/runtime_paths.py` + `config.py`/`db.py`/`certs/generate_cert.py`
  refactor, `scripts/run_server.py` launcher, local PyInstaller
  build-and-restart verification on this real Windows machine). Returned
  verified: build succeeded with **no** `--hidden-import`/`--collect-all`
  flags needed once `uvicorn.run()` was switched from the `"app.main:app"`
  string form to passing the imported `app` object directly (the string
  form built fine but failed at runtime — PyInstaller's static analysis
  can't see a module only referenced as a runtime string). Verified live:
  exe served HTTPS from a clean directory with no source nearby, and a
  second launch reused the existing cert (unchanged mtime) and retained
  both `settings.json` and a SQLite-written debitor record — full
  persistence across an exe restart, matching this project's existing
  `start.sh`/`start.bat` behavior. Reviewed the diff independently
  (orchestrator), re-ran `pytest tests/ -q` independently (344 passed,
  matches the agent's own count), confirmed no build artifacts (`dist_test/`,
  `build_test/`) were left behind. Committed as `7406c89`.
- 2026-09-24: P4 done. `.github/workflows/release.yml` — triggers on
  `v*.*.*` tag pushes, builds on `windows-latest` with the exact verified
  recipe (`pyinstaller --onefile --name datev-mock scripts/run_server.py`,
  no extra flags), publishes a GitHub Release for the tag with
  `dist/datev-mock.exe` attached via the pre-installed `gh` CLI (no
  third-party release action to pin/trust). YAML validated with
  `yaml.safe_load`.
- 2026-09-24: P5 done. Pushed `1f91112` to `main`, then created and pushed
  annotated tag `v0.1.0` — this triggers `release.yml` on GitHub's side.
  This machine has no `gh` CLI installed, so the workflow run itself
  couldn't be polled/verified from here; the user should check the
  Actions tab on GitHub to confirm the build+release succeeded remotely.
  This closes the epic: `3.9)` root cause fixed, one-line installers
  documented, and a tag-triggered standalone-.exe release pipeline in
  place, all committed and pushed across 4 commits (`bc7a16c`, `c5c5b4c`,
  `7406c89`, `1f91112`) plus tag `v0.1.0`.
