# ARC Lucifer Cleanroom Runtime

A clean-room, local-first operator runtime that combines:
- **ARC Kernel** for event authority, policy, receipts, replay, rollback, branching, and persistent state
- **Lucifer Runtime** for terminal routing, command handling, tool execution, and resilience/fallbacks
- **Cognition Services** for goals, world-model views, planning, evaluation, and persistent loop behavior
- **Managed local-model execution** through llamafile
- **Memory tiers** with mirror-then-retire archival and ranked retrieval
- **Self-improvement runs** with sandboxed candidate generation, scoring, validation, promotion, and adversarial testing

## Current package state (v2.8.0)

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

## Production posture

This repo is production-ready as a **technical operator/runtime foundation**.
It is not claiming solved AGI. What remains outside repo-only completion is real hardware/model soak testing, GGUF quality comparisons, installer packaging, and long-duration burn-in.

## Quick start

```bash
/usr/local/bin/python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
pytest -q
./scripts/smoke.sh
PYTHONPATH=src python -m lucifer_runtime.cli commands
```

## Common commands

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

## Code-operator commands

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

## Repo structure

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
```

## Release hygiene

```bash
./scripts/smoke.sh
./scripts/release_check.sh
```

## Documentation

See:
- `docs/llamafile_flow.md`
- `docs/token_counting.md`
- `docs/memory_retention.md`
- `docs/v2_1_code_operator.md`
- `docs/v2_4_memory_mirror_and_stack.md`
- `docs/v2_6_candidate_cycles.md`
- `docs/v2_7_adversarial_cycles.md`


## Open-ended model profiles and training export

This runtime now supports open-ended model profiles so you can keep using the
current local llamafile path while preparing your own future GGUF-oriented model
work.

Examples:

```bash
PYTHONPATH=src python -m lucifer_runtime.cli model register-profile local-dev --backend-type gguf_local --binary-path /path/to/llamafile --model-path /path/to/model.gguf --activate
PYTHONPATH=src python -m lucifer_runtime.cli model profiles
PYTHONPATH=src python -m lucifer_runtime.cli train export-supervised --output training_corpus.jsonl
PYTHONPATH=src python -m lucifer_runtime.cli train export-preferences --output preference_pairs.jsonl
```
