# README Java backend and localization

## Objective
Document the Spring Boot backend and add maintained German and Spanish README entry points linked from the English README.

## Why
Recent commits introduced a standalone Java 21 / Spring Boot backend, auto-detecting launchers, a standalone configurable admin frontend, GitHub Pages publishing, endpoint E2E progress feedback, and Java release assets. The root README still describes only the FastAPI backend.

## Scope
- Update `README.md` with accurate backend selection, Java setup/run/test/release information, project structure, technology, and language links.
- Add `README.de.md` and `README.es.md` as localized onboarding documents that link to the English README for exhaustive contract detail.
- Do not change application behavior, build configuration, or release workflows.

## Constraints
- The FastAPI server is the full reference implementation; Java offers 63 of 75 documented routes and intentionally does not serve the admin HTML itself.
- Java requires JDK 21 and normally runs plain HTTP on port 58553 through its dedicated launchers.
- Verify all README claims against committed project documentation.

## Delivery strategy
- `ask-on-risk`; documentation-only change, no PR slicing forecast needed.
- TDD: not applicable to documentation-only work. Verification: Markdown link/structure checks and repository diff review.

## Tasks
- [x] RDM-1 — Update the English README with an accurate Java backend path and recent delivery/frontend changes. Route: inline (documentation-only, scope already verified).
- [x] RDM-2 — Add a German localized README. Route: inline (documentation-only, derived from verified English content).
- [x] RDM-3 — Add a Spanish localized README. Route: inline (documentation-only, derived from verified English content).
- [x] RDM-4 — Verify Markdown links, headings, and final diff; record evidence.

## Progress
Completed RDM-1 through RDM-4. Verification: local Markdown targets resolve; `git diff --check` is clean for these documentation files; the Spring Boot route count/gaps were reconciled with the SB10 inventory and the later SB12 state-sharing commit. Application tests were not run because this change is documentation-only.

## Next step
Documentation is complete and ready for review. A local commit could not be created because this environment denies writes to `.git` (`index.lock`: permission denied).
