"""
Backend Router — Reputation
==============================

GET /reputation/{wallet} — Compute reputation profile
GET /verify/{wallet}     — On-chain verification status
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import fetch_records
from reputation_engine.engine import ReputationEngine

logger = logging.getLogger("backend.reputation")
router = APIRouter(tags=["Reputation"])

rep_engine = ReputationEngine()


class DomainScoreResponse(BaseModel):
    domain: str
    score: float
    record_count: int
    latest_timestamp: int
    trend: str


class ReputationResponse(BaseModel):
    wallet: str
    total_reputation: float
    credibility_level: str
    trust_index: float
    verification_badge: bool
    total_records: int
    top_domain: Optional[str] = None
    active_since: Optional[int] = None
    domain_scores: list[DomainScoreResponse] = []


class VerifyWalletResponse(BaseModel):
    wallet: str
    verified: bool
    record_count: int
    records: list[dict]
    message: str
    reputation: Optional[ReputationResponse] = None


@router.get("/reputation/{wallet}", response_model=ReputationResponse)
async def get_reputation(wallet: str):
    """Compute full reputation profile for a wallet."""
    try:
        records = fetch_records(wallet)
        profile = rep_engine.compute(wallet, records)

        return ReputationResponse(
            wallet=profile.wallet,
            total_reputation=profile.total_reputation,
            credibility_level=profile.credibility_level.value,
            trust_index=profile.trust_index,
            verification_badge=profile.verification_badge,
            total_records=profile.total_records,
            top_domain=profile.top_domain,
            active_since=profile.active_since,
            domain_scores=[
                DomainScoreResponse(
                    domain=ds.domain,
                    score=ds.score,
                    record_count=ds.record_count,
                    latest_timestamp=ds.latest_timestamp,
                    trend=ds.trend,
                )
                for ds in profile.domain_scores
            ],
        )
    except Exception as exc:
        logger.error("Reputation failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/verify/{wallet}", response_model=VerifyWalletResponse)
async def verify_wallet(wallet: str):
    """Verify a wallet's on-chain records + reputation."""
    try:
        records = fetch_records(wallet)

        if not records:
            return VerifyWalletResponse(
                wallet=wallet,
                verified=False,
                record_count=0,
                records=[],
                message="No skill records found for this wallet.",
            )

        profile = rep_engine.compute(wallet, records)

        rep = ReputationResponse(
            wallet=profile.wallet,
            total_reputation=profile.total_reputation,
            credibility_level=profile.credibility_level.value,
            trust_index=profile.trust_index,
            verification_badge=profile.verification_badge,
            total_records=profile.total_records,
            top_domain=profile.top_domain,
            active_since=profile.active_since,
            domain_scores=[
                DomainScoreResponse(
                    domain=ds.domain,
                    score=ds.score,
                    record_count=ds.record_count,
                    latest_timestamp=ds.latest_timestamp,
                    trend=ds.trend,
                )
                for ds in profile.domain_scores
            ],
        )

        return VerifyWalletResponse(
            wallet=wallet,
            verified=profile.verification_badge,
            record_count=len(records),
            records=records,
            message=f"{'✅ Verified' if profile.verification_badge else '⚠ Not yet verified'} — {profile.credibility_level.value} credibility ({profile.total_reputation:.0f}/100) with {len(records)} on-chain record(s).",
            reputation=rep,
        )
    except Exception as exc:
        logger.error("Verify failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))
