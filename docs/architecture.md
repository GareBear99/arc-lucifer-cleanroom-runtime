# ARC Lucifer Cleanroom Runtime Architecture

ARC Lucifer Cleanroom Runtime is organized as a deterministic operator runtime with separated responsibilities.

## Major subsystems

- `arc_kernel/` — event authority, receipts, policy recording, replay, rollback, branching, persistence
- `lucifer_runtime/` — CLI surface, routing, command handling, operator-facing execution layer
- `cognition_services/` — goals, planning, evaluation, world-model oriented helpers
- `model_services/` — local model configuration and managed execution paths
- `memory_subsystem/` — hot/warm/archive tiers, mirroring, ranking, retrieval
- `self_improve/` — scaffolded runs, candidate generation, scoring, execution, promotion, adversarial testing
- `code_editing/` — exact range and symbol-grounded code manipulation flows
- `resilience/` — degraded modes, fallbacks, tracked failures, operational hardening
- `verifier/` — validation surfaces and safe promotion checks

## Design priorities

1. Deterministic runtime behavior where possible
2. Receipts and auditability over silent mutation
3. Replay and rollback as first-class operational tools
4. Memory that remains readable and rankable
5. Bounded self-improvement instead of unconstrained mutation
6. Open-ended backend integration without giving up runtime authority

## Current boundary

The repository is a strong technical foundation. Real-world production maturity still depends on external soak testing, hardware validation, installer packaging, and chosen model benchmarking.
