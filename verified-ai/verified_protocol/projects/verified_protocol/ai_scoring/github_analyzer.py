"""
AI Scoring Engine — GitHub Analyzer
=====================================

Analyzes GitHub repositories via the public REST API to produce
credibility signals. Works without authentication (60 req/hr) or
with a GITHUB_TOKEN for 5000 req/hr.

Signals extracted:
    • Commit activity & frequency
    • Language composition & diversity
    • Community signals (stars, forks, watchers, issues)
    • Documentation quality (README, LICENSE, CI, tests)
    • Repo maturity & recency
    • Code quality heuristics
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from ai_scoring.models import DomainDetection, SourceType, VerificationSignal
from ai_scoring.rules import (
    CI_FILES,
    CONFIG_FILES,
    DOC_FILES,
    GitHubWeights,
    LANGUAGE_DOMAIN_MAP,
    SUBDOMAIN_SIGNALS,
    TEST_DIRS,
)

logger = logging.getLogger("ai_scoring.github")

GITHUB_API = "https://api.github.com"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _parse_repo_url(url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL.

    Accepts:
        https://github.com/owner/repo
        https://github.com/owner/repo.git
        github.com/owner/repo
        owner/repo
    """
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]

    match = re.search(r"(?:github\.com/)?([^/]+)/([^/]+)$", url)
    if not match:
        raise ValueError(f"Cannot parse GitHub repo from: {url}")
    return match.group(1), match.group(2)


def _headers() -> dict[str, str]:
    """Build request headers, optionally with auth token."""
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _normalize(value: float, low: float, high: float) -> float:
    """Normalize value to 0.0–1.0 range with clamping."""
    if high <= low:
        return 0.0
    return max(0.0, min(1.0, (value - low) / (high - low)))


# ─────────────────────────────────────────────────────────────────────────────
# GitHub Data Fetcher
# ─────────────────────────────────────────────────────────────────────────────
class GitHubAnalyzer:
    """Fetches and scores GitHub repository data."""

    def __init__(self) -> None:
        self.weights = GitHubWeights()

    async def analyze(self, repo_url: str) -> dict[str, Any]:
        """Full analysis pipeline for a GitHub repo.

        Returns dict with:
            signals: list[VerificationSignal]
            domains: list[DomainDetection]
            metadata: dict
            overall_score: float (0.0–1.0)
        """
        owner, repo = _parse_repo_url(repo_url)
        headers = _headers()

        async with httpx.AsyncClient(timeout=15.0) as client:
            # Parallel fetches
            repo_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers
            )
            if repo_resp.status_code == 404:
                return self._error_result("Repository not found")
            if repo_resp.status_code == 403:
                return self._error_result("GitHub API rate limit exceeded")
            repo_resp.raise_for_status()
            repo_data = repo_resp.json()

            # Languages
            lang_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/languages", headers=headers
            )
            languages = lang_resp.json() if lang_resp.status_code == 200 else {}

            # Contributors (top 30)
            contrib_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/contributors",
                headers=headers,
                params={"per_page": 30},
            )
            contributors = contrib_resp.json() if contrib_resp.status_code == 200 else []

            # Recent commits (last 100)
            commits_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                headers=headers,
                params={"per_page": 100},
            )
            commits = commits_resp.json() if commits_resp.status_code == 200 else []

            # Repo tree (root level)
            tree_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{repo_data.get('default_branch', 'main')}",
                headers=headers,
            )
            tree = tree_resp.json().get("tree", []) if tree_resp.status_code == 200 else []

        # Build signals
        signals: list[VerificationSignal] = []
        metadata: dict[str, Any] = {
            "owner": owner,
            "repo": repo,
            "full_name": repo_data.get("full_name", ""),
            "description": repo_data.get("description", ""),
            "default_branch": repo_data.get("default_branch", "main"),
            "created_at": repo_data.get("created_at", ""),
            "updated_at": repo_data.get("updated_at", ""),
            "pushed_at": repo_data.get("pushed_at", ""),
            "html_url": repo_data.get("html_url", ""),
            "topics": repo_data.get("topics", []),
        }

        # 1. Commit Activity
        total_commits = sum(
            (c.get("contributions", 0) if isinstance(c, dict) else 0)
            for c in (contributors if isinstance(contributors, list) else [])
        )
        commit_score = _normalize(
            total_commits, 0, self.weights.COMMIT_HIGH
        )
        signals.append(VerificationSignal(
            signal_name="commit_activity",
            value=total_commits,
            max_value=self.weights.COMMIT_HIGH,
            normalized=commit_score,
            detail=f"{total_commits} total contributions across {len(contributors) if isinstance(contributors, list) else 0} contributors",
        ))

        # 2. Code Volume (file count in tree)
        file_count = len([t for t in tree if t.get("type") == "blob"])
        vol_score = _normalize(file_count, 0, self.weights.FILE_COUNT_HIGH)
        signals.append(VerificationSignal(
            signal_name="code_volume",
            value=file_count,
            max_value=self.weights.FILE_COUNT_HIGH,
            normalized=vol_score,
            detail=f"{file_count} files in root tree",
        ))

        # 3. Language Diversity
        lang_count = len(languages)
        lang_score = _normalize(lang_count, 0, 6)
        signals.append(VerificationSignal(
            signal_name="language_diversity",
            value=lang_count,
            max_value=6,
            normalized=lang_score,
            detail=f"Languages: {', '.join(languages.keys()) if languages else 'none detected'}",
        ))

        # 4. Community Signals
        stars = repo_data.get("stargazers_count", 0)
        forks = repo_data.get("forks_count", 0)
        watchers = repo_data.get("watchers_count", 0)
        community_raw = (
            _normalize(stars, 0, self.weights.STARS_HIGH) * 0.50
            + _normalize(forks, 0, self.weights.FORKS_HIGH) * 0.30
            + _normalize(watchers, 0, 50) * 0.20
        )
        signals.append(VerificationSignal(
            signal_name="community_signals",
            value=stars + forks,
            max_value=self.weights.STARS_HIGH + self.weights.FORKS_HIGH,
            normalized=min(1.0, community_raw),
            detail=f"⭐ {stars} stars, 🍴 {forks} forks, 👀 {watchers} watchers",
        ))

        # 5. Documentation
        tree_names = {t.get("path", "").lower() for t in tree}
        doc_present = sum(1 for d in DOC_FILES if d in tree_names)
        ci_present = any(c in tree_names for c in CI_FILES)
        config_present = sum(1 for c in CONFIG_FILES if c in tree_names)
        test_present = any(t in tree_names for t in TEST_DIRS)

        doc_signals_count = doc_present + (2 if ci_present else 0) + min(config_present, 3) + (2 if test_present else 0)
        doc_score = _normalize(doc_signals_count, 0, 10)
        signals.append(VerificationSignal(
            signal_name="documentation",
            value=doc_signals_count,
            max_value=10,
            normalized=doc_score,
            detail=f"Docs: {doc_present}, CI: {ci_present}, Config: {config_present}, Tests: {test_present}",
        ))

        # 6. Recency
        pushed_at = repo_data.get("pushed_at", "")
        days_since_push = 999
        if pushed_at:
            try:
                push_dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                days_since_push = (datetime.now(timezone.utc) - push_dt).days
            except (ValueError, TypeError):
                pass

        if days_since_push <= self.weights.RECENCY_EXCELLENT:
            recency_score = 1.0
        elif days_since_push <= self.weights.RECENCY_GOOD:
            recency_score = 0.7
        elif days_since_push <= self.weights.RECENCY_ACCEPTABLE:
            recency_score = 0.4
        else:
            recency_score = 0.1

        signals.append(VerificationSignal(
            signal_name="recency",
            value=days_since_push,
            max_value=365,
            normalized=recency_score,
            detail=f"Last pushed {days_since_push} day(s) ago",
        ))

        # 7. Repo Maturity
        created_at = repo_data.get("created_at", "")
        repo_age_days = 0
        if created_at:
            try:
                create_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                repo_age_days = (datetime.now(timezone.utc) - create_dt).days
            except (ValueError, TypeError):
                pass

        maturity_score = _normalize(
            repo_age_days, 0, self.weights.MATURITY_ESTABLISHED
        )
        signals.append(VerificationSignal(
            signal_name="repo_maturity",
            value=repo_age_days,
            max_value=self.weights.MATURITY_ESTABLISHED,
            normalized=maturity_score,
            detail=f"Repository age: {repo_age_days} days",
        ))

        # 8. Code Quality Signals (heuristic)
        has_license = "license" in tree_names or "license.md" in tree_names
        has_gitignore = ".gitignore" in tree_names
        has_readme = any(
            n.startswith("readme") for n in tree_names
        )
        quality_bits = sum([has_license, has_gitignore, has_readme, ci_present, test_present])
        quality_score = _normalize(quality_bits, 0, 5)
        signals.append(VerificationSignal(
            signal_name="code_quality_signals",
            value=quality_bits,
            max_value=5,
            normalized=quality_score,
            detail=f"License: {has_license}, .gitignore: {has_gitignore}, README: {has_readme}, CI: {ci_present}, Tests: {test_present}",
        ))

        # ── Compute weighted overall score ────────────────────────────
        weight_map = {
            "commit_activity": self.weights.COMMIT_ACTIVITY,
            "code_volume": self.weights.CODE_VOLUME,
            "language_diversity": self.weights.LANGUAGE_DIVERSITY,
            "community_signals": self.weights.COMMUNITY_SIGNALS,
            "documentation": self.weights.DOCUMENTATION,
            "recency": self.weights.RECENCY,
            "repo_maturity": self.weights.REPO_MATURITY,
            "code_quality_signals": self.weights.CODE_QUALITY_SIGNALS,
        }

        overall = sum(
            s.normalized * weight_map.get(s.signal_name, 0)
            for s in signals
        )

        # ── Domain Detection ──────────────────────────────────────────
        domains = self._detect_domains(languages, tree_names, repo_data.get("topics", []))

        metadata["languages"] = languages
        metadata["stars"] = stars
        metadata["forks"] = forks
        metadata["file_count"] = file_count
        metadata["total_commits"] = total_commits
        metadata["contributor_count"] = len(contributors) if isinstance(contributors, list) else 0
        metadata["days_since_push"] = days_since_push
        metadata["repo_age_days"] = repo_age_days

        return {
            "signals": signals,
            "domains": domains,
            "metadata": metadata,
            "overall_score": round(overall, 4),
        }

    def _detect_domains(
        self,
        languages: dict[str, int],
        tree_names: set[str],
        topics: list[str],
    ) -> list[DomainDetection]:
        """Detect skill domains from languages, file tree, and topics."""
        domains: dict[str, float] = {}
        total_bytes = sum(languages.values()) or 1

        # From languages
        for lang, byte_count in languages.items():
            lang_lower = lang.lower()
            domain = LANGUAGE_DOMAIN_MAP.get(lang_lower)
            if domain:
                confidence = min(1.0, (byte_count / total_bytes) * 2)
                domains[domain] = max(domains.get(domain, 0), confidence)

        # Subdomain detection from tree names + topics
        all_names = tree_names | {t.lower() for t in topics}
        for subdomain, keywords in SUBDOMAIN_SIGNALS.items():
            matches = sum(1 for kw in keywords if any(kw in n for n in all_names))
            if matches >= 2:
                confidence = min(1.0, matches / 4)
                domains[subdomain] = max(domains.get(subdomain, 0), confidence)

        # Sort by confidence
        result = [
            DomainDetection(domain=d, confidence=round(c, 3))
            for d, c in sorted(domains.items(), key=lambda x: -x[1])
        ]
        return result[:5]  # top 5

    @staticmethod
    def _error_result(msg: str) -> dict[str, Any]:
        return {
            "signals": [],
            "domains": [],
            "metadata": {"error": msg},
            "overall_score": 0.0,
        }
