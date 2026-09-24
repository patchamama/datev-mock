# DATEV Mock — static read-only demo export for GitHub Pages

## Objective

User request (2026-09-24), following up on the referential-integrity
epic and an earlier `AskUserQuestion` about GitHub Pages: build a
**static, read-only snapshot** of a fixed, small set of demo IDs' GET
responses (both JSON and XML), plus a simple static frontend that
consumes them, deployable to GitHub Pages. The frontend must open with a
highlighted banner explaining what this is, its limitations, and how to
run the real dynamic mock locally (URL, port, a few example endpoints).

This is explicitly **not** a replacement for the real mock — established
in the prior conversation (GitHub Pages is static-only, no server
compute, no arbitrary port; the real mock's whole purpose is emulating a
*local* DATEV Desktop API, which is inherently not a public-internet
concept). This epic delivers the read-only, fixed-demo-ID subset that
*is* honestly achievable on static hosting, framed honestly as such.

## Why this is viable now (and wasn't before)

The referential-integrity epic
([`odd/tasks/datev-mock-referential-integrity.md`](datev-mock-referential-integrity.md))
made `app/scoped_data.py` generate **deterministic** data per
`(client_id, fiscal_year_id[, cost_system_id])` scope key — the same
scope always produces byte-identical output. A static export is now a
faithful, reproducible snapshot for a small *fixed* set of demo scope
keys, not an approximation. Arbitrary/infinite caller-supplied ids still
can't be pre-generated (the tension flagged earlier) — this epic doesn't
attempt that, it deliberately covers only the fixed demo set.

## Architecture decisions

1. **Fixed demo ID set** (small, memorable, obviously-fake so nobody
   mistakes them for real data): 2 demo clients — `demo-client-1`,
   `demo-client-2` — each with 2 demo fiscal years — `demo-fy-2024`,
   `demo-fy-2025` — giving 4 `(client_id, fiscal_year_id)` scopes total;
   one demo cost system per scope — `demo-cost-system-1` — for the
   nested cost-centers endpoint. This set is a constant in the generation
   script, not configurable at runtime (a static export has no runtime).
2. **Generation script, not hand-written fixtures.**
   `scripts/generate_static_demo.py` uses FastAPI's `TestClient`
   in-process (no live server needed) to call every relevant GET
   endpoint for the fixed demo set, in both JSON (`Accept:
   application/json`) and XML (default), and writes each response body
   verbatim to `static-demo/data/<url-path-with-demo-ids>.json` /
   `.xml` — mirroring the real API path structure so the relationship
   between a demo file and its real endpoint is obvious and greppable.
   Idempotent/re-runnable (overwrites, doesn't append).
3. **Scope of endpoints exported**: every Group-A GET route (has real
   fake data: fiscal-years, cost-systems, cost-centers, creditors,
   debitors, general-ledger-accounts, accounts-payable[+condense],
   accounts-receivable-condense, accounting-sequences-processed,
   accounting-transaction-keys, assets-stocktakings,
   posting-proposal-rules-incoming/outgoing, terms-of-payment), plus the
   global/unscoped ones: `accounting/v1/clients`, all 4 master-data
   routes (clients, addressees, banks, employees), both DMS routes
   (domains, documents). **Group B routes (cost-center-properties,
   cost-sequences, cost-accounting-records, various-addresses) are
   deliberately excluded** — they only ever show what's been written via
   SQLite, so a fresh static export would always show an empty array,
   which teaches a visitor nothing and just adds clutter. This exclusion
   is stated in the frontend's banner, not silently absent.
4. **No write endpoints in the static export** — impossible on static
   hosting by definition (decision already established in the prior
   conversation), and the banner says so explicitly.
5. **Frontend**: a single self-contained `static-demo/index.html`
   (Bootstrap 5 via CDN, matching this project's existing admin UI look
   and conventions — not a new design language), with:
   - A highlighted banner (Bootstrap `alert-warning`, dismissible false —
     always visible, this is the whole point) at the very top, before
     anything else, stating: this is a **static, read-only** snapshot of
     a **fixed demo ID set** (list them), JSON/XML are separate files
     (no `Accept`-header content negotiation possible on static
     hosting), **no write endpoints**, and **no Group B resources**
     (link to why). Then: to run the **real**, full dynamic mock
     locally — writes, live request log, admin UI, any client/fiscal-year
     id you want — use the one-line installer from the README, real
     mock runs at `https://127.0.0.1:58452` (self-signed cert), list 2-3
     example endpoint paths to try once it's running.
   - A simple catalog/nav below the banner, grouped by resource family,
     each entry offering a JSON link and an XML link that fetch and
     render the corresponding static file (pretty-printed in a `<pre>`,
     syntax-tinted is a nice-to-have not a requirement — keep this
     genuinely simple, it's a demo viewer, not a rebuild of the admin
     UI's full API Catalog).
6. **Publishing to GitHub Pages**: a new
   `.github/workflows/gh-pages.yml`, using GitHub's **official, first-
   party** `actions/upload-pages-artifact` + `actions/deploy-pages` —
   consistent with this project's existing preference (established in
   the exe-release epic) for avoiding third-party actions where an
   official one exists. Triggers on push to `main` touching
   `static-demo/**` or the workflow file itself, plus
   `workflow_dispatch` for manual runs. Publishes the `static-demo/`
   folder as-is (already-generated static files committed to the repo,
   not regenerated in CI — keeps the workflow simple and the published
   output exactly matches what's reviewable in the PR/commit). **Requires
   a one-time manual repo setting** (Settings → Pages → Source: "GitHub
   Actions") that no git/CLI action in this session can set — the user
   needs to do this once; the task doc's progress log will note this as
   an explicit handoff item, not silently assumed done.
7. **Static files are generated and committed**, not gitignored — unlike
   `datev_mock.db`/`settings.json`/certs (real runtime state), this is
   demo *output* meant to be reviewable in the repo and is what GitHub
   Pages actually serves; regenerating it is a deliberate, explicit step
   (`python scripts/generate_static_demo.py`) whenever the demo data
   should be refreshed (e.g. after a future change to `fake_data.py`'s
   generation logic), documented in the script's own docstring and the
   README.

## Phases

- [x] P1 — `scripts/generate_static_demo.py` + run it to produce
      `static-demo/data/**` (JSON+XML per decision #3's endpoint list,
      for the 4 fixed demo scopes + global resources). Verify output
      spot-checks correctly (a demo creditor's `addressee_id` resolves
      in the demo addressees file, same referential-integrity guarantee
      the prior epic established, now visible in static form).
- [x] P2 — `static-demo/index.html` frontend (banner + catalog/viewer).
      Verified in a real browser (via browser automation) against the
      static files on disk (served locally, e.g. `python -m http.server`
      from `static-demo/`) — not just "looks right in the source".
- [x] P3 — `.github/workflows/gh-pages.yml` (official actions,
      `static-demo/**`-triggered + manual dispatch). YAML validated.
      Documents the one-time "enable Pages in repo settings" step as an
      explicit handoff to the user, doesn't assume it's done.
- [ ] P4 — README section (what this is, link to the Pages URL once
      known, how to regenerate the static data), commit + push per
      phase (established workflow).

## Route

P1+P2 combined: delegated direct (script + ~130 generated data files +
a real frontend with browser verification — well past the Writer
trigger). P3/P4: direct inline once P1/P2 are verified (small, mechanical,
same pattern as the exe-release epic's `release.yml`/README phases).

## Progress

- 2026-09-24: Feature doc created. Architecture decisions above are the
  orchestrator's own design call, building directly on the
  referential-integrity epic's deterministic per-scope generation.
- 2026-09-24: P1+P2 done (delegated direct). 65 resources, 125 data
  files under `static-demo/data/`. One deliberate deviation from decision
  #3's literal "both JSON and XML" framing, judged correct and kept:
  master-data addressees/banks/employees and both DMS routes never had
  XML content negotiation in the live app (bare JSON list only) — the
  generation script detects this from the actual response `content-type`
  rather than blindly writing a `.xml` file that would misrepresent the
  real endpoint's behavior. Referential integrity holds in the static
  output too (spot-checked live by the delegated agent and independently
  by the orchestrator).
  Orchestrator independently re-verified: read both new files in full
  (`generate_static_demo.py` 218 lines, `index.html` 214 lines) — clean,
  matches every decision. **Attempted the planned browser-based visual
  pass myself** (`mcp__claude-in-chrome__navigate` to a locally-served
  copy) and hit the exact same failure the delegated agent already
  reported: `navigate` succeeds (tab title updates) but
  `computer{action:"screenshot"}` fails with "Frame with ID 0 is showing
  error page" — confirms this is a structural limitation of this
  environment (the Chrome extension's browser runs in a different network
  namespace than the Bash tool's shell, so it can't reach a `127.0.0.1`
  port the shell bound — same class of issue already seen in the
  write-endpoints epic's P1), not something a retry fixes. Did not force
  a fake visual pass; compensated with direct `curl` checks against the
  same locally-served copy (`index.html` 200, `data/manifest.json` valid
  JSON with 65 entries, a sampled data file's content confirmed) plus the
  full source-code review above. Committed as `9742ece`.
- 2026-09-24: P3 done (direct inline — small, mechanical, same pattern as
  the exe-release epic's `release.yml`). New
  `.github/workflows/gh-pages.yml`: triggers on push to `main` touching
  `static-demo/**` or the workflow file itself, plus manual
  `workflow_dispatch`. Uses only official, first-party GitHub actions
  (`actions/checkout`, `actions/configure-pages`,
  `actions/upload-pages-artifact`, `actions/deploy-pages`) — no
  third-party action to pin/trust, consistent with this project's
  existing preference. Publishes the already-committed `static-demo/`
  folder as-is (not regenerated in CI). YAML validated with
  `yaml.safe_load`.
  **Handoff item for the user**: this workflow cannot itself enable
  GitHub Pages — that's a one-time repository setting
  (Settings → Pages → Source: "GitHub Actions") no git/CLI action in this
  session can set. Until that's done once, this workflow will run but the
  deployment step will fail with a "Pages not enabled" style error.
