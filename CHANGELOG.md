
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
