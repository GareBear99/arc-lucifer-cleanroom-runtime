## v2.10.5

- clarified the public direction around optional perception, multimodal, and robotics adapters
- added `perception_adapters/` contracts so embodiment layers can be attached without becoming hard runtime requirements
- expanded packaging extras for optional vision/audio/robotics experimentation while keeping the base install dependency-light
- updated README and architecture docs to present the repo honestly as an autonomy foundation rather than a finished living machine
- added docs for vision runtime flow, optional adapter doctrine, and public direction goals

## v2.10.4

- cleaned release artifacts from the tracked tree and added a root `.gitignore` for caches, local state, and generated outputs
- restored a real GitHub Actions CI workflow covering Python 3.11, 3.12, and 3.13
- added a `Makefile` for install/test/smoke/release-check/clean flows
- made bootstrap and release-check scripts more portable by defaulting to `python3` and invoking smoke through `bash`
- corrected README quick-start and repo-structure docs so they match the actual package layout

## v2.10.3

- Added first-class directive ledger with persisted operator directives, priorities, supersession, and completion state.
- Added continuity shell with boot receipts, heartbeat tracking, watchdog health, and primary/fallback mode selection.
- Projected directives and continuity events into runtime world state for durable observability.
- Added CLI surfaces for `directive` and `continuity` administration.
- Added tests for directive round-tripping, continuity boot/heartbeat behavior, and state projection.

## v2.10.2
- added structured goal compilation with constraints, invariants, evidence requirements, and archive mode
- added shadow predicted-vs-actual comparison recording
- added promotion-court review for self-improvement runs before promotion
- auto-emitted FixNet records from candidate scoring and best-candidate selection
- synced package version and README state to the current release

## v2.9.1
- added FixNet dossier recording and embedded archive packs so repair intelligence can be persisted into branch-visible runtime history
- projected FixNet case/archive counts into runtime state world model
- added CLI support for `fixnet record` and `fixnet embed`


# Changelog

## v2.9.0
- Added open-ended model profile registry for GGUF/local/external backends.
- Added training corpus export commands for supervised and preference JSONL.
- Active model profiles now feed prompt configuration automatically.
- Kept the runtime open-ended for future custom GGUF learning work while preserving current llamafile flow.

## v2.8.0
- Production release hygiene pass
- Added CI workflow for Python 3.11, 3.12, and 3.13
- Added smoke-test and release-check scripts
- Added CONTRIBUTING and SECURITY docs
- Cleaned packaged tree and refreshed README to current package capabilities

## v2.7.0
- Added adversarial self-improvement fault injection and cycle testing

## v2.6.0
- Added multi-candidate self-improvement generation, scoring, and best-candidate execution

## v2.5.0
- Added memory search/ranking and planning influence from mirrored memory

## v2.4.0
- Added early archive mirroring with mirror-then-retire lifecycle

## v2.3.0
- Added deterministic sandbox patch/validate/promote cycle

## v2.2.0
- Added resilience and fallback subsystem with degraded completion states

## v2.1.0
- Added exact line/symbol-grounded code editing and promotion validation

## v2.0.0
- Added self-improvement planning and scaffolded run worktrees
