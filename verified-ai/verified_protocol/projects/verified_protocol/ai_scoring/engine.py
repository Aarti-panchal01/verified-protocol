"""
AI Scoring Engine — Main Orchestrator
=======================================

Routes evidence to the appropriate analyzer, aggregates signals,
and produces a final ScoringResult ready for on-chain submission.

Design:
    • Pluggable provider architecture
    • Hybrid: static rules + heuristic reasoning
    • Produces explanations for every score
    • Generates artifact_hash for on-chain storage
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from ai_scoring.certificate_analyzer import CertificateAnalyzer
from ai_scoring.github_analyzer import GitHubAnalyzer
from ai_scoring.models import (
    DomainDetection,
    EvidenceMode,
    ScoringBreakdown,
    ScoringInput,
    ScoringResult,
    SkillRecordPayload,
    SourceType,
)
from ai_scoring.project_analyzer import ProjectAnalyzer
from ai_scoring.rules import credibility_label

logger = logging.getLogger("ai_scoring.engine")


class ScoringEngine:
    """Main AI scoring orchestrator.

    Usage:
        engine = ScoringEngine()
        result = await engine.score(ScoringInput(
            mode=EvidenceMode.DEVELOPER,
            source_type=SourceType.GITHUB_REPO,
            source_url="https://github.com/owner/repo",
        ))
    """

    def __init__(self) -> None:
        self.github = GitHubAnalyzer()
        self.certificate = CertificateAnalyzer()
        self.project = ProjectAnalyzer()

    async def score(self, inp: ScoringInput) -> ScoringResult:
        """Score evidence and return a ScoringResult.

        Routes to the correct analyzer based on source_type, then
        normalizes the output into a unified scoring format.
        """
        logger.info(
            "Scoring %s evidence [%s] — source: %s",
            inp.mode.value, inp.source_type.value,
            inp.source_url or inp.file_path or "raw",
        )

        # ── Route to analyzer ────────────────────────────────────────
        analysis: dict[str, Any]

        if inp.source_type in (SourceType.GITHUB_REPO, SourceType.GITHUB_PROFILE):
            if not inp.source_url:
                return self._error_result("source_url required for GitHub analysis", inp)
            analysis = await self.github.analyze(inp.source_url)

        elif inp.source_type == SourceType.CERTIFICATE:
            if not inp.file_path:
                return self._error_result("file_path required for certificate analysis", inp)
            analysis = await self.certificate.analyze(inp.file_path)

        elif inp.source_type == SourceType.PROJECT:
            path = inp.file_path or inp.source_url
            if not path:
                return self._error_result("file_path or source_url required for project analysis", inp)
            analysis = await self.project.analyze(path)

        elif inp.source_type in (SourceType.COURSEWORK, SourceType.HACKATHON, SourceType.DOCUMENT):
            # Treat as certificate/document for now
            if inp.file_path:
                analysis = await self.certificate.analyze(inp.file_path)
            else:
                analysis = self._basic_analysis(inp)
        else:
            analysis = self._basic_analysis(inp)

        # ── Check for errors ─────────────────────────────────────────
        if analysis.get("metadata", {}).get("error"):
            return self._error_result(
                analysis["metadata"]["error"], inp
            )

        # ── Build scoring result ─────────────────────────────────────
        raw_score = analysis.get("overall_score", 0.0)
        credibility_score = int(round(raw_score * 100))
        credibility_score = max(0, min(100, credibility_score))

        # Domain selection
        domains: list[DomainDetection] = analysis.get("domains", [])
        primary_domain = domains[0].domain if domains else "general"
        subdomain = domains[1].domain if len(domains) > 1 else None
        confidence = domains[0].confidence if domains else 0.5

        # Build breakdown
        breakdown: list[ScoringBreakdown] = []
        signals = analysis.get("signals", [])
        for sig in signals:
            breakdown.append(ScoringBreakdown(
                factor=sig.signal_name,
                weight=1.0 / max(len(signals), 1),
                raw_score=sig.normalized,
                weighted_score=sig.normalized / max(len(signals), 1),
                explanation=sig.detail,
            ))

        # Generate explanation
        explanation = self._build_explanation(
            credibility_score, primary_domain, signals, analysis.get("metadata", {})
        )

        # Generate artifact hash
        artifact_hash = self._build_artifact_hash(inp, analysis)

        result = ScoringResult(
            credibility_score=credibility_score,
            domain=primary_domain,
            subdomain=subdomain,
            confidence=confidence,
            explanation=explanation,
            breakdown=breakdown,
            mode=inp.mode,
            source_type=inp.source_type,
            artifact_hash=artifact_hash,
            source_url=inp.source_url,
        )

        logger.info(
            "Score: %d/100 (%s) — Domain: %s — Confidence: %.2f",
            credibility_score, credibility_label(credibility_score),
            primary_domain, confidence,
        )

        return result

    async def score_and_prepare(self, inp: ScoringInput) -> SkillRecordPayload:
        """Score evidence and produce ready-to-submit on-chain payload."""
        result = await self.score(inp)
        return SkillRecordPayload(
            mode=result.mode,
            domain=result.domain,
            subdomain=result.subdomain,
            credibility_score=result.credibility_score,
            artifact_hash=result.artifact_hash,
            source_type=result.source_type,
            source_url=result.source_url,
            issuer=result.issuer,
            timestamp=int(time.time()),
        )

    def _build_explanation(
        self,
        score: int,
        domain: str,
        signals: list,
        metadata: dict,
    ) -> str:
        """Build a human-readable explanation of the score."""
        level = credibility_label(score)
        parts = [f"Credibility: {level} ({score}/100) in {domain}."]

        # Top positive signals
        top_signals = sorted(signals, key=lambda s: s.normalized, reverse=True)[:3]
        if top_signals:
            strengths = [
                f"{s.signal_name.replace('_', ' ').title()}: {s.detail}"
                for s in top_signals if s.normalized >= 0.5
            ]
            if strengths:
                parts.append("Strengths: " + "; ".join(strengths) + ".")

        # Weaknesses
        weak_signals = [s for s in signals if s.normalized < 0.3]
        if weak_signals:
            weaknesses = [s.signal_name.replace("_", " ").title() for s in weak_signals[:2]]
            parts.append(f"Areas for improvement: {', '.join(weaknesses)}.")

        return " ".join(parts)

    @staticmethod
    def _build_artifact_hash(inp: ScoringInput, analysis: dict) -> str:
        """Create a deterministic hash representing the evidence bundle."""
        payload = {
            "mode": inp.mode.value,
            "source_type": inp.source_type.value,
            "source_url": inp.source_url,
            "file_path": inp.file_path,
            "overall_score": analysis.get("overall_score"),
            "domains": [d.domain for d in analysis.get("domains", [])],
            "metadata_hash": analysis.get("metadata", {}).get("sha256", ""),
        }
        canonical = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _basic_analysis(inp: ScoringInput) -> dict[str, Any]:
        """Fallback analysis for source types without specialized analyzers."""
        return {
            "signals": [],
            "domains": [],
            "metadata": {"source_type": inp.source_type.value},
            "overall_score": 0.3,
        }

    @staticmethod
    def _error_result(msg: str, inp: ScoringInput) -> ScoringResult:
        return ScoringResult(
            credibility_score=0,
            domain="unknown",
            confidence=0.0,
            explanation=f"Scoring failed: {msg}",
            mode=inp.mode,
            source_type=inp.source_type,
            artifact_hash="",
        )
