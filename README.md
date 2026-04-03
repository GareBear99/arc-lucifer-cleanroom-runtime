# 📜 ARC Lucifer Cleanroom Runtime

A clean-room, local-first operator runtime that combines:
- **ARC Kernel** for event authority, policy, receipts, replay, rollback, branching, and persistent state
- **Lucifer Runtime** for terminal routing, command handling, tool execution, and resilience/fallbacks
- **Cognition Services** for goals, world-model views, planning, evaluation, and persistent loop behavior
- **Managed local-model execution** through llamafile and open-ended model profiles
- **Memory tiers** with mirror-then-retire archival and ranked retrieval
- **Self-improvement runs** with sandboxed candidate generation, scoring, validation, promotion, and adversarial testing
- **Directive + continuity shell** for persistent mission state, boot receipts, heartbeats, and primary/fallback mode tracking
- **FixNet repair intelligence** for fix storage, trust/consensus, novelty filtering, semantic fix lineage, and archive-visible mirrors

## What this is

This repo is not a generic chat wrapper.
It is a **persistent local operator runtime** designed around an enduring shell and a replaceable cognition core.

The intended architecture is:
- **directive shell** for long-lived operator intent
- **GGUF / local model core** for reasoning and planning
- **deterministic runtime spine** for receipts, replay, rollback, and policy
- **fallback continuity mode** for degraded operation
- **FixNet repair graph** for reusable failure-to-solution knowledge
- **archive lineage** for mirror-then-retire historical memory

## Current package state (v2.10.3)

This build includes:
- persistent shared SQLite-backed kernel state
- deterministic file, shell, and code-edit operator flows
- exact line/symbol-grounded code editing for Python
- managed local llamafile prompt path with tracked receipts
- rollback, replay, evaluations, policy decisions, and fallback histories
- hot/warm/archive memory with early archive mirroring and ranked memory search
- self-improvement analysis, planning, scaffolding, candidate generation, scoring, best-candidate execution, promotion review, and adversarial fault injection
- goal compilation into constraints, invariants, success metrics, abort conditions, evidence requirements, and archive mode
- shadow predicted-vs-actual comparison
- tool trust tracking and curriculum-memory updates
- directive ledger, continuity boot receipts, heartbeats, and primary/fallback mode tracking
- FixNet repair intelligence with semantic fix-to-fix lineage and embedded archive mirrors
- operator commands for monitor, info, doctor, export/import, backup, compact, and failures
- bootstrap, smoke-test, and release-check scripts

## Production posture

This repo is production-ready as a **technical operator/runtime foundation**.
It is **not** claiming solved AGI.

What still sits outside repo-only completion:
- long-run soak testing on target hardware
- real GGUF quality comparisons and routing policy tuning
- signed installer and end-user packaging
- proving safe long-duration autonomy under real workloads
- optional remote publisher/sync against real remotes

## Why this exists

Most commercial systems in this space are optimized for **coding-agent productivity**.
This repo is aimed at a different shape:

**an enduring, directive-bound, local-first intelligence shell with a swappable cognition core**.

That means the runtime identity comes from:
- directives
- doctrine/policy
- event spine
- memory/archive lineage
- repair knowledge
- current cognition core

not from a single stateless model session.

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

## Directive and continuity commands

```bash
PYTHONPATH=src python -m lucifer_runtime.cli directive add "Preserve continuity and never silently fail" --priority 10
PYTHONPATH=src python -m lucifer_runtime.cli directive stats
PYTHONPATH=src python -m lucifer_runtime.cli continuity boot
PYTHONPATH=src python -m lucifer_runtime.cli continuity heartbeat
PYTHONPATH=src python -m lucifer_runtime.cli continuity status
```

## Goal and shadow-loop commands

```bash
PYTHONPATH=src python -m lucifer_runtime.cli goal "Keep the runtime healthy and improve resilience" --priority 8
PYTHONPATH=src python -m lucifer_runtime.cli shadow "Run release checks and compare expected vs actual" --predicted-status approve --confirm
```

## Self-improvement commands

```bash
PYTHONPATH=src python -m lucifer_runtime.cli self-improve analyze
PYTHONPATH=src python -m lucifer_runtime.cli self-improve plan
PYTHONPATH=src python -m lucifer_runtime.cli self-improve scaffold
PYTHONPATH=src python -m lucifer_runtime.cli self-improve generate-candidates <run_id> --path src/file.py --replacement "..."
PYTHONPATH=src python -m lucifer_runtime.cli self-improve score-candidates <run_id>
PYTHONPATH=src python -m lucifer_runtime.cli self-improve best-candidate <run_id>
PYTHONPATH=src python -m lucifer_runtime.cli self-improve review-run <run_id>
PYTHONPATH=src python -m lucifer_runtime.cli self-improve execute-best <run_id> --promote
PYTHONPATH=src python -m lucifer_runtime.cli self-improve inject-fault <run_id> --kind python_syntax_break --path src/file.py
PYTHONPATH=src python -m lucifer_runtime.cli self-improve adversarial-cycle <run_id> --kind force_validation_failure --path src/file.py --replacement "..."
```

## FixNet, trust, and curriculum commands

```bash
PYTHONPATH=src python -m lucifer_runtime.cli fixnet stats
PYTHONPATH=src python -m lucifer_runtime.cli trust stats
PYTHONPATH=src python -m lucifer_runtime.cli curriculum stats
```

## Code-operator commands

```bash
PYTHONPATH=src python -m lucifer_runtime.cli code index <path>
PYTHONPATH=src python -m lucifer_runtime.cli code verify <path>
PYTHONPATH=src python -m lucifer_runtime.cli code plan <path> "<instruction>" [--symbol name]
PYTHONPATH=src python -m lucifer_runtime.cli code replace-range <path> <start_line> <end_line> "<replacement_text>"
PYTHONPATH=src python -m lucifer_runtime.cli code replace-symbol <path> <symbol_name> "<replacement_text>"
```

## How to visualize the runtime

Think of it as a **local command center with a replaceable brain**.

```text
DIRECTIVES
   ↓
BOOT / CONTINUITY
   ↓
WORLD + MEMORY STATE
   ↓
GOAL COMPILE / PLAN
   ↓
ACTION / TOOL USE
   ↓
RECEIPT / RESULT
   ↓
VERIFY / COMPARE
   ↓
LEARN / FIXNET / TRUST / CURRICULUM
   ↓
ARCHIVE / CONTINUITY UPDATE
   ↺
```

Typical live output looks more like an operator log than a chatbot:

```text
[BOOT] runtime_id=lucifer-main mode=primary status=healthy
[DIRECTIVE] loaded 4 active directives
[MEMORY] active=12 archived_links=31 fixnet_records=9
[GOAL] compiled "keep runtime healthy and improve resilience"
[PLAN] 3 candidate actions generated
[SHADOW] predicted outcome=approve confidence=0.82
[EXECUTE] sandbox self-improve run created: run_1042
[PATCH] candidate_2 applied to src/runtime.py
[VALIDATE] pytest passed
[REVIEW] promotion court accepted
[PROMOTE] run_1042 promoted
[FIXNET] recorded improved_version of fix_0081
[TRUST] self_improve_validation +0.04
[CURRICULUM] updated recurring theme: resilience-hardening
[ARCHIVE] mirrored fix dossier to archive branch
[HEARTBEAT] mode=primary uptime_ok=yes
```

## Positioning vs current commercial tools

The commercial market already has stronger product maturity in some areas.
Public materials currently show:
- **Devin** emphasizes long-horizon autonomous software engineering with shell, editor, and browser access in a sandboxed environment.
- **Claude Code** emphasizes terminal-native agentic coding, codebase reading, editing, command execution, and checkpoint-style autonomy workflows.
- **Augment Intent** emphasizes a living-spec, isolated-workspace, multi-agent orchestration model.

This runtime aims at a somewhat different center of gravity: a **persistent local-first continuity shell** rather than only a coding-agent workspace.

### Comparison snapshot

| Capability | ARC Lucifer Cleanroom Runtime | Devin | Claude Code | Augment Intent |
|---|---|---|---|---|
| Long-horizon coding autonomy | Strong foundation | Strong | Strong | Strong |
| Terminal-native operation | Yes | Partial/publicly less emphasized | Yes | Yes |
| Sandboxed execution | Yes | Yes | Strong workflow support | Strong |
| PR / test / review loop | Yes, repo-side | Yes | Strong workflows | Strong |
| Persistent directive ledger | Yes | Not publicly core-positioned | Not publicly core-positioned | Living spec is the closest overlap |
| Primary / fallback self continuity | Yes | Not publicly presented this way | Not publicly presented this way | Not publicly presented this way |
| Append-only receipt / replay / rollback spine | Yes | Some overlap, not core-public framing | Checkpoints and rewind overlap | Some orchestration overlap |
| FixNet-style repair graph | Yes | Not publicly shown | Not publicly shown | Not publicly shown |
| Live archive mirroring / retirement metadata | Yes | Not publicly shown | Not publicly shown | Not publicly shown |
| Local-first GGUF “replaceable brain” shell | Yes | No | No | Not core-positioned |
| Enterprise product maturity | Low vs market | High | High | High |

### Honest reading

- Commercial products are ahead on **polish, onboarding, enterprise packaging, and validated production usage**.
- This runtime is more distinctive on **continuity-shell architecture**, **directive persistence**, **fallback self**, **repair lineage**, and **archive lineage**.
- The goal here is not to pretend to out-product those systems today.
- The goal is to build a stronger **governed persistent runtime architecture** that can host local cognition over long horizons.

## Memory lifecycle

Memory supports:
- early archive mirroring on demand
- continued live/front-memory presence until scheduled retirement
- sync from live memory into archive while live
- final front-memory retirement at the normal archive date
- ranked retrieval using readable memory headers: title, summary, keywords, category, importance, and status

## FixNet repair intelligence

FixNet is the repair-intelligence sidecar to the deterministic runtime spine.
It separates:
- **FixLedger** for stored fix objects and semantic fix-to-fix lineage
- **FixConsensus** for trust, analytics, and reuse quality
- **FixNoveltyFilter** for duplicate/variant detection before polluting the store
- **EmbeddedFixArchive** for archive-visible mirrors of selected fixes

The runtime auto-emits FixNet records for key self-improve outcomes so repair knowledge compounds instead of disappearing into logs.

## Open-ended model profiles and training export

This runtime supports open-ended model profiles so you can keep using the
current local llamafile path while preparing your own future GGUF-oriented model
work.

Examples:

```bash
PYTHONPATH=src python -m lucifer_runtime.cli model register-profile local-dev --backend-type gguf_local --binary-path /path/to/llamafile --model-path /path/to/model.gguf --activate
PYTHONPATH=src python -m lucifer_runtime.cli model profiles
PYTHONPATH=src python -m lucifer_runtime.cli train export-supervised --output training_corpus.jsonl
PYTHONPATH=src python -m lucifer_runtime.cli train export-preferences --output preference_pairs.jsonl
```

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
src/fixnet/
src/continuity/
src/directives/
src/trust/
src/curriculum/
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

## Current limits

This repo is a serious local operator-runtime foundation.
It is not yet a proven forever-running AGI system.

The remaining real work is mostly outside markdown edits:
- long-horizon runtime soak testing
- actual GGUF routing and quality benchmarking
- remote publisher hardening
- end-user packaging and installers
- proving safe continuous operation under real directives
