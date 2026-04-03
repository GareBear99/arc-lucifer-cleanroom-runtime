# 📜 ARC Lucifer Cleanroom Runtime

Deterministic, local-first AI operator runtime with receipts, replay, rollback, ranked memory, managed local-model execution, and sandboxed self-improvement.

## Why this repo exists

ARC Lucifer Cleanroom Runtime is a clean-room runtime foundation for building persistent local AI operators that can:
- execute deterministic operator flows
- record receipts and policy decisions
- support replay, rollback, and validation
- maintain ranked hot/warm/archive memory
- run bounded self-improvement cycles inside a sandbox
- stay open-ended for future GGUF, llamafile, or other backend integrations

This repository is designed as a **production-ready technical foundation**, not a claim of solved AGI.

## Current package state

**Version:** `v2.9.1`

This build includes:
- persistent shared SQLite-backed kernel state
- deterministic file, shell, and code-edit operator flows
- exact line/symbol-grounded code editing for Python
- managed local llamafile prompt path with tracked receipts
- rollback, replay, evaluations, policy decisions, and fallback histories
- hot/warm/archive memory with early archive mirroring and ranked memory search
- self-improvement analysis, planning, scaffolding, candidate generation, scoring, best-candidate execution, promotion, and adversarial fault injection
- operator commands for monitor, info, doctor, export/import, backup, compact, and failures
- bootstrap, smoke-test, and release-check scripts
- open-ended model profile registration and training data export hooks

## Production posture

This repo is production-ready as a **technical operator/runtime foundation**.

It is **not** yet claiming the following are complete:
- real hardware soak validation on your exact GGUF + llamafile setup
- benchmark-backed model quality comparison pack
- signed desktop installer packaging
- unconstrained model-authored patching beyond deterministic candidate machinery

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
pytest -q
./scripts/smoke.sh
PYTHONPATH=src python -m lucifer_runtime.cli commands
```

## Core commands

```bash
PYTHONPATH=src python -m lucifer_runtime.cli commands
PYTHONPATH=src python -m lucifer_runtime.cli state
PYTHONPATH=src python -m lucifer_runtime.cli info
PYTHONPATH=src python -m lucifer_runtime.cli doctor
PYTHONPATH=src python -m lucifer_runtime.cli monitor --watch 2 --iterations 5
PYTHONPATH=src python -m lucifer_runtime.cli failures
PYTHONPATH=src python -m lucifer_runtime.cli memory status
PYTHONPATH=src python -m lucifer_runtime.cli memory search "archive mirror"
PYTHONPATH=src python -m lucifer_runtime.cli bench
```

## Self-improvement commands

```bash
PYTHONPATH=src python -m lucifer_runtime.cli self-improve analyze
PYTHONPATH=src python -m lucifer_runtime.cli self-improve plan
PYTHONPATH=src python -m lucifer_runtime.cli self-improve scaffold
PYTHONPATH=src python -m lucifer_runtime.cli self-improve generate-candidates <run_id> --path src/file.py --replacement "..."
PYTHONPATH=src python -m lucifer_runtime.cli self-improve score-candidates <run_id>
PYTHONPATH=src python -m lucifer_runtime.cli self-improve best-candidate <run_id>
PYTHONPATH=src python -m lucifer_runtime.cli self-improve execute-best <run_id> --promote
PYTHONPATH=src python -m lucifer_runtime.cli self-improve inject-fault <run_id> --kind python_syntax_break --path src/file.py
PYTHONPATH=src python -m lucifer_runtime.cli self-improve adversarial-cycle <run_id> --kind force_validation_failure --path src/file.py --replacement "..."
```

## Code operator commands

```bash
PYTHONPATH=src python -m lucifer_runtime.cli code index <path>
PYTHONPATH=src python -m lucifer_runtime.cli code verify <path>
PYTHONPATH=src python -m lucifer_runtime.cli code plan <path> "<instruction>" [--symbol name]
PYTHONPATH=src python -m lucifer_runtime.cli code replace-range <path> <start_line> <end_line> "<replacement_text>"
PYTHONPATH=src python -m lucifer_runtime.cli code replace-symbol <path> <symbol_name> "<replacement_text>"
```

## Memory lifecycle

Memory supports:
- early archive mirroring on demand
- continued live/front-memory presence until scheduled retirement
- sync from live memory into archive while live
- final front-memory retirement at the normal archive date
- ranked retrieval using readable memory headers: title, summary, keywords, category, importance, and status

## Repository structure

```text
src/arc_kernel/
src/lucifer_runtime/
src/cognition_services/
src/model_services/
src/verifier/
src/memory_subsystem/
src/self_improve/
src/code_editing/
src/resilience/
src/dashboards/
scripts/
examples/
tests/
docs/
.github/
assets/
```

## Release and validation

```bash
./scripts/smoke.sh
./scripts/release_check.sh
```

## Documentation index

Start here:
- [`docs/INDEX.md`](docs/INDEX.md)
- [`docs/architecture.md`](docs/architecture.md)
- [`docs/REPO_SEO.md`](docs/REPO_SEO.md)

Technical references:
- `docs/llamafile_flow.md`
- `docs/token_counting.md`
- `docs/memory_retention.md`
- `docs/v2_1_code_operator.md`
- `docs/v2_4_memory_mirror_and_stack.md`
- `docs/v2_6_candidate_cycles.md`
- `docs/v2_7_adversarial_cycles.md`
- `docs/v2_9_model_profiles_and_training.md`

## Open-ended model profiles and training export

Examples:

```bash
PYTHONPATH=src python -m lucifer_runtime.cli model register-profile local-dev --backend-type gguf_local --binary-path /path/to/llamafile --model-path /path/to/model.gguf --activate
PYTHONPATH=src python -m lucifer_runtime.cli model profiles
PYTHONPATH=src python -m lucifer_runtime.cli train export-supervised --output training_corpus.jsonl
PYTHONPATH=src python -m lucifer_runtime.cli train export-preferences --output preference_pairs.jsonl
```

## GitHub release checklist

Before publishing a release:
- run `pytest -q`
- run `./scripts/smoke.sh`
- run `./scripts/release_check.sh`
- update `CHANGELOG.md`
- tag the release with the matching version
- use the release template in `.github/release_template.md`

## License and contribution

- See [`LICENSE.md`](LICENSE.md)
- See [`CONTRIBUTING.md`](CONTRIBUTING.md)
- See [`SECURITY.md`](SECURITY.md)
