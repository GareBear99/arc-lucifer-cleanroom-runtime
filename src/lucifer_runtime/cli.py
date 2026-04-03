"""Command-line entrypoint for the ARC Lucifer runtime and operational tooling."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
from pathlib import Path
from typing import Any

from arc_kernel.engine import KernelEngine
from dashboards.trace_viewer import render_trace
from dashboards.monitor import render_monitor_panel
from memory_subsystem import MemoryManager, RetentionConfig

from .config import CONFIG_ENV, default_config_path, default_runtime_dir, load_config, merge_settings, save_config
from self_improve import TrainingCorpusExporter
from model_services import ModelProfileStore
from .runtime import LuciferRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='lucifer', description='ARC Lucifer clean-room runtime CLI')
    parser.add_argument('--workspace', default='.', help='Workspace root for file and shell actions.')
    parser.add_argument('--db', default=None, help='Optional SQLite event log path.')
    parser.add_argument('--config', default=None, help='Optional JSON config path. Defaults to .arc_lucifer/config.json or ARC_LUCIFER_CONFIG.')
    sub = parser.add_subparsers(dest='command', required=True)

    read_p = sub.add_parser('read', help='Read a file inside the workspace.')
    read_p.add_argument('path')

    write_p = sub.add_parser('write', help='Write a file inside the workspace.')
    write_p.add_argument('path')
    write_p.add_argument('content')
    write_p.add_argument('--confirm', action='store_true', help='Confirm gated actions immediately.')

    delete_p = sub.add_parser('delete', help='Delete a file inside the workspace.')
    delete_p.add_argument('path')
    delete_p.add_argument('--confirm', action='store_true', help='Approve destructive action immediately.')

    shell_p = sub.add_parser('shell', help='Run an allowlisted shell command.')
    shell_p.add_argument('command_text', nargs=argparse.REMAINDER)

    prompt_p = sub.add_parser('prompt', help='Use the managed local model when configured, otherwise route through the deterministic runtime.')
    prompt_p.add_argument('text')
    prompt_p.add_argument('--confirm', action='store_true')
    prompt_p.add_argument('--stream', action='store_true', help='Print streamed text chunks live.')
    prompt_p.add_argument('--json-output', action='store_true', help='Print only the final JSON payload for model prompts.')
    prompt_p.add_argument('--system', default=None, help='Optional system prompt for model execution.')
    prompt_p.add_argument('--binary-path', default=None, help='Path to llamafile binary. Can also come from ARC_LUCIFER_LLAMAFILE_BINARY.')
    prompt_p.add_argument('--model-path', default=None, help='Path to GGUF model file. Can also come from ARC_LUCIFER_LLAMAFILE_MODEL.')
    prompt_p.add_argument('--model-name', default=None, help='Optional model name passed to the backend.')
    prompt_p.add_argument('--host', default=None, help='Override host. Defaults to 127.0.0.1 or ARC_LUCIFER_LLAMAFILE_HOST.')
    prompt_p.add_argument('--port', type=int, default=None, help='Override port or use ARC_LUCIFER_LLAMAFILE_PORT.')
    prompt_p.add_argument('--startup-timeout', type=float, default=None)
    prompt_p.add_argument('--idle-timeout', type=float, default=None)
    prompt_p.add_argument('--temperature', type=float, default=None)
    prompt_p.add_argument('--max-tokens', type=int, default=None)
    prompt_p.add_argument('--keep-alive', action='store_true', help='Keep the managed llamafile process alive between prompt calls.')

    approve_p = sub.add_parser('approve', help='Approve a pending proposal by ID.')
    approve_p.add_argument('proposal_id')

    reject_p = sub.add_parser('reject', help='Reject a pending proposal by ID.')
    reject_p.add_argument('proposal_id')
    reject_p.add_argument('--reason', default='Operator rejected pending proposal.')

    rollback_p = sub.add_parser('rollback', help='Rollback a previously completed proposal by receipt/undo data.')
    rollback_p.add_argument('proposal_id')

    code_p = sub.add_parser('code', help='Line-anchored and symbol-aware code editing commands.')
    code_sub = code_p.add_subparsers(dest='code_command', required=True)
    code_index = code_sub.add_parser('index', help='Index exact lines and symbols for a code file.')
    code_index.add_argument('path')
    code_verify = code_sub.add_parser('verify', help='Verify a code file and parser state.')
    code_verify.add_argument('path')
    code_plan = code_sub.add_parser('plan', help='Create a line/symbol-grounded edit plan.')
    code_plan.add_argument('path')
    code_plan.add_argument('instruction')
    code_plan.add_argument('--symbol', default=None)
    code_replace_range = code_sub.add_parser('replace-range', help='Replace an exact line range.')
    code_replace_range.add_argument('path')
    code_replace_range.add_argument('start_line', type=int)
    code_replace_range.add_argument('end_line', type=int)
    code_replace_range.add_argument('replacement_text')
    code_replace_range.add_argument('--expected-hash', default=None)
    code_replace_range.add_argument('--confirm', action='store_true')
    code_replace_range.add_argument('--reason', default='')
    code_replace_symbol = code_sub.add_parser('replace-symbol', help='Replace an exact Python symbol block.')
    code_replace_symbol.add_argument('path')
    code_replace_symbol.add_argument('symbol_name')
    code_replace_symbol.add_argument('replacement_text')
    code_replace_symbol.add_argument('--expected-hash', default=None)
    code_replace_symbol.add_argument('--confirm', action='store_true')
    code_replace_symbol.add_argument('--reason', default='')

    trace_p = sub.add_parser('trace', help='Render the current event trace to HTML.')
    trace_p.add_argument('--output', default='trace.html')

    export_p = sub.add_parser('export', help='Export event history or back up the SQLite database.')
    export_p.add_argument('--jsonl', default=None, help='Write all events as JSONL to this path.')
    export_p.add_argument('--sqlite-backup', default=None, help='Copy the SQLite database to this path.')

    import_p = sub.add_parser('import', help='Import previously exported JSONL events into the current workspace DB.')
    import_p.add_argument('--jsonl', required=True, help='JSONL file created by export --jsonl.')

    compact_p = sub.add_parser('compact', help='Checkpoint WAL and vacuum the SQLite event database.')

    info_p = sub.add_parser('info', help='Show runtime paths and database statistics.')

    monitor_p = sub.add_parser('monitor', help='Show a live operator monitor panel from persisted state.')
    sub.add_parser('failures', help='Show recorded fallback/degraded execution events.')
    monitor_p.add_argument('--watch', type=float, default=0.0, help='Refresh interval in seconds. 0 prints once.')
    monitor_p.add_argument('--iterations', type=int, default=1, help='How many refreshes to print when --watch is set.')

    doctor_p = sub.add_parser('doctor', help='Run production diagnostics for workspace, DB, and local model config.')
    doctor_p.add_argument('--json-output', action='store_true', help='Emit only the final JSON diagnostic payload.')

    config_p = sub.add_parser('config', help='Inspect or write the runtime JSON config file.')
    config_sub = config_p.add_subparsers(dest='config_command', required=True)
    config_show = config_sub.add_parser('show', help='Print the resolved config.')
    config_show.add_argument('--resolved', action='store_true', help='Include effective defaults.')
    config_init = config_sub.add_parser('init', help='Write a starter config file.')
    config_init.add_argument('--force', action='store_true', help='Overwrite existing config file.')

    model_p = sub.add_parser('model', help='Manage open-ended model backends and GGUF profiles.')
    model_sub = model_p.add_subparsers(dest='model_command', required=True)
    model_sub.add_parser('backends', help='List registered runtime backends.')
    model_profiles = model_sub.add_parser('profiles', help='List stored model profiles.')
    model_show = model_sub.add_parser('show-profile', help='Show a stored model profile.')
    model_show.add_argument('name')
    model_register = model_sub.add_parser('register-profile', help='Register a model profile for any local or external backend.')
    model_register.add_argument('name')
    model_register.add_argument('--backend-type', required=True, help='Examples: llamafile, gguf_local, openai_compatible, custom')
    model_register.add_argument('--binary-path', default=None)
    model_register.add_argument('--model-path', default=None)
    model_register.add_argument('--endpoint', default=None)
    model_register.add_argument('--notes', default='')
    model_register.add_argument('--intended-use', default='')
    model_register.add_argument('--training-ready', action='store_true')
    model_register.add_argument('--activate', action='store_true')
    model_register.add_argument('--param', action='append', default=[], help='Extra key=value metadata')
    model_activate = model_sub.add_parser('activate-profile', help='Set the active model profile.')
    model_activate.add_argument('name')
    model_compare = model_sub.add_parser('compare-profiles', help='Compare one or more stored profiles.')
    model_compare.add_argument('names', nargs='+')

    train_p = sub.add_parser('train', help='Export training corpora for future custom GGUF/model work.')
    train_sub = train_p.add_subparsers(dest='train_command', required=True)
    train_supervised = train_sub.add_parser('export-supervised', help='Export supervised training JSONL from persisted state.')
    train_supervised.add_argument('--output', required=True)
    train_pref = train_sub.add_parser('export-preferences', help='Export preference-pair JSONL from candidate scoring state.')
    train_pref.add_argument('--output', required=True)

    sub.add_parser('state', help='Print projected state as JSON.')
    sub.add_parser('commands', help='List the command surface.')
    sub.add_parser('bench', help='Run the built-in smoke benchmark suite.')
    self_p = sub.add_parser('self-improve', help='Analyze, plan, and scaffold improvement runs from persisted state.')
    self_sub = self_p.add_subparsers(dest='self_command', required=True)
    self_sub.add_parser('analyze', help='Summarize the next prioritized engineering targets from current state.')
    self_plan = self_sub.add_parser('plan', help='Turn current improvement targets into a concrete repo plan.')
    self_plan.add_argument('--target-key', default=None, help='Optional target key from self-improve analyze.')
    self_scaffold = self_sub.add_parser('scaffold', help='Create a self-improvement sandbox/worktree from the current plan.')
    self_scaffold.add_argument('--target-key', default=None, help='Optional target key from self-improve analyze.')
    self_validate = self_sub.add_parser('validate-run', help='Run manifest validation commands inside a self-improvement worktree.')
    self_validate.add_argument('run_id')
    self_validate.add_argument('--timeout', type=int, default=120)
    self_promote = self_sub.add_parser('promote', help='Promote a validated self-improvement worktree back into the repo.')
    self_promote.add_argument('run_id')
    self_promote.add_argument('--force', action='store_true')
    self_patch = self_sub.add_parser('apply-patch', help='Apply an exact patch inside a self-improvement worktree.')
    self_patch.add_argument('run_id')
    self_patch.add_argument('--path', required=True)
    self_patch.add_argument('--replacement', required=True)
    self_patch.add_argument('--symbol', default=None)
    self_patch.add_argument('--start-line', type=int, default=None)
    self_patch.add_argument('--end-line', type=int, default=None)
    self_patch.add_argument('--expected-hash', default=None)
    self_patch.add_argument('--reason', default='')
    self_patch.add_argument('--validate', action='store_true')
    self_candidates = self_sub.add_parser('generate-candidates', help='Create deterministic candidate patches for a self-improvement run.')
    self_candidates.add_argument('run_id')
    self_candidates.add_argument('--path', required=True)
    self_candidates.add_argument('--replacement', required=True)
    self_candidates.add_argument('--symbol', default=None)
    self_candidates.add_argument('--start-line', type=int, default=None)
    self_candidates.add_argument('--end-line', type=int, default=None)
    self_candidates.add_argument('--expected-hash', default=None)
    self_candidates.add_argument('--reason', default='')
    self_score = self_sub.add_parser('score-candidates', help='Validate and score generated candidate patches.')
    self_score.add_argument('run_id')
    self_score.add_argument('--timeout', type=int, default=120)
    self_best = self_sub.add_parser('best-candidate', help='Show the best currently scored candidate.')
    self_best.add_argument('run_id')
    self_exec_best = self_sub.add_parser('execute-best', help='Execute the best scored candidate in the main run worktree.')
    self_exec_best.add_argument('run_id')
    self_exec_best.add_argument('--timeout', type=int, default=120)
    self_exec_best.add_argument('--promote', action='store_true')
    self_exec_best.add_argument('--force-promote', action='store_true')
    self_exec_best.add_argument('--no-quarantine', action='store_true')
    self_fault = self_sub.add_parser('inject-fault', help='Inject a deterministic failure into a self-improvement run worktree.')
    self_fault.add_argument('run_id')
    self_fault.add_argument('--kind', required=True, choices=['delete_target_file', 'python_syntax_break', 'force_validation_failure', 'corrupt_candidate_tree'])
    self_fault.add_argument('--path', default=None)
    self_fault.add_argument('--note', default='')
    self_adv = self_sub.add_parser('adversarial-cycle', help='Inject a fault and execute a validation cycle under stress.')
    self_adv.add_argument('run_id')
    self_adv.add_argument('--kind', required=True, choices=['delete_target_file', 'python_syntax_break', 'force_validation_failure', 'corrupt_candidate_tree'])
    self_adv.add_argument('--path', required=True)
    self_adv.add_argument('--replacement', required=True)
    self_adv.add_argument('--symbol', default=None)
    self_adv.add_argument('--start-line', type=int, default=None)
    self_adv.add_argument('--end-line', type=int, default=None)
    self_adv.add_argument('--expected-hash', default=None)
    self_adv.add_argument('--reason', default='')
    self_adv.add_argument('--timeout', type=int, default=120)
    self_cycle = self_sub.add_parser('execute-cycle', help='Patch, validate, and optionally promote a self-improvement run.')
    self_cycle.add_argument('run_id')
    self_cycle.add_argument('--path', required=True)
    self_cycle.add_argument('--replacement', required=True)
    self_cycle.add_argument('--symbol', default=None)
    self_cycle.add_argument('--start-line', type=int, default=None)
    self_cycle.add_argument('--end-line', type=int, default=None)
    self_cycle.add_argument('--expected-hash', default=None)
    self_cycle.add_argument('--reason', default='')
    self_cycle.add_argument('--timeout', type=int, default=120)
    self_cycle.add_argument('--no-validate', action='store_true')
    self_cycle.add_argument('--promote', action='store_true')
    self_cycle.add_argument('--force-promote', action='store_true')
    self_cycle.add_argument('--no-quarantine', action='store_true')
    self_review = self_sub.add_parser('review-run', help='Review the promotion evidence bundle for a self-improvement run.')
    self_review.add_argument('run_id')

    fixnet_p = sub.add_parser('fixnet', help='FixNet repair intelligence: storage, consensus, novelty, and embedded archive mirrors.')
    fixnet_sub = fixnet_p.add_subparsers(dest='fixnet_command', required=True)

    fixnet_register = fixnet_sub.add_parser('register', help='Register a fix with semantic lineage and novelty scoring.')
    fixnet_register.add_argument('--title', required=True)
    fixnet_register.add_argument('--error-type', required=True)
    fixnet_register.add_argument('--error-signature', required=True)
    fixnet_register.add_argument('--solution', required=True)
    fixnet_register.add_argument('--summary', default='')
    fixnet_register.add_argument('--keywords', default='')
    fixnet_register.add_argument('--context-json', default='{}')
    fixnet_register.add_argument('--evidence-json', default='{}')
    fixnet_register.add_argument('--linked-event-id', action='append', default=[])
    fixnet_register.add_argument('--linked-run-id', action='append', default=[])
    fixnet_register.add_argument('--linked-proposal-id', action='append', default=[])
    fixnet_register.add_argument('--auto-embed', action='store_true')
    fixnet_register.add_argument('--archive-branch-id', default='archive_branch_main')

    fixnet_embed = fixnet_sub.add_parser('embed', help='Embed an existing fix into the archive-visible mirror.')
    fixnet_embed.add_argument('fix_id')
    fixnet_embed.add_argument('--archive-branch-id', default='archive_branch_main')

    fixnet_stats = fixnet_sub.add_parser('stats', help='Show FixNet statistics and consensus tier counts.')

    fixnet_sync = fixnet_sub.add_parser('sync-archive', help='Update live-linked embedded archive metadata for an existing fix.')
    fixnet_sync.add_argument('fix_id')
    fixnet_sync.add_argument('--status', default='live')
    fixnet_sync.add_argument('--retirement-at', default=None)

    trust_p = sub.add_parser('trust', help='Record or inspect tool/model trust profiles.')
    trust_sub = trust_p.add_subparsers(dest='trust_command', required=True)
    trust_record = trust_sub.add_parser('record', help='Record a tool or subsystem outcome.')
    trust_record.add_argument('tool_name')
    trust_record.add_argument('--status', choices=['success', 'failure'], required=True)
    trust_record.add_argument('--notes', default='')
    trust_record.add_argument('--evidence-json', default='{}')
    trust_sub.add_parser('stats', help='Show trust profile statistics.')

    curriculum_p = sub.add_parser('curriculum', help='Record or inspect long-horizon curriculum memory.')
    curriculum_sub = curriculum_p.add_subparsers(dest='curriculum_command', required=True)
    curriculum_record = curriculum_sub.add_parser('record', help='Record a curriculum theme, skill, or failure cluster.')
    curriculum_record.add_argument('--theme', required=True)
    curriculum_record.add_argument('--skill', default=None)
    curriculum_record.add_argument('--failure-cluster', default=None)
    curriculum_record.add_argument('--outcome', default='observed')
    curriculum_record.add_argument('--notes', default='')
    curriculum_sub.add_parser('stats', help='Show curriculum memory statistics.')

    directive_p = sub.add_parser('directive', help='Persist long-lived operator directives for the runtime.')
    directive_sub = directive_p.add_subparsers(dest='directive_command', required=True)
    directive_add = directive_sub.add_parser('add', help='Add an active directive to the directive ledger.')
    directive_add.add_argument('--title', required=True)
    directive_add.add_argument('--instruction', required=True)
    directive_add.add_argument('--priority', type=int, default=50)
    directive_add.add_argument('--scope', default='global')
    directive_add.add_argument('--constraints', default='')
    directive_add.add_argument('--success-conditions', default='')
    directive_add.add_argument('--abort-conditions', default='')
    directive_add.add_argument('--persistence-mode', default='forever')
    directive_add.add_argument('--issuer', default='operator')
    directive_add.add_argument('--supersedes', default=None)
    directive_complete = directive_sub.add_parser('complete', help='Mark a directive complete or superseded.')
    directive_complete.add_argument('directive_id')
    directive_complete.add_argument('--status', default='complete')
    directive_sub.add_parser('stats', help='Show directive ledger status.')

    continuity_p = sub.add_parser('continuity', help='Boot, heartbeat, and inspect runtime continuity state.')
    continuity_sub = continuity_p.add_subparsers(dest='continuity_command', required=True)
    continuity_boot = continuity_sub.add_parser('boot', help='Record a continuity boot receipt and choose primary/fallback mode.')
    continuity_boot.add_argument('--fallback-available', action='store_true')
    continuity_boot.add_argument('--notes', default='')
    continuity_heartbeat = continuity_sub.add_parser('heartbeat', help='Update continuity heartbeat state.')
    continuity_heartbeat.add_argument('--mode', default=None)
    continuity_heartbeat.add_argument('--notes', default='')
    continuity_sub.add_parser('status', help='Show continuity identity, boot receipts, and watchdog health.')


    goal_p = sub.add_parser('goal', help='Compile operator intent into a structured goal contract.')
    goal_p.add_argument('text')
    goal_p.add_argument('--priority', type=int, default=50)

    shadow_p = sub.add_parser('shadow', help='Run a shadow predicted-vs-actual comparison for a command.')
    shadow_p.add_argument('text')
    shadow_p.add_argument('--predicted-status', default='approve')
    shadow_p.add_argument('--confirm', action='store_true')


    memory_p = sub.add_parser('memory', help='Manage live, warm, and archived memory tiers.')
    memory_sub = memory_p.add_subparsers(dest='memory_command', required=True)
    memory_status = memory_sub.add_parser('status', help='Show archive manifests and memory update history.')
    memory_archive = memory_sub.add_parser('archive-now', help='Mirror a memory item into the archive branch early while keeping it live until its scheduled retirement date.')
    memory_archive.add_argument('event_id')
    memory_archive.add_argument('--reason', default='manual_override')
    memory_archive.add_argument('--archive-branch-id', default='archive_branch_main')
    memory_sync = memory_sub.add_parser('sync', help='Sync mirrored live memory into the archive branch.')
    memory_sync.add_argument('--event-id', default=None)
    memory_search = memory_sub.add_parser('search', help='Search readable live/archive memory using title, summary, and keyword ranking.')
    memory_search.add_argument('query')
    memory_search.add_argument('--limit', type=int, default=10)
    return parser


def resolve_config_path(args: argparse.Namespace) -> Path:
    explicit = args.config or os.getenv(CONFIG_ENV)
    if explicit:
        return Path(explicit).expanduser().resolve()
    return default_config_path(args.workspace)


def load_runtime_config(args: argparse.Namespace) -> tuple[Path, dict[str, Any]]:
    config_path = resolve_config_path(args)
    return config_path, load_config(config_path)


def default_db_path(workspace: str | Path) -> Path:
    runtime_dir = default_runtime_dir(workspace)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / 'events.sqlite3'


def effective_settings(args: argparse.Namespace, config: dict[str, Any]) -> dict[str, Any]:
    cli = {
        'workspace': args.workspace,
        'db': args.db,
    }
    return merge_settings(config, cli)


def runtime_from_args(args: argparse.Namespace) -> LuciferRuntime:
    _config_path, config = load_runtime_config(args)
    settings = effective_settings(args, config)
    db_raw = settings.get('db')
    db_path = Path(db_raw).expanduser().resolve() if db_raw else default_db_path(settings.get('workspace', args.workspace))
    kernel = KernelEngine(db_path=db_path)
    return LuciferRuntime(kernel=kernel, workspace_root=settings.get('workspace', args.workspace))


def _print_json(data: dict[str, Any]) -> int:
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0 if data.get('status') not in {'denied', 'error', 'not_found', 'not_pending'} else 1


def _env_or_default(cli_value: Any, env_name: str, default: Any = None) -> Any:
    if cli_value is not None:
        return cli_value
    return os.getenv(env_name, default)


def _model_settings_from_args(args: argparse.Namespace) -> dict[str, Any]:
    config_path, config = load_runtime_config(args)
    model_config = dict(config.get('model', {}))
    active_profile = ModelProfileStore(default_runtime_dir(args.workspace)).active_profile() or {}
    profile_settings = {
        'binary_path': active_profile.get('binary_path'),
        'model_path': active_profile.get('model_path'),
        'model_name': active_profile.get('name'),
        'endpoint': active_profile.get('endpoint'),
        'backend_type': active_profile.get('backend_type'),
    }
    return merge_settings(model_config, profile_settings, {
        'binary_path': getattr(args, 'binary_path', None),
        'model_path': getattr(args, 'model_path', None),
        'model_name': getattr(args, 'model_name', None),
        'host': getattr(args, 'host', None),
        'port': getattr(args, 'port', None),
        'startup_timeout': getattr(args, 'startup_timeout', None),
        'idle_timeout': getattr(args, 'idle_timeout', None),
        'keep_alive': getattr(args, 'keep_alive', False) if getattr(args, 'keep_alive', False) else None,
        'temperature': getattr(args, 'temperature', None),
        'max_tokens': getattr(args, 'max_tokens', None),
        'use_model': None,
        'config_path': str(config_path),
    })


def _prompt_should_use_model(args: argparse.Namespace) -> bool:
    settings = _model_settings_from_args(args)
    return any([
        settings.get('binary_path') or _env_or_default(None, 'ARC_LUCIFER_LLAMAFILE_BINARY'),
        settings.get('model_path') or _env_or_default(None, 'ARC_LUCIFER_LLAMAFILE_MODEL'),
        settings.get('endpoint'),
        settings.get('use_model') or _env_or_default(None, 'ARC_LUCIFER_USE_MODEL'),
    ])


def _configure_model_runtime(runtime: LuciferRuntime, args: argparse.Namespace) -> None:
    settings = _model_settings_from_args(args)
    binary_path = _env_or_default(settings.get('binary_path'), 'ARC_LUCIFER_LLAMAFILE_BINARY')
    model_path = _env_or_default(settings.get('model_path'), 'ARC_LUCIFER_LLAMAFILE_MODEL')
    host = _env_or_default(settings.get('host'), 'ARC_LUCIFER_LLAMAFILE_HOST', '127.0.0.1')
    port = _env_or_default(settings.get('port'), 'ARC_LUCIFER_LLAMAFILE_PORT')
    startup_timeout = float(_env_or_default(settings.get('startup_timeout'), 'ARC_LUCIFER_LLAMAFILE_STARTUP_TIMEOUT', 20.0))
    idle_timeout_raw = _env_or_default(settings.get('idle_timeout'), 'ARC_LUCIFER_LLAMAFILE_IDLE_TIMEOUT', 120.0)
    idle_timeout = None if str(idle_timeout_raw).lower() == 'none' else float(idle_timeout_raw)
    runtime.configure_llamafile(
        binary_path=binary_path,
        model_path=model_path,
        host=str(host),
        port=int(port) if port not in (None, '') else None,
        startup_timeout=startup_timeout,
        idle_timeout=idle_timeout,
        keep_alive=bool(settings.get('keep_alive') or str(os.getenv('ARC_LUCIFER_LLAMAFILE_KEEP_ALIVE', '')).lower() in {'1', 'true', 'yes'}),
        model_name=settings.get('model_name'),
    )


def _run_prompt(runtime: LuciferRuntime, args: argparse.Namespace) -> int:
    if not _prompt_should_use_model(args):
        return _print_json(runtime.handle(args.text, confirm=args.confirm))

    _configure_model_runtime(runtime, args)
    context = {'system': args.system or ''}
    options: dict[str, Any] = {}
    if args.temperature is not None:
        options['temperature'] = args.temperature
    if args.max_tokens is not None:
        options['max_tokens'] = args.max_tokens

    def on_chunk(payload: dict[str, Any]) -> None:
        if payload.get('text'):
            print(payload['text'], end='', flush=True)

    result = runtime.prompt_model(
        args.text,
        context=context,
        options=options,
        stream=args.stream and not args.json_output,
        on_chunk=on_chunk if args.stream and not args.json_output else None,
    )
    if args.stream and not args.json_output:
        print()
    return _print_json(result)




def _doctor(runtime: LuciferRuntime, args: argparse.Namespace) -> dict[str, Any]:
    config_path, config = load_runtime_config(args)
    db_path = runtime.kernel.db_path
    runtime_dir = default_runtime_dir(args.workspace)
    model_settings = _model_settings_from_args(args)
    binary_path = _env_or_default(model_settings.get('binary_path'), 'ARC_LUCIFER_LLAMAFILE_BINARY')
    model_path = _env_or_default(model_settings.get('model_path'), 'ARC_LUCIFER_LLAMAFILE_MODEL')
    checks: list[dict[str, Any]] = []

    def add_check(name: str, ok: bool, detail: str, level: str = 'error') -> None:
        checks.append({'name': name, 'ok': ok, 'detail': detail, 'level': level})

    add_check('python_version', tuple(map(int, platform.python_version_tuple()[:2])) >= (3, 11), f'Python {platform.python_version()}')
    add_check('workspace_exists', Path(args.workspace).expanduser().resolve().exists(), f'workspace={Path(args.workspace).expanduser().resolve()}')
    runtime_dir.mkdir(parents=True, exist_ok=True)
    add_check('runtime_dir_writable', os.access(runtime_dir, os.W_OK), f'runtime_dir={runtime_dir}')
    stats = runtime.kernel.stats()
    add_check('db_configured', db_path is not None, f'db_path={db_path}')
    if db_path is not None:
        db_parent = Path(db_path).parent
        db_parent.mkdir(parents=True, exist_ok=True)
        add_check('db_parent_writable', os.access(db_parent, os.W_OK), f'db_parent={db_parent}')
    add_check('config_present', config_path.exists(), f'config_path={config_path}', level='warn')
    add_check('llamafile_binary', bool(binary_path) and Path(str(binary_path)).expanduser().exists(), f'binary_path={binary_path}', level='warn')
    add_check('llamafile_model', bool(model_path) and Path(str(model_path)).expanduser().exists(), f'model_path={model_path}', level='warn')
    if binary_path and Path(str(binary_path)).expanduser().exists():
        add_check('llamafile_executable', os.access(Path(str(binary_path)).expanduser(), os.X_OK), f'binary_path={binary_path}', level='warn')
    lucifer_bin = shutil.which('lucifer')
    add_check('lucifer_on_path', bool(lucifer_bin), f'lucifer={lucifer_bin}', level='warn')
    summary = {
        'ok': all(check['ok'] or check['level'] == 'warn' for check in checks),
        'errors': sum(1 for check in checks if not check['ok'] and check['level'] != 'warn'),
        'warnings': sum(1 for check in checks if not check['ok'] and check['level'] == 'warn'),
    }
    return {
        'status': 'ok' if summary['errors'] == 0 else 'error',
        'summary': summary,
        'checks': checks,
        'paths': {
            'workspace': str(Path(args.workspace).expanduser().resolve()),
            'runtime_dir': str(runtime_dir),
            'db_path': str(db_path) if db_path is not None else None,
            'config_path': str(config_path),
        },
        'db_stats': stats,
        'config': config,
    }


def _config_command(args: argparse.Namespace) -> dict[str, Any]:
    config_path, config = load_runtime_config(args)
    if args.config_command == 'show':
        payload = {'status': 'ok', 'config_path': str(config_path), 'config': config}
        if args.resolved:
            payload['resolved'] = merge_settings(config, {'workspace': args.workspace, 'db': str(default_db_path(args.workspace))})
        return payload
    if args.config_command == 'init':
        if config_path.exists() and not args.force:
            return {'status': 'exists', 'config_path': str(config_path), 'reason': 'Config already exists. Use --force to overwrite.'}
        starter = {
            'workspace': str(Path(args.workspace).expanduser().resolve()),
            'db': str(default_db_path(args.workspace)),
            'model': {
                'binary_path': '/absolute/path/to/llamafile',
                'model_path': '/absolute/path/to/model.gguf',
                'host': '127.0.0.1',
                'port': 8080,
                'startup_timeout': 20.0,
                'idle_timeout': 120.0,
                'keep_alive': False,
            },
        }
        written = save_config(config_path, starter)
        return {'status': 'ok', 'config_path': str(written), 'config': starter}
    return {'status': 'error', 'reason': f'Unsupported config command: {args.config_command}'}


def _export_command(runtime: LuciferRuntime, args: argparse.Namespace) -> dict[str, Any]:
    if not args.jsonl and not args.sqlite_backup:
        return {'status': 'error', 'reason': 'Provide --jsonl and/or --sqlite-backup.'}
    payload: dict[str, Any] = {'status': 'ok'}
    if args.jsonl:
        payload['jsonl_path'] = str(runtime.kernel.export_events_jsonl(args.jsonl).resolve())
    if args.sqlite_backup:
        payload['sqlite_backup_path'] = str(runtime.kernel.backup_sqlite(args.sqlite_backup).resolve())
    payload['db_stats'] = runtime.kernel.stats()
    return payload


def _import_command(runtime: LuciferRuntime, args: argparse.Namespace) -> dict[str, Any]:
    imported = runtime.kernel.import_events_jsonl(args.jsonl)
    return {'status': 'ok', 'imported_events': imported, 'db_stats': runtime.kernel.stats()}


def _compact_command(runtime: LuciferRuntime) -> dict[str, Any]:
    result = runtime.kernel.compact()
    return {'status': 'ok', **result}


def _info_command(runtime: LuciferRuntime, args: argparse.Namespace) -> dict[str, Any]:
    config_path, _config = load_runtime_config(args)
    return {
        'status': 'ok',
        'paths': {
            'workspace': str(Path(args.workspace).expanduser().resolve()),
            'runtime_dir': str(default_runtime_dir(args.workspace)),
            'db_path': str(runtime.kernel.db_path) if runtime.kernel.db_path else None,
            'config_path': str(config_path),
        },
        'db_stats': runtime.kernel.stats(),
    }


def _monitor_command(runtime: LuciferRuntime, args: argparse.Namespace) -> int:
    import time

    def build_payload() -> dict[str, Any]:
        info = _info_command(runtime, args)
        state = runtime.kernel.state().__dict__
        return {'status': 'ok', 'panel': render_monitor_panel(info, state), 'info': info, 'state': state}

    if args.watch and args.watch > 0:
        iterations = max(1, int(args.iterations))
        for idx in range(iterations):
            payload = build_payload()
            print(payload['panel'])
            if idx < iterations - 1:
                print('\n' + '=' * 72 + '\n')
                time.sleep(args.watch)
        return 0
    return _print_json(build_payload())



def _memory_manager(args: argparse.Namespace, runtime: LuciferRuntime) -> MemoryManager:
    runtime_dir = default_runtime_dir(args.workspace)
    retention_cfg = load_runtime_config(args)[1].get('retention', {})
    config = RetentionConfig(
        hot_days=int(retention_cfg.get('hot_days', 30)),
        warm_days=int(retention_cfg.get('warm_days', 180)),
        access_grace_days=int(retention_cfg.get('access_grace_days', 45)),
    )
    return MemoryManager(runtime.kernel, runtime_dir / 'memory', config)


def _memory_command(runtime: LuciferRuntime, args: argparse.Namespace) -> int:
    manager = _memory_manager(args, runtime)
    if args.memory_command == 'status':
        return _print_json(manager.memory_status())
    if args.memory_command == 'archive-now':
        return _print_json(manager.archive_now_but_keep_live(args.event_id, reason=args.reason, archive_branch_id=args.archive_branch_id))
    if args.memory_command == 'sync':
        return _print_json(manager.sync_live_mirrors(event_id=args.event_id))
    if args.memory_command == 'search':
        return _print_json(manager.search_memory(args.query, limit=args.limit))
    return _print_json({'status': 'error', 'reason': f'unknown memory command: {args.memory_command}'})


def _model_profile_store(args: argparse.Namespace) -> ModelProfileStore:
    return ModelProfileStore(default_runtime_dir(args.workspace))


def _parse_kv_pairs(items: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in items:
        if '=' not in item:
            raise ValueError(f'Expected key=value pair, got: {item}')
        key, value = item.split('=', 1)
        result[key.strip()] = value.strip()
    return result


def _model_command(runtime: LuciferRuntime, args: argparse.Namespace) -> int:
    store = _model_profile_store(args)
    if args.model_command == 'backends':
        return _print_json({'status': 'ok', 'backends': runtime.backends.names()})
    if args.model_command == 'profiles':
        return _print_json(store.list_profiles())
    if args.model_command == 'show-profile':
        return _print_json(store.show_profile(args.name))
    if args.model_command == 'register-profile':
        extra = _parse_kv_pairs(args.param)
        profile = {
            'backend_type': args.backend_type,
            'binary_path': args.binary_path,
            'model_path': args.model_path,
            'endpoint': args.endpoint,
            'notes': args.notes,
            'intended_use': args.intended_use,
            'training_ready': args.training_ready,
            'metadata': extra,
        }
        return _print_json(store.register_profile(args.name, profile, activate=args.activate))
    if args.model_command == 'activate-profile':
        return _print_json(store.activate_profile(args.name))
    if args.model_command == 'compare-profiles':
        return _print_json(store.compare_profiles(args.names))
    return _print_json({'status': 'error', 'reason': f'unknown model command: {args.model_command}'})


def _train_command(runtime: LuciferRuntime, args: argparse.Namespace) -> int:
    exporter = TrainingCorpusExporter()
    state = runtime.kernel.state()
    if args.train_command == 'export-supervised':
        return _print_json(exporter.export_supervised(state, args.output))
    if args.train_command == 'export-preferences':
        return _print_json(exporter.export_preferences(state, args.output))
    return _print_json({'status': 'error', 'reason': f'unknown train command: {args.train_command}'})

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    runtime = runtime_from_args(args)
    try:
        if args.command == 'read':
            return _print_json(runtime.handle(f'read {args.path}'))
        if args.command == 'write':
            return _print_json(runtime.handle(f'write {args.path} :: {args.content}', confirm=args.confirm))
        if args.command == 'delete':
            return _print_json(runtime.handle(f'delete {args.path}', confirm=args.confirm))
        if args.command == 'shell':
            command_text = ' '.join(args.command_text).strip()
            if not command_text:
                parser.error('shell command requires command_text')
            return _print_json(runtime.handle(f'shell {command_text}'))
        if args.command == 'prompt':
            return _run_prompt(runtime, args)
        if args.command == 'approve':
            return _print_json(runtime.approve(args.proposal_id))
        if args.command == 'reject':
            return _print_json(runtime.reject(args.proposal_id, reason=args.reason))
        if args.command == 'rollback':
            return _print_json(runtime.rollback(args.proposal_id))
        if args.command == 'trace':
            output = Path(args.output)
            render_trace(runtime.kernel, output)
            return _print_json({'status': 'ok', 'trace_path': str(output.resolve())})
        if args.command == 'export':
            return _print_json(_export_command(runtime, args))
        if args.command == 'import':
            return _print_json(_import_command(runtime, args))
        if args.command == 'compact':
            return _print_json(_compact_command(runtime))
        if args.command == 'info':
            return _print_json(_info_command(runtime, args))
        if args.command == 'monitor':
            return _monitor_command(runtime, args)
        if args.command == 'doctor':
            return _print_json(_doctor(runtime, args))
        if args.command == 'config':
            return _print_json(_config_command(args))
        if args.command == 'model':
            return _model_command(runtime, args)
        if args.command == 'train':
            return _train_command(runtime, args)
        if args.command == 'state':
            state = runtime.kernel.state()
            return _print_json({'status': 'ok', 'state': state.__dict__})
        if args.command == 'commands':
            return _print_json({
                'status': 'ok',
                'commands': [
                    'read <path>',
                    'write <path> <content>',
                    'delete <path> [--confirm]',
                    'shell <allowlisted command>',
                    'prompt <text> [--stream] [--binary-path ...] [--model-path ...]',
                    'approve <proposal_id>',
                    'reject <proposal_id> [--reason]',
                    'rollback <proposal_id>',
                    'trace [--output trace.html]',
                    'export [--jsonl events.jsonl] [--sqlite-backup events.sqlite3]',
                    'import --jsonl events.jsonl',
                    'compact',
                    'info',
                    'monitor [--watch 2 --iterations 5]',
                    'doctor',
                    'config show|init',
                    'state',
                    'memory status|archive-now|sync|search',
                    'model backends|profiles|show-profile|register-profile|activate-profile|compare-profiles',
                    'train export-supervised|export-preferences',
                    'failures',
                    'bench',
                    'self-improve analyze',
                    'self-improve plan [--target-key key]',
                    'self-improve scaffold [--target-key key]',
                    'self-improve validate-run <run_id> [--timeout 120]',
                    'self-improve promote <run_id> [--force]',
                    'self-improve apply-patch <run_id> --path file --replacement text [--symbol name]',
                    'self-improve generate-candidates <run_id> --path file --replacement text [--symbol name]',
                    'self-improve score-candidates <run_id> [--timeout 120]',
                    'self-improve best-candidate <run_id>',
                    'self-improve execute-best <run_id> [--promote]',
                    'self-improve inject-fault <run_id> --kind python_syntax_break --path src/file.py',
                    'self-improve adversarial-cycle <run_id> --kind force_validation_failure --path file --replacement text',
                    'self-improve execute-cycle <run_id> --path file --replacement text [--symbol name] [--promote]',
                    'code index <path>',
                    'code verify <path>',
                    'code plan <path> <instruction> [--symbol name]',
                    'code replace-range <path> <start_line> <end_line> <replacement_text>',
                    'code replace-symbol <path> <symbol_name> <replacement_text>',
                    'fixnet sync-archive <fix_id> [--status live]',
                    'trust record <tool_name> --status success|failure',
                    'trust stats',
                    'curriculum record --theme name [--skill skill]',
                    'curriculum stats',
                    'directive add --title title --instruction text [--priority 90]',
                    'directive stats',
                    'continuity boot [--fallback-available]',
                    'continuity heartbeat [--mode fallback]',
                    'continuity status',
                ],
            })
        if args.command == 'code':
            if args.code_command == 'index':
                return _print_json(runtime.code_index(args.path))
            if args.code_command == 'verify':
                return _print_json(runtime.code_verify(args.path))
            if args.code_command == 'plan':
                return _print_json(runtime.code_plan(args.path, args.instruction, symbol_name=args.symbol))
            if args.code_command == 'replace-range':
                return _print_json(runtime.code_replace_range(args.path, args.start_line, args.end_line, args.replacement_text, confirm=args.confirm, expected_hash=args.expected_hash, reason=args.reason))
            if args.code_command == 'replace-symbol':
                return _print_json(runtime.code_replace_symbol(args.path, args.symbol_name, args.replacement_text, confirm=args.confirm, expected_hash=args.expected_hash, reason=args.reason))
        if args.command == 'directive':
            if args.directive_command == 'add':
                return _print_json(runtime.register_directive(
                    title=args.title,
                    instruction=args.instruction,
                    priority=args.priority,
                    scope=args.scope,
                    constraints=[k.strip() for k in args.constraints.split(',') if k.strip()],
                    success_conditions=[k.strip() for k in args.success_conditions.split(',') if k.strip()],
                    abort_conditions=[k.strip() for k in args.abort_conditions.split(',') if k.strip()],
                    persistence_mode=args.persistence_mode,
                    issuer=args.issuer,
                    supersedes=args.supersedes,
                ))
            if args.directive_command == 'complete':
                return _print_json(runtime.complete_directive(args.directive_id, status=args.status))
            if args.directive_command == 'stats':
                return _print_json(runtime.directive_stats())
            return _print_json({'status': 'error', 'reason': f'unknown directive command: {args.directive_command}'})
        if args.command == 'continuity':
            if args.continuity_command == 'boot':
                return _print_json(runtime.boot_continuity(fallback_available=args.fallback_available, notes=args.notes))
            if args.continuity_command == 'heartbeat':
                return _print_json(runtime.continuity_heartbeat(mode=args.mode, notes=args.notes))
            if args.continuity_command == 'status':
                return _print_json(runtime.continuity_status())
            return _print_json({'status': 'error', 'reason': f'unknown continuity command: {args.continuity_command}'})
        if args.command == 'goal':
            return _print_json(runtime.compile_goal(args.text, priority=args.priority))
        if args.command == 'shadow':
            return _print_json(runtime.shadow_handle(args.text, predicted_status=args.predicted_status, confirm=args.confirm))
        if args.command == 'memory':
            return _memory_command(runtime, args)
        if args.command == 'fixnet':
            if args.fixnet_command == 'register':
                return _print_json(runtime.fixnet_register(
                    title=args.title,
                    error_type=args.error_type,
                    error_signature=args.error_signature,
                    solution=args.solution,
                    summary=args.summary,
                    keywords=[k.strip() for k in args.keywords.split(',') if k.strip()],
                    context=json.loads(args.context_json),
                    evidence=json.loads(args.evidence_json),
                    linked_event_ids=args.linked_event_id,
                    linked_run_ids=args.linked_run_id,
                    linked_proposal_ids=args.linked_proposal_id,
                    auto_embed=args.auto_embed,
                    archive_branch_id=args.archive_branch_id,
                ))
            if args.fixnet_command == 'embed':
                return _print_json(runtime.fixnet_embed(args.fix_id, archive_branch_id=args.archive_branch_id))
            if args.fixnet_command == 'stats':
                return _print_json(runtime.fixnet_stats())
            if args.fixnet_command == 'sync-archive':
                return _print_json(runtime.fixnet_sync_archive(args.fix_id, status=args.status, retirement_at=args.retirement_at))
            return _print_json({'status': 'error', 'reason': f'unknown fixnet command: {args.fixnet_command}'})
        if args.command == 'trust':
            if args.trust_command == 'record':
                return _print_json(runtime.record_tool_outcome(args.tool_name, succeeded=args.status == 'success', notes=args.notes, evidence=json.loads(args.evidence_json)))
            if args.trust_command == 'stats':
                return _print_json(runtime.tool_trust_stats())
            return _print_json({'status': 'error', 'reason': f'unknown trust command: {args.trust_command}'})
        if args.command == 'curriculum':
            if args.curriculum_command == 'record':
                return _print_json(runtime.record_curriculum(theme=args.theme, skill=args.skill, failure_cluster=args.failure_cluster, outcome=args.outcome, notes=args.notes))
            if args.curriculum_command == 'stats':
                return _print_json(runtime.curriculum_stats())
            return _print_json({'status': 'error', 'reason': f'unknown curriculum command: {args.curriculum_command}'})
        if args.command == 'failures':
            state = runtime.kernel.state()
            return _print_json({'status': 'ok', 'failures': state.fallback_events, 'count': len(state.fallback_events)})
        if args.command == 'bench':
            return _print_json(runtime.run_benchmarks())
        if args.command == 'self-improve':
            if args.self_command == 'analyze':
                return _print_json(runtime.analyze_improvements())
            if args.self_command == 'plan':
                return _print_json(runtime.plan_improvements(target_key=args.target_key))
            if args.self_command == 'scaffold':
                return _print_json(runtime.scaffold_improvement_run(target_key=args.target_key))
            if args.self_command == 'validate-run':
                return _print_json(runtime.validate_improvement_run(args.run_id, timeout=args.timeout))
            if args.self_command == 'promote':
                return _print_json(runtime.promote_improvement_run(args.run_id, force=args.force))
            if args.self_command == 'apply-patch':
                return _print_json(runtime.apply_improvement_patch(
                    args.run_id,
                    path=args.path,
                    replacement_text=args.replacement,
                    symbol_name=args.symbol,
                    start_line=args.start_line,
                    end_line=args.end_line,
                    expected_hash=args.expected_hash,
                    rationale=args.reason,
                    validation_requested=args.validate,
                ))
            if args.self_command == 'generate-candidates':
                return _print_json(runtime.generate_improvement_candidates(
                    args.run_id,
                    path=args.path,
                    replacement_text=args.replacement,
                    symbol_name=args.symbol,
                    start_line=args.start_line,
                    end_line=args.end_line,
                    expected_hash=args.expected_hash,
                    rationale=args.reason,
                ))
            if args.self_command == 'score-candidates':
                return _print_json(runtime.score_improvement_candidates(args.run_id, timeout=args.timeout))
            if args.self_command == 'best-candidate':
                return _print_json(runtime.choose_best_improvement_candidate(args.run_id))
            if args.self_command == 'execute-best':
                return _print_json(runtime.execute_best_improvement_candidate(
                    args.run_id,
                    timeout=args.timeout,
                    promote=args.promote,
                    force_promote=args.force_promote,
                    quarantine_on_failure=not args.no_quarantine,
                ))
            if args.self_command == 'inject-fault':
                return _print_json(runtime.inject_improvement_fault(args.run_id, kind=args.kind, path=args.path, note=args.note))
            if args.self_command == 'adversarial-cycle':
                return _print_json(runtime.run_improvement_adversarial_cycle(
                    args.run_id,
                    kind=args.kind,
                    path=args.path,
                    replacement_text=args.replacement,
                    symbol_name=args.symbol,
                    start_line=args.start_line,
                    end_line=args.end_line,
                    expected_hash=args.expected_hash,
                    rationale=args.reason,
                    timeout=args.timeout,
                ))
            if args.self_command == 'execute-cycle':
                return _print_json(runtime.execute_improvement_cycle(
                    args.run_id,
                    path=args.path,
                    replacement_text=args.replacement,
                    symbol_name=args.symbol,
                    start_line=args.start_line,
                    end_line=args.end_line,
                    expected_hash=args.expected_hash,
                    rationale=args.reason,
                    validate=not args.no_validate,
                    timeout=args.timeout,
                    promote=args.promote,
                    force_promote=args.force_promote,
                    quarantine_on_failure=not args.no_quarantine,
                ))
    finally:
        runtime.kernel.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
