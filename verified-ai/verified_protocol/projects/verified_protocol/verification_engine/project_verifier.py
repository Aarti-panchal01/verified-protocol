"""
Verification Engine — Project Verifier
========================================

Verifies local project directories for authenticity and quality.

Checks:
    • Directory existence and structure
    • Code file presence and diversity
    • Documentation signals
    • Originality heuristics (not just scaffold)
    • Composite project hash for immutability
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

from ai_scoring.models import SourceType, VerificationResult, VerificationSignal, DomainDetection
from ai_scoring.rules import LANGUAGE_DOMAIN_MAP

logger = logging.getLogger("verification.project")

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", "dist", "build",
}

CODE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rs", ".rb", ".php", ".c", ".cpp", ".cs", ".sol",
}


class ProjectVerifier:
    """Verifies local project evidence."""

    async def verify(self, project_path: str) -> VerificationResult:
        """Verify a project directory."""
        root = Path(project_path)
        signals: list[VerificationSignal] = []
        metadata: dict[str, Any] = {"project_path": project_path}

        if not root.exists() or not root.is_dir():
            return VerificationResult(
                source_type=SourceType.PROJECT,
                verified=False,
                error=f"Invalid directory: {project_path}",
            )

        # Scan
        all_files: list[Path] = []
        for dp, dirs, fns in os.walk(root):
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
            for fn in fns:
                all_files.append(Path(dp) / fn)
                if len(all_files) >= 2000:
                    break

        code_files = [f for f in all_files if f.suffix.lower() in CODE_EXTS]
        filenames = {f.name.lower() for f in all_files}

        # 1. Structure
        has_structure = len(code_files) >= 3
        signals.append(VerificationSignal(
            signal_name="project_structure",
            value=len(code_files),
            max_value=50,
            normalized=min(1.0, len(code_files) / 15) if has_structure else 0.2,
            detail=f"{len(code_files)} code files, {len(all_files)} total files",
        ))

        # 2. Documentation
        doc_signals = sum(1 for f in ["readme.md", "readme.rst", "readme.txt", "license", "license.md"] if f in filenames)
        signals.append(VerificationSignal(
            signal_name="documentation",
            value=doc_signals,
            max_value=5,
            normalized=min(1.0, doc_signals / 2),
            detail=f"{doc_signals} documentation files found",
        ))

        # 3. Originality
        ext_diversity = len({f.suffix.lower() for f in code_files if f.suffix})
        non_trivial = len(code_files) > 5
        signals.append(VerificationSignal(
            signal_name="originality",
            value=ext_diversity,
            max_value=5,
            normalized=min(1.0, ext_diversity / 3) if non_trivial else 0.2,
            detail=f"{ext_diversity} code languages, {'non-trivial' if non_trivial else 'minimal'} project",
        ))

        # 4. Project hash
        sha = hashlib.sha256()
        for f in sorted(code_files[:30]):
            try:
                sha.update(f.read_bytes())
            except (OSError, PermissionError):
                continue
        project_hash = sha.hexdigest()
        metadata["project_hash"] = project_hash

        signals.append(VerificationSignal(
            signal_name="hash_integrity",
            value=1,
            max_value=1,
            normalized=1.0,
            detail=f"Project hash: {project_hash[:24]}…",
        ))

        # Domains
        ext_to_lang = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".go": "go", ".rs": "rust", ".sol": "solidity",
            ".java": "java", ".rb": "ruby", ".c": "c", ".cpp": "c++",
        }
        domains: list[DomainDetection] = []
        for f in code_files:
            lang = ext_to_lang.get(f.suffix.lower())
            if lang:
                dom = LANGUAGE_DOMAIN_MAP.get(lang)
                if dom and dom not in [d.domain for d in domains]:
                    domains.append(DomainDetection(domain=dom, confidence=0.7))

        metadata["total_files"] = len(all_files)
        metadata["code_files"] = len(code_files)

        overall = sum(s.normalized for s in signals) / max(len(signals), 1)

        return VerificationResult(
            source_type=SourceType.PROJECT,
            verified=overall >= 0.4 and has_structure,
            overall_score=round(overall, 4),
            signals=signals,
            domains_detected=domains[:3],
            metadata=metadata,
        )
