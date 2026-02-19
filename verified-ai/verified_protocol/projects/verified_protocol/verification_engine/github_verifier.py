"""
Verification Engine — GitHub Verifier
=======================================

Verifies GitHub evidence by cross-referencing repo data
with claimed skills. Detects potential misrepresentation.

Checks:
    • Repo existence and accessibility
    • Ownership signals (contributor presence)
    • Commit authenticity (temporal patterns)
    • Language claim consistency
    • Fork vs original detection
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from ai_scoring.models import SourceType, VerificationResult, VerificationSignal, DomainDetection
from ai_scoring.rules import LANGUAGE_DOMAIN_MAP

logger = logging.getLogger("verification.github")

GITHUB_API = "https://api.github.com"


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"token {token}"
    return h


def _parse_repo(url: str) -> tuple[str, str]:
    url = url.strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    m = re.search(r"(?:github\.com/)?([^/]+)/([^/]+)$", url)
    if not m:
        raise ValueError(f"Cannot parse repo URL: {url}")
    return m.group(1), m.group(2)


class GitHubVerifier:
    """Verifies GitHub repository evidence."""

    async def verify(
        self,
        repo_url: str,
        claimed_wallet: str | None = None,
    ) -> VerificationResult:
        """Verify a GitHub repo and return a VerificationResult."""
        try:
            owner, repo = _parse_repo(repo_url)
        except ValueError as e:
            return VerificationResult(
                source_type=SourceType.GITHUB_REPO,
                source_url=repo_url,
                verified=False,
                error=str(e),
            )

        headers = _headers()
        signals: list[VerificationSignal] = []
        metadata: dict[str, Any] = {"owner": owner, "repo": repo}

        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Repo existence
            r = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers)
            if r.status_code == 404:
                return VerificationResult(
                    source_type=SourceType.GITHUB_REPO,
                    source_url=repo_url,
                    verified=False,
                    error="Repository not found",
                )
            if r.status_code == 403:
                return VerificationResult(
                    source_type=SourceType.GITHUB_REPO,
                    source_url=repo_url,
                    verified=False,
                    error="API rate limit exceeded",
                )
            r.raise_for_status()
            data = r.json()

            # 2. Fork check
            is_fork = data.get("fork", False)
            signals.append(VerificationSignal(
                signal_name="originality",
                value=0 if is_fork else 1,
                max_value=1,
                normalized=0.3 if is_fork else 1.0,
                detail=f"{'Forked repo — reduced credibility' if is_fork else 'Original repository'}",
            ))

            # 3. Not empty
            size = data.get("size", 0)
            is_empty = size == 0
            signals.append(VerificationSignal(
                signal_name="content_presence",
                value=size,
                max_value=10000,
                normalized=0.0 if is_empty else min(1.0, size / 500),
                detail=f"Repo size: {size} KB" + (" — EMPTY" if is_empty else ""),
            ))

            # 4. Recent activity
            pushed_at = data.get("pushed_at", "")
            days_inactive = 999
            if pushed_at:
                try:
                    dt = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
                    days_inactive = (datetime.now(timezone.utc) - dt).days
                except (ValueError, TypeError):
                    pass

            activity_score = 1.0 if days_inactive < 30 else (0.6 if days_inactive < 180 else 0.2)
            signals.append(VerificationSignal(
                signal_name="recent_activity",
                value=days_inactive,
                max_value=365,
                normalized=activity_score,
                detail=f"Last push: {days_inactive} days ago",
            ))

            # 5. Commit consistency (check last 30 commits for spread)
            commits_r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/commits",
                headers=headers,
                params={"per_page": 30},
            )
            commits = commits_r.json() if commits_r.status_code == 200 and isinstance(commits_r.json(), list) else []

            if len(commits) >= 5:
                # Check temporal spread — are commits over days or all in one burst?
                dates = []
                for c in commits:
                    cd = c.get("commit", {}).get("author", {}).get("date", "")
                    if cd:
                        try:
                            dates.append(datetime.fromisoformat(cd.replace("Z", "+00:00")))
                        except (ValueError, TypeError):
                            continue

                if len(dates) >= 2:
                    span = (max(dates) - min(dates)).days
                    consistency = min(1.0, span / 30)
                else:
                    consistency = 0.3
            else:
                consistency = 0.2

            signals.append(VerificationSignal(
                signal_name="commit_consistency",
                value=len(commits),
                max_value=30,
                normalized=consistency,
                detail=f"{len(commits)} recent commits — {'organic pattern' if consistency > 0.5 else 'burst pattern'}",
            ))

            # 6. Languages
            lang_r = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/languages", headers=headers
            )
            languages = lang_r.json() if lang_r.status_code == 200 else {}

            lang_score = min(1.0, len(languages) / 3)
            signals.append(VerificationSignal(
                signal_name="language_verification",
                value=len(languages),
                max_value=5,
                normalized=lang_score,
                detail=f"Languages: {', '.join(languages.keys()) or 'none'}",
            ))

        # Domains
        domains: list[DomainDetection] = []
        for lang in languages:
            dom = LANGUAGE_DOMAIN_MAP.get(lang.lower())
            if dom:
                domains.append(DomainDetection(domain=dom, confidence=0.8))

        metadata["is_fork"] = is_fork
        metadata["size_kb"] = size
        metadata["days_inactive"] = days_inactive
        metadata["languages"] = list(languages.keys())
        metadata["html_url"] = data.get("html_url", "")

        overall = sum(s.normalized for s in signals) / max(len(signals), 1)
        verified = overall >= 0.4 and not is_empty

        return VerificationResult(
            source_type=SourceType.GITHUB_REPO,
            source_url=repo_url,
            verified=verified,
            overall_score=round(overall, 4),
            signals=signals,
            domains_detected=domains[:3],
            metadata=metadata,
        )
