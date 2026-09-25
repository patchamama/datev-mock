# Save live resource responses to disk for later reload (both backends)

## Objective

User request (2026-09-25): "Agregar opción de guardar en una carpeta en
backend con fastapi, o spring-boot todos los requests de un determinado
recurso para que se puedan cargar en el futuro con esos datos si se desea."
— add an option, on both backends, to save all requests/responses for a
given resource to a folder on disk, so that data can be loaded back later
if desired.

**Queued, not started yet**: this needs to touch `app/main.py` (new router
registration) and Java's admin controller/config, both of which epic F6 is
actively editing concurrently in this session. Starting this now would risk
two agents editing the same files in the same working tree at once (a real
conflict, not a hypothetical one — already avoided once this session by
sequencing F5/gh-pages/release as non-overlapping-file parallel work and
F1-F6 as strictly sequential when they share a file). This epic starts once
F6 (and any epics after it that still touch `app/main.py`) are committed.

## Design (orchestrator's own proposal, not yet confirmed with the user)

Rather than building a separate parallel "recording" subsystem, reuse what
already exists:

- `app/request_log.py` already captures every request/response that flows
  through the mock (used today for the admin panel's live SSE request log).
- `app/overrides.py` already accepts an uploaded XML/JSON file *per
  resource* as an override, and already knows how to detect/validate a
  resource's content type from that file (`detect_candidates`/
  `detect_content_type`/`sanitize_xml`).

Proposed new capability: a "Save to file" action (new admin API endpoint,
e.g. `POST /admin/api/snapshots` taking a resource path/selector) that
writes the most recent observed response body for that resource from the
request log to a file under a new `snapshots/` folder (gitignored, like
`datev_mock.db`/`settings.json`), in **exactly the format the existing
override-upload endpoint already accepts** — so the loop closes with
infrastructure that already exists rather than inventing a second, separate
load/replay mechanism: a saved snapshot is just a file a user can re-upload
via the existing overrides UI whenever they want that exact response back.

Open questions to confirm with the user once this epic actually starts
(do not assume silently):
1. Should this snapshot a *single* most-recent response for the given
   resource, or *every distinct* request/response pair observed for it
   (e.g. once per distinct id/query combination)? The user's wording
   ("todos los requests de un determinado recurso") leans toward "every
   observed request for that resource," which is a meaningfully bigger
   scope (multiple files, a naming scheme to avoid collisions) than "the
   latest one."
2. Folder location and naming convention — `snapshots/<resource-path>/...`
   mirroring `static-demo/data/`'s own path-mirroring convention seems
   consistent with this project's existing style, but worth confirming
   rather than assuming.
3. Should Java get an equivalent, or is this acceptable as a Python-first
   feature with Java following later (matching this project's existing
   "asymmetric completion, documented honestly" pattern already used for
   F5's NTLM gap)? The user's own wording explicitly asked for "fastapi, o
   spring-boot" (either), suggesting both are wanted, not just one.

## Scope (draft, to refine when this epic starts)

- [ ] Design confirmation (the 3 open questions above) before writing code.
- [ ] FastAPI: new save-to-folder endpoint + wiring into `request_log.py`'s
  existing captured data; folder gitignored.
- [ ] Java: equivalent endpoint using `RequestLogStore`/`RequestLoggingFilter`
  (from SB9's `admin/` package).
- [ ] Frontend: a "Save to file" action somewhere sensible (the API Catalog
  card, or per-resource in the request log view) wired to the new
  endpoint(s) via `appFetch`.
- [ ] Strict TDD on both backends, as this repo's standing convention
  requires.

## Route

Delegated direct once started — touches `app/main.py`/a new router (backend
conflict-risk file, see above), Java's admin package, and
`frontend/admin.html` (also currently touched by F6/F7/F8 in flight) — well
past the Writer trigger, and must be sequenced after every currently-queued
frontend epic finishes, not run in parallel with them.
