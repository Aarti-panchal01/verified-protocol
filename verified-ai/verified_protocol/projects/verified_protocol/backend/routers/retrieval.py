"""
Backend Router — Retrieval
=============================

GET /wallet/{wallet}    — Fetch decoded records
GET /timeline/{wallet}  — Fetch records as timeline
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import fetch_records

logger = logging.getLogger("backend.retrieval")
router = APIRouter(tags=["Retrieval"])


class RecordItem(BaseModel):
    mode: Optional[str] = None
    domain: Optional[str] = None
    score: Optional[int] = None
    artifact_hash: Optional[str] = None
    timestamp: Optional[int] = None


class WalletResponse(BaseModel):
    wallet: str
    record_count: int
    records: list[dict]


class TimelineEvent(BaseModel):
    domain: str
    score: int
    mode: str
    timestamp: int
    artifact_hash: str
    date_display: str


class TimelineResponse(BaseModel):
    wallet: str
    events: list[TimelineEvent]


@router.get("/wallet/{wallet}", response_model=WalletResponse)
async def get_wallet_records(wallet: str):
    """Fetch and decode all skill records for a wallet."""
    try:
        records = fetch_records(wallet)
        return WalletResponse(
            wallet=wallet,
            record_count=len(records),
            records=records,
        )
    except Exception as exc:
        logger.error("Fetch failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/timeline/{wallet}", response_model=TimelineResponse)
async def get_timeline(wallet: str):
    """Fetch records as a chronological timeline."""
    try:
        records = fetch_records(wallet)

        events: list[TimelineEvent] = []
        for rec in sorted(records, key=lambda r: r.get("timestamp", 0)):
            ts = rec.get("timestamp", 0)
            import datetime
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)

            events.append(TimelineEvent(
                domain=rec.get("domain", "unknown"),
                score=rec.get("score", 0),
                mode=rec.get("mode", "unknown"),
                timestamp=ts,
                artifact_hash=rec.get("artifact_hash", ""),
                date_display=dt.strftime("%b %d, %Y • %H:%M UTC"),
            ))

        return TimelineResponse(wallet=wallet, events=events)
    except Exception as exc:
        logger.error("Timeline failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail=str(exc))
