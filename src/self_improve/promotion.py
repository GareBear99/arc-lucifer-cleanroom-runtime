from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ValidationResult:
    run_id: str
    passed: bool
    command_results: list[dict[str, Any]]
    manifest_path: str
    worktree_dir: str
    validation_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            'run_id': self.run_id,
            'passed': self.passed,
            'command_results': self.command_results,
            'manifest_path': self.manifest_path,
            'worktree_dir': self.worktree_dir,
            'validation_path': self.validation_path,
        }


class PromotionGate:
    def _run_root(self, workspace_root: str | Path) -> Path:
        return Path(workspace_root) / '.arc_lucifer' / 'self_improve_runs'

    def _find_run_dir(self, workspace_root: str | Path, run_id: str) -> Path:
        run_dir = self._run_root(workspace_root) / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f'Unknown improvement run: {run_id}')
        return run_dir

    def load_manifest(self, workspace_root: str | Path, run_id: str) -> dict[str, Any]:
        run_dir = self._find_run_dir(workspace_root, run_id)
        manifest_path = run_dir / 'manifest.json'
        return json.loads(manifest_path.read_text(encoding='utf-8'))

    def validate_run(self, workspace_root: str | Path, run_id: str, timeout: int = 120) -> ValidationResult:
        run_dir = self._find_run_dir(workspace_root, run_id)
        manifest = self.load_manifest(workspace_root, run_id)
        worktree_dir = Path(manifest['worktree_dir'])
        command_results: list[dict[str, Any]] = []
        all_passed = True
        for command in manifest.get('recommended_commands', []):
            proc = subprocess.run(
                command,
                cwd=worktree_dir,
                shell=True,
                text=True,
                capture_output=True,
                timeout=timeout,
            )
            result = {
                'command': command,
                'returncode': proc.returncode,
                'stdout': proc.stdout[-4000:],
                'stderr': proc.stderr[-4000:],
                'passed': proc.returncode == 0,
            }
            command_results.append(result)
            all_passed = all_passed and result['passed']
        payload = {
            'run_id': run_id,
            'passed': all_passed,
            'command_results': command_results,
        }
        validation_path = run_dir / 'validation.json'
        validation_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
        return ValidationResult(
            run_id=run_id,
            passed=all_passed,
            command_results=command_results,
            manifest_path=str((run_dir / 'manifest.json').resolve()),
            worktree_dir=str(worktree_dir.resolve()),
            validation_path=str(validation_path.resolve()),
        )

    def promote_run(self, workspace_root: str | Path, run_id: str, *, force: bool = False) -> dict[str, Any]:
        run_dir = self._find_run_dir(workspace_root, run_id)
        manifest = self.load_manifest(workspace_root, run_id)
        validation_path = run_dir / 'validation.json'
        if not force:
            if not validation_path.exists():
                raise ValueError('Run must be validated before promotion.')
            validation = json.loads(validation_path.read_text(encoding='utf-8'))
            if not validation.get('passed'):
                raise ValueError('Validation failed; refusing promotion.')
        worktree_dir = Path(manifest['worktree_dir'])
        workspace = Path(workspace_root).resolve()
        promoted: list[str] = []
        for rel in ['src', 'tests', 'docs', 'README.md', 'pyproject.toml']:
            src = worktree_dir / rel
            dst = workspace / rel
            if not src.exists():
                continue
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache', '*.pyc'))
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            promoted.append(rel)
        payload = {
            'run_id': run_id,
            'promoted_paths': promoted,
            'forced': force,
            'workspace': str(workspace),
        }
        (run_dir / 'promotion.json').write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')
        return payload
