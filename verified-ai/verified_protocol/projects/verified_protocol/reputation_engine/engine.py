"""
Reputation Engine — Aggregation & Trust Scoring
=================================================

Computes off-chain reputation profiles from on-chain records.

Capabilities:
    • Aggregate records into domain-level scores
    • Time-decay weighting (recent records matter more)
    • Domain-specific strength assessment
    • Trust index computation
    • Credibility level assignment
    • Verification badge eligibility
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from typing import Any

from ai_scoring.models import (
    CredibilityLevel,
    DomainScore,
    ReputationProfile,
)

logger = logging.getLogger("reputation_engine")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
DECAY_HALF_LIFE_DAYS = 180     # Score halves every 180 days
BADGE_MIN_RECORDS = 3          # Min records for verification badge
BADGE_MIN_REPUTATION = 50     # Min reputation for badge
BADGE_MIN_DOMAINS = 1          # Min distinct domains for badge
MAX_SCORE_PER_RECORD = 100     # Cap per record


class ReputationEngine:
    """Computes aggregated reputation from decoded on-chain records."""

    def compute(
        self,
        wallet: str,
        records: list[dict[str, Any]],
    ) -> ReputationProfile:
        """Build a full reputation profile from decoded skill records.

        Parameters
        ----------
        wallet : str
            Algorand wallet address.
        records : list[dict]
            Decoded on-chain records with keys:
            mode, domain, score, artifact_hash, timestamp.
        """
        if not records:
            return ReputationProfile(
                wallet=wallet,
                total_reputation=0.0,
                credibility_level=CredibilityLevel.MINIMAL,
                total_records=0,
                trust_index=0.0,
                verification_badge=False,
            )

        now = int(time.time())

        # ── Group by domain ──────────────────────────────────────────
        domain_records: dict[str, list[dict]] = defaultdict(list)
        for rec in records:
            domain_key = self._normalize_domain(rec.get("domain", "general"))
            domain_records[domain_key].append(rec)

        # ── Compute per-domain scores ────────────────────────────────
        domain_scores: list[DomainScore] = []
        weighted_total = 0.0
        total_weight = 0.0

        for domain, recs in domain_records.items():
            domain_result = self._score_domain(domain, recs, now)
            domain_scores.append(domain_result)
            weighted_total += domain_result.score * len(recs)
            total_weight += len(recs)

        # ── Aggregate ────────────────────────────────────────────────
        if total_weight > 0:
            total_reputation = round(weighted_total / total_weight, 2)
        else:
            total_reputation = 0.0

        # ── Trust index (0.0–1.0) ────────────────────────────────────
        trust_index = self._compute_trust_index(
            total_reputation, len(records), len(domain_scores), now, records
        )

        # ── Credibility level ────────────────────────────────────────
        credibility_level = self._level_from_score(total_reputation)

        # ── Verification badge eligibility ───────────────────────────
        badge = (
            len(records) >= BADGE_MIN_RECORDS
            and total_reputation >= BADGE_MIN_REPUTATION
            and len(domain_scores) >= BADGE_MIN_DOMAINS
        )

        # ── Top domain ───────────────────────────────────────────────
        top_domain = None
        if domain_scores:
            top_domain = max(domain_scores, key=lambda d: d.score).domain

        # ── Active since ─────────────────────────────────────────────
        timestamps = [r.get("timestamp", 0) for r in records if r.get("timestamp")]
        active_since = min(timestamps) if timestamps else None

        # Sort domain scores descending
        domain_scores.sort(key=lambda ds: ds.score, reverse=True)

        profile = ReputationProfile(
            wallet=wallet,
            total_reputation=total_reputation,
            credibility_level=credibility_level,
            domain_scores=domain_scores,
            verification_badge=badge,
            total_records=len(records),
            trust_index=round(trust_index, 4),
            top_domain=top_domain,
            active_since=active_since,
        )

        logger.info(
            "Reputation for %s: %.1f (%s) — %d records — badge: %s",
            wallet[:12] + "…",
            total_reputation,
            credibility_level.value,
            len(records),
            badge,
        )

        return profile

    def _score_domain(
        self,
        domain: str,
        records: list[dict],
        now: int,
    ) -> DomainScore:
        """Score a single domain with time-decay weighting."""
        weighted_sum = 0.0
        weight_sum = 0.0
        latest_ts = 0

        for rec in records:
            raw_score = min(rec.get("score", 0), MAX_SCORE_PER_RECORD)
            ts = rec.get("timestamp", 0)
            latest_ts = max(latest_ts, ts)

            # Time-decay weight
            age_days = max(0, (now - ts) / 86400) if ts else 365
            decay = self._decay_weight(age_days)

            weighted_sum += raw_score * decay
            weight_sum += decay

        avg_score = weighted_sum / weight_sum if weight_sum > 0 else 0.0

        # Trend detection
        if len(records) >= 2:
            sorted_recs = sorted(records, key=lambda r: r.get("timestamp", 0))
            first_half = sorted_recs[: len(sorted_recs) // 2]
            second_half = sorted_recs[len(sorted_recs) // 2 :]
            avg_first = sum(r.get("score", 0) for r in first_half) / max(len(first_half), 1)
            avg_second = sum(r.get("score", 0) for r in second_half) / max(len(second_half), 1)

            if avg_second > avg_first + 5:
                trend = "rising"
            elif avg_second < avg_first - 5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return DomainScore(
            domain=domain,
            score=round(avg_score, 2),
            record_count=len(records),
            latest_timestamp=latest_ts,
            trend=trend,
        )

    def _compute_trust_index(
        self,
        reputation: float,
        record_count: int,
        domain_count: int,
        now: int,
        records: list[dict],
    ) -> float:
        """Compute trust index (0.0–1.0) from multiple factors."""
        # Factor 1: Reputation level (40%)
        rep_factor = min(1.0, reputation / 85) * 0.40

        # Factor 2: Record volume (20%)
        volume_factor = min(1.0, record_count / 10) * 0.20

        # Factor 3: Domain diversity (15%)
        diversity_factor = min(1.0, domain_count / 4) * 0.15

        # Factor 4: Consistency — std dev of scores (15%)
        scores = [r.get("score", 0) for r in records]
        if len(scores) >= 2:
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            std_dev = math.sqrt(variance)
            consistency = max(0, 1.0 - std_dev / 30)
        else:
            consistency = 0.5
        consistency_factor = consistency * 0.15

        # Factor 5: Longevity (10%)
        timestamps = [r.get("timestamp", 0) for r in records if r.get("timestamp")]
        if timestamps:
            span_days = (max(timestamps) - min(timestamps)) / 86400
            longevity = min(1.0, span_days / 180)
        else:
            longevity = 0.0
        longevity_factor = longevity * 0.10

        return rep_factor + volume_factor + diversity_factor + consistency_factor + longevity_factor

    @staticmethod
    def _decay_weight(age_days: float) -> float:
        """Exponential decay weight based on record age."""
        return math.exp(-0.693 * age_days / DECAY_HALF_LIFE_DAYS)

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        """Normalize domain string (handle 'domain:subdomain' format)."""
        return domain.split(":")[0].lower().strip()

    @staticmethod
    def _level_from_score(score: float) -> CredibilityLevel:
        if score >= 90:
            return CredibilityLevel.EXCEPTIONAL
        if score >= 70:
            return CredibilityLevel.STRONG
        if score >= 50:
            return CredibilityLevel.MODERATE
        if score >= 30:
            return CredibilityLevel.DEVELOPING
        return CredibilityLevel.MINIMAL
