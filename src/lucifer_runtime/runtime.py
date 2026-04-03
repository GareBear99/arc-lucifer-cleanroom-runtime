"""Primary runtime orchestration for deterministic tools, local model calls, and self-improvement flows."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterator, Optional

from arc_kernel.engine import KernelEngine
from arc_kernel.schemas import Capability, Decision, EventKind, Proposal, Receipt, RiskLevel
from verifier.validators import validate_result
from cognition_services.planner import PlannerService
from cognition_services.evaluator import EvaluatorService
from cognition_services.goal_engine import GoalEngine
from cognition_services.shadow import ShadowExecutionService
from cognition_services.trust import ToolTrustRegistry
from cognition_services.directives import DirectiveLedger
from model_services import BackendRegistry, LlamafileBackend, LlamafileProcessManager, StreamEvent
from self_improve import BenchmarkRunner, ImprovementAnalyzer, ImprovementPlanner, SandboxManager, PromotionGate, ImprovementExecutor, CandidateCycleManager, AdversarialManager
from code_editing import CodeEditPlanner, CodeVerifier, PatchEngine, PatchKind, PatchOperation
from resilience import ContinuationManager, FailureClassifier, FallbackSelector, ContinuityShell
from .router import IntentRouter
from .tools import ToolRegistry
from fixnet import FixNet
from memory_subsystem.curriculum import CurriculumMemory


class LuciferRuntime:
    def __init__(
        self,
        kernel: KernelEngine | None = None,
        workspace_root: str | Path = '.',
        backend_registry: BackendRegistry | None = None,
    ) -> None:
        self.kernel = kernel or KernelEngine()
        self.workspace_root = Path(workspace_root)
        self.session_metrics = {
            'requests': 0,
            'prompt_chars': 0,
            'prompt_words': 0,
            'templated_prompt_chars': 0,
            'completion_chars': 0,
            'completion_words': 0,
            'exact_prompt_tokens': 0,
            'exact_completion_tokens': 0,
            'exact_total_tokens': 0,
        }
        self.router = IntentRouter()
        self.tools = ToolRegistry(workspace_root=workspace_root)
        self.planner = PlannerService()
        self.evaluator = EvaluatorService()
        self.goals = GoalEngine()
        self.directives = DirectiveLedger(workspace_root)
        self.shadow = ShadowExecutionService()
        self.trust = ToolTrustRegistry(workspace_root)
        self.curriculum = CurriculumMemory(workspace_root)
        self.benchmarks = BenchmarkRunner()
        self.improvement_analyzer = ImprovementAnalyzer()
        self.improvement_planner = ImprovementPlanner()
        self.sandbox_manager = SandboxManager()
        self.promotion_gate = PromotionGate()
        self.improvement_executor = ImprovementExecutor()
        self.candidate_cycles = CandidateCycleManager()
        self.adversarial = AdversarialManager()
        self.code_planner = CodeEditPlanner()
        self.code_verifier = CodeVerifier()
        self.patch_engine = PatchEngine()
        self.failure_classifier = FailureClassifier()
        self.fallback_selector = FallbackSelector()
        self.continuations = ContinuationManager()
        self.continuity = ContinuityShell(workspace_root, runtime_name='arc-lucifer-runtime')
        self.backends = backend_registry or BackendRegistry()
        self.fixnet = FixNet(str(self.workspace_root))
        if 'llamafile' not in self.backends.names():
            self.backends.register('llamafile', LlamafileBackend(process_manager=LlamafileProcessManager(keep_alive=True)))


    def register_directive(
        self,
        *,
        title: str,
        instruction: str,
        priority: int = 50,
        scope: str = 'global',
        constraints: list[str] | None = None,
        success_conditions: list[str] | None = None,
        abort_conditions: list[str] | None = None,
        persistence_mode: str = 'forever',
        issuer: str = 'operator',
        supersedes: str | None = None,
    ) -> dict:
        directive = self.directives.register(
            title=title,
            instruction=instruction,
            priority=priority,
            scope=scope,
            constraints=constraints,
            success_conditions=success_conditions,
            abort_conditions=abort_conditions,
            persistence_mode=persistence_mode,
            issuer=issuer,
            supersedes=supersedes,
        )
        payload = {'kind': 'directive_ledger', **directive}
        self.kernel.record_evaluation('directives', payload)
        return {'status': 'ok', 'directive': directive, **({'directive_id': directive.get('directive_id'), 'directive_status': directive.get('status')})}

    def complete_directive(self, directive_id: str, *, status: str = 'complete') -> dict:
        directive = self.directives.complete(directive_id, status=status)
        if directive is None:
            return {'status': 'error', 'reason': 'unknown_directive'}
        payload = {'kind': 'directive_ledger', **directive}
        self.kernel.record_evaluation('directives', payload)
        return {'status': 'ok', 'directive': directive, **({'directive_id': directive.get('directive_id'), 'directive_status': directive.get('status')})}

    def directive_stats(self) -> dict:
        return {'status': 'ok', **self.directives.stats()}

    def boot_continuity(self, *, fallback_available: bool = True, notes: str = '') -> dict:
        primary_available = 'llamafile' in self.backends.names()
        receipt = self.continuity.boot(
            active_directive_count=self.directives.stats().get('active_directive_count', 0),
            primary_available=primary_available,
            fallback_available=fallback_available,
            notes=notes,
        )
        payload = {'kind': 'continuity_boot', **receipt}
        self.kernel.record_evaluation('continuity', payload)
        return {'status': 'ok', 'boot_receipt': receipt, **({'mode': receipt.get('mode'), 'boot_index': receipt.get('boot_index')})}

    def continuity_heartbeat(self, *, mode: str | None = None, notes: str = '') -> dict:
        heartbeat = self.continuity.heartbeat(mode=mode, notes=notes)
        payload = {'kind': 'continuity_heartbeat', **heartbeat}
        self.kernel.record_evaluation('continuity', payload)
        return {'status': 'ok', 'heartbeat': heartbeat, **({'mode': heartbeat.get('mode'), 'heartbeat_at': heartbeat.get('heartbeat_at')})}

    def continuity_status(self) -> dict:
        watchdog = self.continuity.watchdog()
        return {'status': 'ok', **self.continuity.status(), 'watchdog': watchdog}

    def fixnet_register(
        self,
        *,
        title: str,
        error_type: str,
        error_signature: str,
        solution: str,
        summary: str = '',
        keywords: list[str] | None = None,
        context: dict | None = None,
        evidence: dict | None = None,
        linked_event_ids: list[str] | None = None,
        linked_run_ids: list[str] | None = None,
        linked_proposal_ids: list[str] | None = None,
        auto_embed: bool = False,
        archive_branch_id: str = 'archive_branch_main',
    ) -> dict:
        fix, novelty = self.fixnet.register_fix(
            title=title,
            error_type=error_type,
            error_signature=error_signature,
            solution=solution,
            summary=summary,
            keywords=keywords,
            context=context,
            evidence=evidence,
            linked_event_ids=linked_event_ids,
            linked_run_ids=linked_run_ids,
            linked_proposal_ids=linked_proposal_ids,
        )
        payload = {
            'kind': 'fixnet_fix',
            'fix_id': fix['fix_id'],
            'title': fix.get('title'),
            'error_type': fix.get('error_type'),
            'error_signature': fix.get('error_signature'),
            'summary': fix.get('summary'),
            'keywords': fix.get('keywords', []),
            'novelty': novelty,
        }
        self.kernel.record_evaluation('fixnet', payload)
        result = {'status': 'ok', 'fix': fix, 'novelty': novelty}
        if auto_embed:
            embedded = self.fixnet.embed(fix['fix_id'], archive_branch_id=archive_branch_id)
            embed_payload = {
                'kind': 'fixnet_embedded_archive',
                'fix_id': fix['fix_id'],
                'archive_branch_id': archive_branch_id,
                'archive_pack_id': embedded['archive_ref']['archive_pack_id'],
                'early_merge_at': embedded['archive_ref']['early_merge_at'],
                'last_sync_at': embedded['archive_ref']['last_sync_at'],
                'path': embedded['path'],
            }
            self.kernel.record_evaluation('fixnet', embed_payload)
            self.kernel.record_memory_update('fixnet', embed_payload)
            result['embedded'] = embedded
        return result

    def fixnet_embed(self, fix_id: str, *, archive_branch_id: str = 'archive_branch_main') -> dict:
        embedded = self.fixnet.embed(fix_id, archive_branch_id=archive_branch_id)
        embed_payload = {
            'kind': 'fixnet_embedded_archive',
            'fix_id': fix_id,
            'archive_branch_id': archive_branch_id,
            'archive_pack_id': embedded['archive_ref']['archive_pack_id'],
            'early_merge_at': embedded['archive_ref']['early_merge_at'],
            'last_sync_at': embedded['archive_ref']['last_sync_at'],
            'path': embedded['path'],
        }
        self.kernel.record_evaluation('fixnet', embed_payload)
        self.kernel.record_memory_update('fixnet', embed_payload)
        return {'status': 'ok', **embedded}

    def fixnet_stats(self) -> dict:
        return {'status': 'ok', **self.fixnet.stats()}

    def fixnet_sync_archive(self, fix_id: str, *, status: str = 'live', retirement_at: str | None = None) -> dict:
        synced = self.fixnet.sync_archive(fix_id, status=status, retirement_at=retirement_at)
        payload = {'kind': 'fixnet_embedded_archive', 'fix_id': fix_id, **synced}
        self.kernel.record_evaluation('fixnet', payload)
        self.kernel.record_memory_update('fixnet', payload)
        return {'status': 'ok', **synced}

    def record_tool_outcome(self, tool_name: str, *, succeeded: bool, notes: str = '', evidence: dict | None = None) -> dict:
        profile = self.trust.record_outcome(tool_name, succeeded=succeeded, notes=notes, evidence=evidence)
        payload = {'kind': 'tool_trust', **profile}
        self.kernel.record_evaluation('trust', payload)
        return {'status': 'ok', **profile}

    def tool_trust_stats(self) -> dict:
        return {'status': 'ok', **self.trust.stats()}

    def record_curriculum(self, *, theme: str, skill: str | None = None, failure_cluster: str | None = None, outcome: str = 'observed', notes: str = '') -> dict:
        data = self.curriculum.record(theme=theme, skill=skill, failure_cluster=failure_cluster, outcome=outcome, notes=notes)
        payload = {
            'kind': 'curriculum_memory',
            'theme': theme,
            'skill': skill,
            'failure_cluster': failure_cluster,
            'outcome': outcome,
            'notes': notes,
        }
        self.kernel.record_evaluation('curriculum', payload)
        return {'status': 'ok', **self.curriculum.stats()}

    def curriculum_stats(self) -> dict:
        return {'status': 'ok', **self.curriculum.stats()}

    def compile_goal(self, text: str, *, priority: int = 50) -> dict:
        goal = self.goals.compile_goal(text, priority=priority)
        payload = {'kind': 'goal_compilation', **goal.to_dict()}
        self.kernel.record_evaluation('goal-engine', payload)
        return {'status': 'ok', **goal.to_dict()}

    def shadow_handle(self, text: str, *, predicted_status: str = 'approve', confirm: bool = False) -> dict:
        predicted = {'status': predicted_status, 'text': text, 'branches': []}
        actual = self.handle(text, confirm=confirm)
        comparison = self.shadow.compare(predicted, actual).to_dict()
        payload = {'kind': 'shadow_execution', 'text': text, 'prediction': predicted, 'actual': actual, 'comparison': comparison}
        self.kernel.record_evaluation('shadow', payload)
        self.record_tool_outcome('shadow_execution', succeeded=bool(comparison.get('status_match')), notes='predicted vs actual comparison', evidence={'comparison': comparison})
        self.record_curriculum(theme='shadow_execution', skill='prediction_alignment', failure_cluster=None if comparison.get('status_match') else 'shadow_mismatch', outcome='success' if comparison.get('status_match') else 'failure')
        return {'status': 'ok', **payload}

    def review_improvement_run(self, run_id: str) -> dict:
        review = self.promotion_gate.review_run(self.workspace_root, run_id)
        payload = {'kind': 'self_improve_promotion_review', **review}
        self.kernel.record_evaluation('self-improve', payload)
        return {'status': 'ok' if review.get('approved') else 'error', **review}


    def configure_llamafile(
        self,
        *,
        binary_path: str | Path | None = None,
        model_path: str | Path | None = None,
        host: str = '127.0.0.1',
        port: int | None = None,
        startup_timeout: float = 20.0,
        idle_timeout: float | None = 120.0,
        keep_alive: bool = True,
        model_name: str | None = None,
        auto_manage_process: bool = True,
    ) -> None:
        manager = LlamafileProcessManager(
            binary_path=binary_path,
            model_path=model_path,
            host=host,
            port=port,
            startup_timeout=startup_timeout,
            keep_alive=keep_alive,
        )
        backend = LlamafileBackend(
            model=model_name,
            process_manager=manager,
            auto_manage_process=auto_manage_process,
            stream_idle_timeout=idle_timeout,
        )
        self.backends.register('llamafile', backend)

    def handle(self, text: str, confirm: bool = False) -> dict:
        input_event = self.kernel.record_input('operator', {'text': text, 'confirm': confirm})
        routed = self.router.classify(text)
        proposal = self.tools.proposal_for_intent(routed.intent_type, text, proposed_by='lucifer-runtime')
        proposal_event = self.kernel.record_proposal('lucifer-runtime', proposal, parent_event_id=input_event.event_id)
        branches = self.kernel.plan_branches('branch-planner', proposal, parent_event_id=proposal_event.event_id)
        plan = self.planner.build_plan(proposal, [b.to_dict() for b in branches])
        self.kernel.record_evaluation('planner', {'kind': 'plan_summary', 'proposal_id': proposal.proposal_id, **plan}, parent_event_id=proposal_event.event_id)
        decision = self.kernel.evaluate_proposal('arc-policy', proposal, parent_event_id=proposal_event.event_id)

        if decision.decision == Decision.DENY:
            return {'status': 'denied', 'reason': decision.reason, 'branches': [b.to_dict() for b in branches], 'plan': plan}
        if decision.decision == Decision.REQUIRE_CONFIRMATION and not confirm:
            return {
                'status': 'require_confirmation',
                'reason': decision.reason,
                'proposal_id': proposal.proposal_id,
                'branches': [b.to_dict() for b in branches],
                'plan': plan,
            }

        if decision.decision == Decision.REQUIRE_CONFIRMATION and confirm:
            self.kernel.force_decision(
                'operator',
                proposal.proposal_id,
                Decision.APPROVE,
                'Operator confirmed previously gated action.',
                parent_event_id=proposal_event.event_id,
            )
        return self._execute_proposal(proposal, parent_event_id=proposal_event.event_id, branches=branches, status_hint=('approve' if decision.decision == Decision.APPROVE else 'confirmed'), plan=plan)

    def stream_model(self, prompt: str, backend_name: str = 'llamafile', context: dict | None = None, options: dict | None = None) -> Iterator[dict]:
        # legacy generator kept for compatibility; no receipt/proposal lifecycle.
        input_event = self.kernel.record_input('operator', {'model_prompt': prompt, 'backend': backend_name})
        backend = self.backends.get(backend_name)
        self.kernel.record_evaluation('model-services', {'kind': 'stream_start', 'backend': backend_name, 'prompt_chars': len(prompt)}, parent_event_id=input_event.event_id)
        last_event: StreamEvent | None = None
        for event in backend.stream_generate(prompt, context=context, options=options):
            last_event = event
            payload = self._payload_from_stream_event(event)
            payload['hud'] = self.render_stream_hud(payload)
            if not event.done:
                self.kernel.record_evaluation('model-services', {'kind': 'stream_chunk', 'backend': backend_name, **payload}, parent_event_id=input_event.event_id)
            yield payload
        if last_event is None:
            last_event = StreamEvent(text='', sequence=0, chars_emitted=0, words_emitted=0, estimated_tokens=0, done=True)
        self.kernel.record_evaluation('model-services', {'kind': 'stream_complete', 'backend': backend_name, **self._payload_from_stream_event(last_event), 'session_totals': self._accumulate_session_metrics(last_event)}, parent_event_id=input_event.event_id)

    def prompt_model(
        self,
        prompt: str,
        *,
        backend_name: str = 'llamafile',
        context: dict | None = None,
        options: dict | None = None,
        stream: bool = False,
        on_chunk: Callable[[dict], None] | None = None,
    ) -> dict:
        input_event = self.kernel.record_input('operator', {'model_prompt': prompt, 'backend': backend_name})
        proposal = Proposal(
            action='model_prompt',
            capability=Capability(
                name='model.generate',
                description='Local model generation',
                risk=RiskLevel.LOW,
                side_effects=[],
                validators=[],
                dry_run_supported=False,
                requires_confirmation=False,
            ),
            params={'prompt': prompt, 'backend': backend_name},
            proposed_by='lucifer-runtime',
            rationale='Model prompt execution',
        )
        proposal_event = self.kernel.record_proposal('lucifer-runtime', proposal, parent_event_id=input_event.event_id)
        decision = self.kernel.evaluate_proposal('arc-policy', proposal, parent_event_id=proposal_event.event_id)
        if decision.decision == Decision.DENY:
            return {'status': 'denied', 'reason': decision.reason, 'proposal_id': proposal.proposal_id}

        backend = self.backends.get(backend_name)
        self.kernel.record_execution('lucifer-runtime', {'proposal_id': proposal.proposal_id, 'action': 'model_prompt', 'success': True, 'backend': backend_name, 'started': True}, parent_event_id=proposal_event.event_id)
        chunks: list[str] = []
        final_payload: dict | None = None
        interrupted = False
        interrupt_reason = ''
        try:
            for event in backend.stream_generate(prompt, context=context, options=options):
                payload = self._payload_from_stream_event(event)
                payload['hud'] = self.render_stream_hud(payload)
                payload['proposal_id'] = proposal.proposal_id
                payload['backend'] = backend_name
                final_payload = payload
                if payload.get('text'):
                    chunks.append(payload['text'])
                if not event.done:
                    self.kernel.record_evaluation('model-services', {'kind': 'stream_chunk', 'proposal_id': proposal.proposal_id, 'backend': backend_name, **payload}, parent_event_id=proposal_event.event_id)
                    if stream and on_chunk is not None:
                        on_chunk(payload)
                else:
                    self.kernel.record_evaluation('model-services', {'kind': 'stream_complete', 'proposal_id': proposal.proposal_id, 'backend': backend_name, **payload}, parent_event_id=proposal_event.event_id)
        except KeyboardInterrupt as exc:
            interrupted = True
            interrupt_reason = 'Operator interrupted local generation.'
            failure = self.failure_classifier.classify_exception(exc)
        except Exception as exc:  # pragma: no cover - defensive runtime path
            interrupted = True
            failure = self.failure_classifier.classify_exception(exc)
            interrupt_reason = f'Model generation failed: {exc}'
            fallback_mode = self.fallback_selector.choose(failure, 'model_prompt')
            if fallback_mode == 'deterministic_router':
                return self._complete_via_deterministic_fallback(prompt, interrupt_reason, proposal.proposal_id, parent_event_id=proposal_event.event_id)
            if fallback_mode == 'echo_stub':
                self._record_fallback(task_kind='model_prompt', proposal_id=proposal.proposal_id, original_mode='managed_llamafile', fallback_mode='echo_stub', reason=interrupt_reason, parent_event_id=proposal_event.event_id)
                stub_text = f'[fallback-echo] {prompt}'
                receipt = Receipt(
                    proposal_id=proposal.proposal_id,
                    success=True,
                    outputs={'backend': 'echo_stub', 'output_text': stub_text},
                    validator_results=[{'validator': 'fallback_echo_completed', 'passed': True}],
                )
                self.kernel.record_receipt('lucifer-runtime', receipt, parent_event_id=proposal_event.event_id)
                return {'status': 'completed_fallback', 'proposal_id': proposal.proposal_id, 'backend': 'echo_stub', 'output_text': stub_text, 'fallback_mode': 'echo_stub', 'fallback_reason': interrupt_reason}
        final_payload = dict(final_payload or {})
        final_payload['output_text'] = ''.join(chunks)
        final_payload['backend'] = backend_name
        final_payload['proposal_id'] = proposal.proposal_id
        final_payload['session_metrics'] = self.get_session_metrics()
        if interrupted:
            final_payload.setdefault('done', False)
            final_payload['status'] = 'partial_fallback'
            final_payload['interrupted'] = True
            self._record_fallback(task_kind='model_prompt', proposal_id=proposal.proposal_id, original_mode='managed_llamafile', fallback_mode='partial_receipt', reason=interrupt_reason, parent_event_id=proposal_event.event_id)
            self.kernel.record_evaluation('model-services', {
                'kind': 'model_prompt_interrupted',
                'proposal_id': proposal.proposal_id,
                'backend': backend_name,
                'reason': interrupt_reason,
                'partial_output_chars': len(final_payload['output_text']),
                'partial_output_words': len(final_payload['output_text'].split()),
            }, parent_event_id=proposal_event.event_id)
            receipt = Receipt(
                proposal_id=proposal.proposal_id,
                success=False,
                outputs={
                    'backend': backend_name,
                    'interrupted': True,
                    'output_text': final_payload['output_text'],
                    'reason': interrupt_reason,
                    'exact_prompt_tokens': final_payload.get('exact_prompt_tokens'),
                    'exact_completion_tokens': final_payload.get('exact_completion_tokens'),
                    'exact_total_tokens': final_payload.get('exact_total_tokens'),
                    'completion_chars': len(final_payload['output_text']),
                },
                validator_results=[{'validator': 'interruption_handled', 'passed': True}],
            )
            self.kernel.record_receipt('lucifer-runtime', receipt, parent_event_id=proposal_event.event_id)
            return final_payload

        stream_event = self._dict_to_stream_event(final_payload)
        final_payload['status'] = 'ok'
        self._accumulate_session_metrics(stream_event)
        self.kernel.record_evaluation('model-services', {
            'kind': 'model_prompt_complete',
            'proposal_id': proposal.proposal_id,
            'backend': backend_name,
            'output_chars': len(final_payload['output_text']),
            'output_words': len(final_payload['output_text'].split()),
            'exact_prompt_tokens': final_payload.get('exact_prompt_tokens'),
            'exact_completion_tokens': final_payload.get('exact_completion_tokens'),
            'exact_total_tokens': final_payload.get('exact_total_tokens'),
            'session_totals': self.get_session_metrics(),
        }, parent_event_id=proposal_event.event_id)
        receipt = Receipt(
            proposal_id=proposal.proposal_id,
            success=True,
            outputs={
                'backend': backend_name,
                'output_text': final_payload['output_text'],
                'exact_prompt_tokens': final_payload.get('exact_prompt_tokens'),
                'exact_completion_tokens': final_payload.get('exact_completion_tokens'),
                'exact_total_tokens': final_payload.get('exact_total_tokens'),
                'completion_chars': final_payload.get('completion_chars'),
                'completion_words': final_payload.get('completion_words'),
            },
            validator_results=[{'validator': 'model_prompt_completed', 'passed': True}],
        )
        self.kernel.record_receipt('lucifer-runtime', receipt, parent_event_id=proposal_event.event_id)
        return final_payload


    def _record_fallback(self, *, task_kind: str, proposal_id: str | None, original_mode: str, fallback_mode: str, reason: str, parent_event_id: str | None = None) -> None:
        """Persist fallback history so degraded completion is inspectable later."""
        record = self.continuations.finish(self.continuations.start(task_kind, fallback_mode, reason), 'completed_fallback')
        self.kernel.record_evaluation('resilience', {
            'kind': 'fallback_event',
            'task_kind': task_kind,
            'proposal_id': proposal_id,
            'original_mode': original_mode,
            'fallback_mode': fallback_mode,
            'reason': reason,
            **record.to_dict(),
        }, parent_event_id=parent_event_id)

    def _complete_via_deterministic_fallback(self, prompt: str, failure_reason: str, proposal_id: str, parent_event_id: str | None = None) -> dict:
        """Fallback from model generation to the deterministic router when the prompt is command-like."""
        fallback_mode = 'deterministic_router'
        self._record_fallback(task_kind='model_prompt', proposal_id=proposal_id, original_mode='managed_llamafile', fallback_mode=fallback_mode, reason=failure_reason, parent_event_id=parent_event_id)
        result = self.handle(prompt, confirm=False)
        result['status'] = 'completed_fallback'
        result['fallback_mode'] = fallback_mode
        result['fallback_reason'] = failure_reason
        result['proposal_id'] = proposal_id
        return result

    def run_benchmarks(self) -> dict:
        payload = self.benchmarks.run_smoke_suite(self.workspace_root)
        self.kernel.record_evaluation('self-improve', payload)
        return {'result': 'ok', **payload}


    def analyze_improvements(self) -> dict:
        state = self.kernel.state()
        payload = self.improvement_analyzer.analyze(state, self.workspace_root)
        self.kernel.record_evaluation('self-improve', {'kind': 'self_improve_analysis', **payload})
        return payload


    def plan_improvements(self, target_key: str | None = None) -> dict:
        state = self.kernel.state()
        analysis = self.improvement_analyzer.analyze(state, self.workspace_root)
        payload = self.improvement_planner.build_plan(analysis, self.workspace_root, target_key=target_key)
        self.kernel.record_evaluation('self-improve', {'kind': 'self_improve_plan', **payload})
        return payload

    def scaffold_improvement_run(self, target_key: str | None = None) -> dict:
        plan = self.plan_improvements(target_key=target_key)
        run = self.sandbox_manager.scaffold(self.workspace_root, plan)
        payload = {'kind': 'self_improve_run', 'plan': plan, **run.to_dict()}
        self.kernel.record_evaluation('self-improve', payload)
        return {'status': 'ok', 'plan': plan, 'run': run.to_dict()}


    def code_index(self, path: str) -> dict:
        payload = self.code_planner.plan_for_path(self.workspace_root, path, instruction='index file')
        self.kernel.record_evaluation('code-edit', {'kind': 'code_index', **payload})
        return payload

    def code_verify(self, path: str) -> dict:
        result = self.code_verifier.verify_file(self.workspace_root / path)
        payload = {'status': 'ok', **result}
        self.kernel.record_evaluation('code-edit', {'kind': 'code_verify', **payload})
        return payload

    def code_plan(self, path: str, instruction: str, symbol_name: str | None = None) -> dict:
        payload = self.code_planner.plan_for_path(self.workspace_root, path, instruction=instruction, symbol_name=symbol_name)
        self.kernel.record_evaluation('code-edit', {'kind': 'code_plan', **payload})
        return payload

    def code_replace_range(self, path: str, start_line: int, end_line: int, replacement_text: str, *, confirm: bool = False, expected_hash: str | None = None, reason: str = '') -> dict:
        proposal = Proposal(
            action='code_replace_range',
            capability=Capability(
                name='code.patch',
                description='Exact line-anchored code patch',
                risk=RiskLevel.MEDIUM,
                side_effects=['mutates code files'],
                validators=['line_anchor', 'workspace_guard', 'python_parse'],
                dry_run_supported=False,
                requires_confirmation=False,
            ),
            params={'path': path, 'start_line': start_line, 'end_line': end_line},
            proposed_by='lucifer-runtime',
            rationale=reason or 'Exact line-anchored code edit',
        )
        proposal_event = self.kernel.record_proposal('code-edit', proposal)
        branches = self.kernel.plan_branches('branch-planner', proposal, parent_event_id=proposal_event.event_id)
        plan = self.planner.build_plan(proposal, [b.to_dict() for b in branches])
        self.kernel.record_evaluation('planner', {'kind': 'plan_summary', 'proposal_id': proposal.proposal_id, **plan}, parent_event_id=proposal_event.event_id)
        decision = self.kernel.evaluate_proposal('arc-policy', proposal, parent_event_id=proposal_event.event_id)
        if decision.decision == Decision.DENY:
            return {'status': 'denied', 'reason': decision.reason, 'proposal_id': proposal.proposal_id}
        if decision.decision == Decision.REQUIRE_CONFIRMATION and not confirm:
            return {'status': 'require_confirmation', 'proposal_id': proposal.proposal_id, 'reason': decision.reason}
        if decision.decision == Decision.REQUIRE_CONFIRMATION and confirm:
            self.kernel.force_decision('operator', proposal.proposal_id, Decision.APPROVE, 'Operator confirmed code patch.', parent_event_id=proposal_event.event_id)
        result = self.patch_engine.apply(self.workspace_root, PatchOperation(kind=PatchKind.REPLACE_RANGE, path=path, replacement_text=replacement_text, start_line=start_line, end_line=end_line, expected_hash=expected_hash, reason=reason))
        self.kernel.record_execution('code-edit', {'proposal_id': proposal.proposal_id, 'action': proposal.action, 'success': result.success, 'path': path}, parent_event_id=proposal_event.event_id)
        receipt = Receipt(proposal_id=proposal.proposal_id, success=result.success, outputs=result.to_dict(), validator_results=result.verification['checks'])
        self.kernel.record_receipt('code-edit', receipt, parent_event_id=proposal_event.event_id)
        result_failure = self.failure_classifier.classify_patch_result(result.to_dict())
        if result_failure is not None:
            fallback_mode = self.fallback_selector.choose(result_failure, 'code_patch')
            if fallback_mode:
                self._record_fallback(task_kind='code_patch', proposal_id=proposal.proposal_id, original_mode='replace_range', fallback_mode=fallback_mode, reason=result_failure.reason, parent_event_id=proposal_event.event_id)
        self.kernel.record_evaluation('code-edit', {'kind': 'code_patch', 'proposal_id': proposal.proposal_id, **result.to_dict()}, parent_event_id=proposal_event.event_id)
        return {'status': 'ok' if result.success else 'completed_fallback', 'proposal_id': proposal.proposal_id, 'result': result.to_dict(), 'branches': [b.to_dict() for b in branches], 'plan': plan}

    def code_replace_symbol(self, path: str, symbol_name: str, replacement_text: str, *, confirm: bool = False, expected_hash: str | None = None, reason: str = '') -> dict:
        proposal = Proposal(
            action='code_replace_symbol',
            capability=Capability(
                name='code.patch',
                description='Exact symbol-anchored code patch',
                risk=RiskLevel.MEDIUM,
                side_effects=['mutates code files'],
                validators=['symbol_anchor', 'workspace_guard', 'python_parse'],
                dry_run_supported=False,
                requires_confirmation=False,
            ),
            params={'path': path, 'symbol_name': symbol_name},
            proposed_by='lucifer-runtime',
            rationale=reason or 'Exact symbol-anchored code edit',
        )
        proposal_event = self.kernel.record_proposal('code-edit', proposal)
        branches = self.kernel.plan_branches('branch-planner', proposal, parent_event_id=proposal_event.event_id)
        plan = self.planner.build_plan(proposal, [b.to_dict() for b in branches])
        self.kernel.record_evaluation('planner', {'kind': 'plan_summary', 'proposal_id': proposal.proposal_id, **plan}, parent_event_id=proposal_event.event_id)
        decision = self.kernel.evaluate_proposal('arc-policy', proposal, parent_event_id=proposal_event.event_id)
        if decision.decision == Decision.DENY:
            return {'status': 'denied', 'reason': decision.reason, 'proposal_id': proposal.proposal_id}
        if decision.decision == Decision.REQUIRE_CONFIRMATION and not confirm:
            return {'status': 'require_confirmation', 'proposal_id': proposal.proposal_id, 'reason': decision.reason}
        if decision.decision == Decision.REQUIRE_CONFIRMATION and confirm:
            self.kernel.force_decision('operator', proposal.proposal_id, Decision.APPROVE, 'Operator confirmed code patch.', parent_event_id=proposal_event.event_id)
        try:
            result = self.patch_engine.apply(self.workspace_root, PatchOperation(kind=PatchKind.REPLACE_SYMBOL, path=path, replacement_text=replacement_text, symbol_name=symbol_name, expected_hash=expected_hash, reason=reason))
        except Exception as exc:
            failure = self.failure_classifier.classify_exception(exc)
            fallback_mode = self.fallback_selector.choose(failure, 'code_patch')
            if fallback_mode == 'scaffold_manual_fix':
                self._record_fallback(task_kind='code_patch', proposal_id=proposal.proposal_id, original_mode='replace_symbol', fallback_mode=fallback_mode, reason=failure.reason, parent_event_id=proposal_event.event_id)
                return {'status': 'partial_fallback', 'proposal_id': proposal.proposal_id, 'reason': failure.reason, 'fallback_mode': fallback_mode, 'branches': [b.to_dict() for b in branches], 'plan': plan}
            raise
        self.kernel.record_execution('code-edit', {'proposal_id': proposal.proposal_id, 'action': proposal.action, 'success': result.success, 'path': path, 'symbol_name': symbol_name}, parent_event_id=proposal_event.event_id)
        receipt = Receipt(proposal_id=proposal.proposal_id, success=result.success, outputs=result.to_dict(), validator_results=result.verification['checks'])
        self.kernel.record_receipt('code-edit', receipt, parent_event_id=proposal_event.event_id)
        result_failure = self.failure_classifier.classify_patch_result(result.to_dict())
        if result_failure is not None:
            fallback_mode = self.fallback_selector.choose(result_failure, 'code_patch')
            if fallback_mode == 'scaffold_manual_fix':
                self._record_fallback(task_kind='code_patch', proposal_id=proposal.proposal_id, original_mode='replace_symbol', fallback_mode=fallback_mode, reason=result_failure.reason, parent_event_id=proposal_event.event_id)
        self.kernel.record_evaluation('code-edit', {'kind': 'code_patch', 'proposal_id': proposal.proposal_id, **result.to_dict()}, parent_event_id=proposal_event.event_id)
        return {'status': 'ok' if result.success else 'completed_fallback', 'proposal_id': proposal.proposal_id, 'result': result.to_dict(), 'branches': [b.to_dict() for b in branches], 'plan': plan}


    def apply_improvement_patch(
        self,
        run_id: str,
        *,
        path: str,
        replacement_text: str,
        symbol_name: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        expected_hash: str | None = None,
        rationale: str = '',
        validation_requested: bool = False,
    ) -> dict:
        """Apply a grounded patch inside a self-improvement worktree and record the result."""
        payload = self.improvement_executor.apply_patch(
            self.workspace_root,
            run_id,
            path=path,
            replacement_text=replacement_text,
            symbol_name=symbol_name,
            start_line=start_line,
            end_line=end_line,
            expected_hash=expected_hash,
            validation_requested=validation_requested,
            rationale=rationale,
        ).to_dict()
        event = {'kind': 'self_improve_patch', **payload}
        self.kernel.record_evaluation('self-improve', event)
        return {'status': 'ok', **payload}

    def execute_improvement_cycle(
        self,
        run_id: str,
        *,
        path: str,
        replacement_text: str,
        symbol_name: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        expected_hash: str | None = None,
        rationale: str = '',
        validate: bool = True,
        timeout: int = 120,
        promote: bool = False,
        force_promote: bool = False,
        quarantine_on_failure: bool = True,
    ) -> dict:
        """Run a full sandbox patch cycle: patch, validate, and optionally promote."""
        payload = self.improvement_executor.execute_cycle(
            self.workspace_root,
            run_id,
            path=path,
            replacement_text=replacement_text,
            symbol_name=symbol_name,
            start_line=start_line,
            end_line=end_line,
            expected_hash=expected_hash,
            rationale=rationale,
            validate=validate,
            timeout=timeout,
            promote=promote,
            force_promote=force_promote,
            quarantine_on_failure=quarantine_on_failure,
        )
        self.kernel.record_evaluation('self-improve', {'kind': 'self_improve_cycle', **payload})
        return payload

    def validate_improvement_run(self, run_id: str, timeout: int = 120) -> dict:
        result = self.promotion_gate.validate_run(self.workspace_root, run_id, timeout=timeout)
        payload = {'kind': 'self_improve_validation', **result.to_dict()}
        self.kernel.record_evaluation('self-improve', payload)

        # DARPA closure: automatically capture validation failures as FixNet repair knowledge.
        self.record_tool_outcome('self_improve_validation', succeeded=result.passed, notes=f'validation run {run_id}', evidence={'validation': result.to_dict()})
        self.record_curriculum(theme='self_improve', skill='validation', failure_cluster=None if result.passed else 'validation_failure', outcome='success' if result.passed else 'failure', notes=run_id)
        if not result.passed:
            failing = [c for c in result.command_results if not c.get('passed')]
            first = failing[0] if failing else {}
            signature = f"run:{run_id}|cmd:{first.get('command','unknown')}|rc:{first.get('returncode')}"
            emitted = self.fixnet_register(
                title='Self-improve validation failure',
                error_type='self_improve_validation',
                error_signature=signature,
                solution='Adjust patch and/or add regression tests until recommended_commands pass.',
                summary='Auto-emitted from PromotionGate validation failure.',
                keywords=['fixnet', 'self-improve', 'validation'],
                context={'run_id': run_id, 'failing_commands': failing},
                evidence={'validation': result.to_dict()},
                linked_run_ids=[run_id],
                auto_embed=True,
            )
            if emitted.get('fix'):
                self.fixnet_sync_archive(emitted['fix']['fix_id'], status='live')

        return {'status': 'ok', **result.to_dict()}

    def promote_improvement_run(self, run_id: str, *, force: bool = False) -> dict:
        try:
            result = self.promotion_gate.promote_run(self.workspace_root, run_id, force=force)
        except Exception as exc:
            # DARPA closure: promotion failures become repair knowledge too.
            emitted = self.fixnet_register(
                title='Self-improve promotion failure',
                error_type='self_improve_promotion',
                error_signature=f"run:{run_id}|force:{force}|exc:{type(exc).__name__}",
                solution='Fix validation failures or adjust evidence bundle before promotion.',
                summary=str(exc),
                keywords=['fixnet', 'self-improve', 'promotion'],
                context={'run_id': run_id, 'force': force},
                evidence={'exception': repr(exc)},
                linked_run_ids=[run_id],
                auto_embed=True,
            )
            self.record_tool_outcome('self_improve_promotion', succeeded=False, notes=f'promotion failed for {run_id}', evidence={'exception': repr(exc)})
            self.record_curriculum(theme='self_improve', skill='promotion', failure_cluster='promotion_failure', outcome='failure', notes=run_id)
            if emitted.get('fix'):
                self.fixnet_sync_archive(emitted['fix']['fix_id'], status='live')
            payload = {'kind': 'self_improve_promotion', 'run_id': run_id, 'forced': force, 'error': str(exc), 'exception': type(exc).__name__}
            self.kernel.record_evaluation('self-improve', payload)
            return {'status': 'error', **payload}
        payload = {'kind': 'self_improve_promotion', **result}
        self.kernel.record_evaluation('self-improve', payload)
        self.record_tool_outcome('self_improve_promotion', succeeded=True, notes=f'promotion succeeded for {run_id}', evidence={'promotion': result})
        self.record_curriculum(theme='self_improve', skill='promotion', failure_cluster=None, outcome='success', notes=run_id)
        return {'status': 'ok', **result}

    def generate_improvement_candidates(
        self,
        run_id: str,
        *,
        path: str,
        replacement_text: str,
        symbol_name: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        expected_hash: str | None = None,
        rationale: str = '',
    ) -> dict:
        payload = self.candidate_cycles.generate_candidates(
            self.workspace_root,
            run_id,
            path=path,
            replacement_text=replacement_text,
            symbol_name=symbol_name,
            start_line=start_line,
            end_line=end_line,
            expected_hash=expected_hash,
            rationale=rationale,
        )
        self.kernel.record_evaluation('self-improve', {'kind': 'self_improve_candidates', **payload})
        return payload

    def score_improvement_candidates(self, run_id: str, *, timeout: int = 120) -> dict:
        payload = self.candidate_cycles.score_candidates(self.workspace_root, run_id, timeout=timeout)
        self.kernel.record_evaluation('self-improve', {'kind': 'self_improve_candidate_scores', **payload})
        top = payload.get('best_candidate') or {}
        self.record_curriculum(theme='self_improve', skill='candidate_scoring', failure_cluster=None if top else 'missing_candidate_scores', outcome='success' if top else 'failure', notes=run_id)
        if top:
            self.fixnet_register(
                title='Self-improve candidate scoring',
                error_type='self_improve_candidates',
                error_signature=f"run:{run_id}|candidate:{top.get('candidate_id','unknown')}",
                solution='Prefer the highest-scoring validated candidate or iterate on failing variants.',
                summary='Auto-emitted from candidate scoring.',
                keywords=['fixnet','self-improve','candidates'],
                context={'run_id': run_id, 'best_candidate': top},
                evidence={'candidate_scores': payload},
                linked_run_ids=[run_id],
            )
        return payload


    def inject_improvement_fault(self, run_id: str, *, kind: str, path: str | None = None, note: str = '') -> dict:
        payload = self.adversarial.inject_fault(self.workspace_root, run_id, kind=kind, path=path, note=note).to_dict()
        self.kernel.record_evaluation('self-improve', {'kind': 'self_improve_fault', **payload})
        return {'status': 'ok', **payload}

    def run_improvement_adversarial_cycle(
        self,
        run_id: str,
        *,
        kind: str,
        path: str,
        replacement_text: str,
        symbol_name: str | None = None,
        start_line: int | None = None,
        end_line: int | None = None,
        expected_hash: str | None = None,
        rationale: str = '',
        timeout: int = 120,
    ) -> dict:
        payload = self.adversarial.adversarial_cycle(
            self.workspace_root,
            run_id,
            kind=kind,
            path=path,
            replacement_text=replacement_text,
            symbol_name=symbol_name,
            start_line=start_line,
            end_line=end_line,
            expected_hash=expected_hash,
            rationale=rationale,
            timeout=timeout,
        )
        self.kernel.record_evaluation('self-improve', {'kind': 'self_improve_adversarial_cycle', **payload})
        return payload
    def choose_best_improvement_candidate(self, run_id: str) -> dict:
        payload = self.candidate_cycles.choose_best_candidate(self.workspace_root, run_id)
        self.kernel.record_evaluation('self-improve', {'kind': 'self_improve_best_candidate', **payload})
        if payload.get('candidate_id'):
            self.record_curriculum(theme='self_improve', skill='candidate_selection', outcome='success', notes=run_id)
            self.fixnet_register(
                title='Self-improve best candidate selected',
                error_type='self_improve_best_candidate',
                error_signature=f"run:{run_id}|candidate:{payload.get('candidate_id')}",
                solution='Promote only after review and successful validation.',
                summary='Auto-emitted from best-candidate selection.',
                keywords=['fixnet','self-improve','best-candidate'],
                context={'run_id': run_id, 'candidate': payload},
                evidence={'best_candidate': payload},
                linked_run_ids=[run_id],
            )
        return payload

    def execute_best_improvement_candidate(
        self,
        run_id: str,
        *,
        timeout: int = 120,
        promote: bool = False,
        force_promote: bool = False,
        quarantine_on_failure: bool = True,
    ) -> dict:
        best = self.choose_best_improvement_candidate(run_id)
        if best.get('status') != 'ok':
            return best
        candidate = best['best_candidate']
        manifest = self.candidate_cycles.load_manifest(self.workspace_root, run_id)
        candidate_spec = next((item for item in manifest.get('candidates', []) if item.get('candidate_id') == candidate.get('candidate_id')), None)
        if candidate_spec is None:
            return {'status': 'not_found', 'run_id': run_id, 'reason': 'Best candidate missing from manifest.'}
        return self.execute_improvement_cycle(
            run_id,
            path=candidate_spec['path'],
            replacement_text=candidate_spec['replacement_text'],
            symbol_name=candidate_spec.get('symbol_name'),
            start_line=candidate_spec.get('start_line'),
            end_line=candidate_spec.get('end_line'),
            expected_hash=candidate_spec.get('expected_hash'),
            rationale=candidate_spec.get('rationale', ''),
            validate=True,
            timeout=timeout,
            promote=promote,
            force_promote=force_promote,
            quarantine_on_failure=quarantine_on_failure,
        )

    def approve(self, proposal_id: str) -> dict:
        proposal = self.kernel.get_proposal(proposal_id)
        if proposal is None:
            return {'status': 'not_found', 'proposal_id': proposal_id}
        decision = self.kernel.latest_decision(proposal_id)
        if decision is None or decision.decision != Decision.REQUIRE_CONFIRMATION:
            return {'status': 'not_pending', 'proposal_id': proposal_id}
        self.kernel.force_decision('operator', proposal_id, Decision.APPROVE, 'Operator approved pending proposal.')
        branches = self.kernel.get_branch_plan(proposal_id)
        plan = self.planner.build_plan(proposal, [b.to_dict() for b in branches])
        self.kernel.record_evaluation('planner', {'kind': 'plan_summary', 'proposal_id': proposal.proposal_id, **plan})
        return self._execute_proposal(proposal, branches=branches, status_hint='confirmed', plan=plan)

    def reject(self, proposal_id: str, reason: str = 'Operator rejected pending proposal.') -> dict:
        proposal = self.kernel.get_proposal(proposal_id)
        if proposal is None:
            return {'status': 'not_found', 'proposal_id': proposal_id}
        self.kernel.force_decision('operator', proposal_id, Decision.DENY, reason)
        return {'status': 'rejected', 'proposal_id': proposal_id, 'reason': reason}

    def rollback(self, proposal_id: str) -> dict:
        receipt = self.kernel.latest_receipt(proposal_id)
        if receipt is None:
            return {'status': 'not_found', 'proposal_id': proposal_id}
        undo = receipt.outputs.get('undo')
        if not undo:
            return {'status': 'no_rollback', 'proposal_id': proposal_id}
        result = self.tools.rollback(undo)
        return {'status': 'rolled_back' if result.success else 'rollback_failed', 'proposal_id': proposal_id, 'result': result.outputs}

    def replay_state_at_receipt(self, proposal_id: str):
        receipt_event = self.kernel.log.find_latest(kind=EventKind.RECEIPT, field_name='proposal_id', value=proposal_id)
        if receipt_event is None:
            return None
        return self.kernel.state_at(receipt_event.event_id)

    def _execute_proposal(self, proposal: Proposal, parent_event_id: Optional[str] = None, branches=None, status_hint: str = 'approve', plan: dict | None = None) -> dict:
        execution_result = self.tools.execute(proposal)
        self.kernel.record_execution('lucifer-runtime', {'proposal_id': proposal.proposal_id, 'action': proposal.action, 'success': execution_result.success}, parent_event_id=parent_event_id)
        validator_results = validate_result(proposal, execution_result)
        receipt = Receipt(proposal_id=proposal.proposal_id, success=execution_result.success, outputs=execution_result.outputs, validator_results=validator_results)
        self.kernel.record_receipt('lucifer-runtime', receipt, parent_event_id=parent_event_id)
        evaluation = self.evaluator.evaluate(proposal.proposal_id, validator_results, execution_result.outputs)
        self.kernel.record_evaluation('evaluator', {'kind': 'execution_evaluation', **evaluation}, parent_event_id=parent_event_id)
        return {
            'status': status_hint,
            'proposal_id': proposal.proposal_id,
            'result': execution_result.outputs,
            'validators': validator_results,
            'branches': [b.to_dict() for b in (branches or [])],
            'plan': plan,
            'evaluation': evaluation,
        }

    def _payload_from_stream_event(self, event: StreamEvent) -> dict:
        return {
            'text': event.text,
            'sequence': event.sequence,
            'chars_emitted': event.chars_emitted,
            'words_emitted': event.words_emitted,
            'estimated_tokens': event.estimated_tokens,
            'prompt_chars': event.prompt_chars,
            'prompt_words': event.prompt_words,
            'prompt_characters_used': event.prompt_characters_used,
            'prompt_word_tokens': event.prompt_word_tokens,
            'templated_prompt_chars': event.templated_prompt_chars,
            'completion_chars': event.completion_chars,
            'completion_words': event.completion_words,
            'completion_characters_generated': event.completion_characters_generated,
            'completion_word_tokens': event.completion_word_tokens,
            'exact_prompt_tokens': event.exact_prompt_tokens,
            'exact_completion_tokens': event.exact_completion_tokens,
            'exact_total_tokens': event.exact_total_tokens,
            'elapsed_seconds': event.elapsed_seconds,
            'chars_per_second': event.chars_per_second,
            'words_per_second': event.words_per_second,
            'done': event.done,
        }

    def _dict_to_stream_event(self, payload: dict) -> StreamEvent:
        return StreamEvent(
            text=payload.get('text', ''),
            sequence=int(payload.get('sequence', 0)),
            chars_emitted=int(payload.get('chars_emitted', 0)),
            words_emitted=int(payload.get('words_emitted', 0)),
            estimated_tokens=int(payload.get('estimated_tokens', 0)),
            prompt_chars=int(payload.get('prompt_chars', 0)),
            prompt_words=int(payload.get('prompt_words', 0)),
            prompt_characters_used=int(payload.get('prompt_characters_used', 0)),
            prompt_word_tokens=int(payload.get('prompt_word_tokens', 0)),
            templated_prompt_chars=int(payload.get('templated_prompt_chars', 0)),
            completion_chars=int(payload.get('completion_chars', 0)),
            completion_words=int(payload.get('completion_words', 0)),
            completion_characters_generated=int(payload.get('completion_characters_generated', 0)),
            completion_word_tokens=int(payload.get('completion_word_tokens', 0)),
            exact_prompt_tokens=int(payload.get('exact_prompt_tokens') or 0),
            exact_completion_tokens=int(payload.get('exact_completion_tokens') or 0),
            exact_total_tokens=int(payload.get('exact_total_tokens') or 0),
            elapsed_seconds=float(payload.get('elapsed_seconds', 0.0)),
            chars_per_second=float(payload.get('chars_per_second', 0.0)),
            words_per_second=float(payload.get('words_per_second', 0.0)),
            done=bool(payload.get('done', False)),
        )

    def _accumulate_session_metrics(self, event: StreamEvent) -> dict:
        self.session_metrics['requests'] += 1
        self.session_metrics['prompt_chars'] += event.prompt_chars
        self.session_metrics['prompt_words'] += event.prompt_words
        self.session_metrics['templated_prompt_chars'] += event.templated_prompt_chars
        self.session_metrics['completion_chars'] += event.completion_chars
        self.session_metrics['completion_words'] += event.completion_words
        self.session_metrics['exact_prompt_tokens'] += int(event.exact_prompt_tokens or 0)
        self.session_metrics['exact_completion_tokens'] += int(event.exact_completion_tokens or 0)
        self.session_metrics['exact_total_tokens'] += int(event.exact_total_tokens or 0)
        return dict(self.session_metrics)

    def get_session_metrics(self) -> dict:
        return dict(self.session_metrics)

    def render_stream_hud(self, payload: dict) -> str:
        return (
            f"seq={payload.get('sequence', 0)} | prompt chars={payload.get('prompt_chars', 0)}"
            f" | template chars={payload.get('templated_prompt_chars', 0)}"
            f" | out chars={payload.get('completion_chars', 0)} | out words={payload.get('completion_words', 0)}"
            f" | exact tokens={payload.get('exact_total_tokens')} | cps={payload.get('chars_per_second', 0.0):.2f}"
            f" | wps={payload.get('words_per_second', 0.0):.2f}"
        )
