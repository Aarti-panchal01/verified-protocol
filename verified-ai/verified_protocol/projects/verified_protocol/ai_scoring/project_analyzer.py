"""
AI Scoring Engine — Project Analyzer
======================================

Analyzes local project directories to score structure,
documentation, code quality, completeness, and originality.

Works on any tech stack by inspecting file structure.
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any

from ai_scoring.models import DomainDetection, VerificationSignal
from ai_scoring.rules import (
    CI_FILES,
    CONFIG_FILES,
    DOC_FILES,
    LANGUAGE_DOMAIN_MAP,
    ProjectWeights,
    SUBDOMAIN_SIGNALS,
    TEST_DIRS,
)

logger = logging.getLogger("ai_scoring.project")

# Max files to scan to avoid hanging on massive repos
MAX_FILES_SCAN = 2000

# Extensions to count by category
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".kt",
    ".c", ".cpp", ".h", ".cs", ".go", ".rs", ".rb", ".php",
    ".swift", ".dart", ".sol", ".vy", ".ex", ".exs",
    ".scala", ".r", ".jl", ".lua", ".sh", ".bash",
}

ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".ico", ".mp4", ".mp3", ".wav", ".ttf", ".woff",
}

IGNORED_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".next", ".nuxt", "target", "bin", "obj",
}


class ProjectAnalyzer:
    """Analyzes local project directories for credibility signals."""

    def __init__(self) -> None:
        self.weights = ProjectWeights()

    async def analyze(self, project_path: str) -> dict[str, Any]:
        """Analyze a project directory.

        Returns dict with:
            signals: list[VerificationSignal]
            domains: list[DomainDetection]
            metadata: dict
            overall_score: float (0.0-1.0)
        """
        root = Path(project_path)

        if not root.exists() or not root.is_dir():
            return self._error_result(f"Not a valid directory: {project_path}")

        # Scan files
        all_files = self._scan_files(root)
        rel_names = {str(f.relative_to(root)).lower().replace("\\", "/") for f in all_files}
        filenames_only = {f.name.lower() for f in all_files}

        signals: list[VerificationSignal] = []
        metadata: dict[str, Any] = {
            "project_path": str(root),
            "total_files": len(all_files),
        }

        # ── 1. Structure ──────────────────────────────────────────────
        code_files = [f for f in all_files if f.suffix.lower() in CODE_EXTENSIONS]
        dir_count = len({f.parent for f in all_files})
        has_nested = dir_count > 3

        structure_score = min(1.0, (
            min(len(code_files) / 20, 0.5) +
            (0.3 if has_nested else 0.1) +
            min(len(all_files) / 50, 0.2)
        ))

        signals.append(VerificationSignal(
            signal_name="structure",
            value=len(code_files),
            max_value=50,
            normalized=round(structure_score, 3),
            detail=f"{len(code_files)} code files across {dir_count} directories",
        ))

        metadata["code_files"] = len(code_files)
        metadata["directories"] = dir_count

        # ── 2. Documentation ──────────────────────────────────────────
        doc_present = sum(1 for d in DOC_FILES if d in filenames_only)
        config_present = sum(1 for c in CONFIG_FILES if c in filenames_only)
        doc_score = min(1.0, (doc_present * 0.2 + config_present * 0.1))

        signals.append(VerificationSignal(
            signal_name="documentation",
            value=doc_present + config_present,
            max_value=10,
            normalized=round(doc_score, 3),
            detail=f"Doc files: {doc_present}, Config files: {config_present}",
        ))

        # ── 3. Code Quality ───────────────────────────────────────────
        has_tests = any(t in filenames_only or any(t in r for r in rel_names) for t in TEST_DIRS)
        has_ci = any(c in filenames_only or any(c in r for r in rel_names) for c in CI_FILES)
        has_gitignore = ".gitignore" in filenames_only
        has_lint = any(
            f in filenames_only for f in
            [".eslintrc", ".eslintrc.json", ".pylintrc", "ruff.toml", ".flake8", "mypy.ini"]
        )

        quality_bits = sum([has_tests, has_ci, has_gitignore, has_lint])
        quality_score = quality_bits / 4

        signals.append(VerificationSignal(
            signal_name="code_quality",
            value=quality_bits,
            max_value=4,
            normalized=quality_score,
            detail=f"Tests: {has_tests}, CI: {has_ci}, .gitignore: {has_gitignore}, Linter: {has_lint}",
        ))

        # ── 4. Completeness ───────────────────────────────────────────
        has_pkg_manager = any(
            f in filenames_only for f in
            ["package.json", "pyproject.toml", "cargo.toml", "go.mod", "gemfile", "pom.xml"]
        )
        has_entry = any(
            f in filenames_only for f in
            ["main.py", "app.py", "index.js", "index.ts", "main.go", "main.rs", "main.java"]
        )
        has_readme = any(f.startswith("readme") for f in filenames_only)

        completeness_bits = sum([has_pkg_manager, has_entry, has_readme, len(code_files) > 3])
        completeness_score = completeness_bits / 4

        signals.append(VerificationSignal(
            signal_name="completeness",
            value=completeness_bits,
            max_value=4,
            normalized=completeness_score,
            detail=f"Package manager: {has_pkg_manager}, Entry point: {has_entry}, README: {has_readme}",
        ))

        # ── 5. Tech Stack ─────────────────────────────────────────────
        extensions_used = {f.suffix.lower() for f in code_files if f.suffix}
        ext_count = len(extensions_used)
        stack_score = min(1.0, ext_count / 5)

        signals.append(VerificationSignal(
            signal_name="tech_stack",
            value=ext_count,
            max_value=5,
            normalized=round(stack_score, 3),
            detail=f"Extensions: {', '.join(sorted(extensions_used)) or 'none'}",
        ))

        # ── 6. Originality (heuristic) ────────────────────────────────
        # Check if it's not just scaffolding
        has_custom_code = len(code_files) > 5
        has_assets = any(f.suffix.lower() in ASSET_EXTENSIONS for f in all_files)
        no_scaffold_only = not (
            len(code_files) <= 3 and
            any("create-" in str(f) or "scaffold" in str(f).lower() for f in all_files)
        )

        originality_bits = sum([has_custom_code, has_assets, no_scaffold_only])
        originality_score = originality_bits / 3

        signals.append(VerificationSignal(
            signal_name="originality",
            value=originality_bits,
            max_value=3,
            normalized=round(originality_score, 3),
            detail=f"Custom code: {has_custom_code}, Assets: {has_assets}, Non-scaffold: {no_scaffold_only}",
        ))

        # ── Weighted overall ──────────────────────────────────────────
        weight_map = {
            "structure": self.weights.STRUCTURE,
            "documentation": self.weights.DOCUMENTATION,
            "code_quality": self.weights.CODE_QUALITY,
            "completeness": self.weights.COMPLETENESS,
            "tech_stack": self.weights.TECH_STACK,
            "originality": self.weights.ORIGINALITY,
        }

        overall = sum(
            s.normalized * weight_map.get(s.signal_name, 0)
            for s in signals
        )

        # ── Domain Detection ──────────────────────────────────────────
        domains = self._detect_domains(code_files, rel_names, filenames_only)

        # ── Project hash ──────────────────────────────────────────────
        project_hash = self._hash_project(code_files[:50])
        metadata["project_hash"] = project_hash
        metadata["extensions_used"] = sorted(extensions_used)

        return {
            "signals": signals,
            "domains": domains,
            "metadata": metadata,
            "overall_score": round(overall, 4),
        }

    def _scan_files(self, root: Path) -> list[Path]:
        """Walk directory tree, skip ignored dirs, cap at MAX_FILES_SCAN."""
        files: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
            for fn in filenames:
                files.append(Path(dirpath) / fn)
                if len(files) >= MAX_FILES_SCAN:
                    return files
        return files

    @staticmethod
    def _detect_domains(
        code_files: list[Path],
        rel_names: set[str],
        filenames: set[str],
    ) -> list[DomainDetection]:
        """Detect domains from file extensions and names."""
        ext_to_lang: dict[str, str] = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".jsx": "javascript", ".tsx": "typescript",
            ".java": "java", ".kt": "kotlin", ".go": "go",
            ".rs": "rust", ".rb": "ruby", ".php": "php",
            ".swift": "swift", ".dart": "dart", ".sol": "solidity",
            ".c": "c", ".cpp": "c++", ".cs": "c#",
        }

        lang_counts: dict[str, int] = {}
        for f in code_files:
            lang = ext_to_lang.get(f.suffix.lower())
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

        total = sum(lang_counts.values()) or 1
        domains: dict[str, float] = {}

        for lang, count in lang_counts.items():
            domain = LANGUAGE_DOMAIN_MAP.get(lang)
            if domain:
                conf = min(1.0, (count / total) * 1.5)
                domains[domain] = max(domains.get(domain, 0), conf)

        # Subdomain signals
        for subdomain, keywords in SUBDOMAIN_SIGNALS.items():
            matches = sum(1 for kw in keywords if any(kw in name for name in rel_names | filenames))
            if matches >= 2:
                conf = min(1.0, matches / 4)
                domains[subdomain] = max(domains.get(subdomain, 0), conf)

        return [
            DomainDetection(domain=d, confidence=round(c, 3))
            for d, c in sorted(domains.items(), key=lambda x: -x[1])
        ][:5]

    @staticmethod
    def _hash_project(files: list[Path]) -> str:
        """Compute a composite hash over the first N code files."""
        sha = hashlib.sha256()
        for f in sorted(files):
            try:
                sha.update(f.read_bytes())
            except (OSError, PermissionError):
                continue
        return sha.hexdigest()

    @staticmethod
    def _error_result(msg: str) -> dict[str, Any]:
        return {
            "signals": [],
            "domains": [],
            "metadata": {"error": msg},
            "overall_score": 0.0,
        }
