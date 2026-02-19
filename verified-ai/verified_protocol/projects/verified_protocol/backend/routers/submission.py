"""
Backend Router — Submission
==============================

POST /submit — Submit a skill record on-chain (after AI scoring).
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

import algokit_utils
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import get_clients, send_params, APP_ID, MAX_RETRIES, RETRY_DELAY
from smart_contracts.artifacts.verified_protocol.verified_protocol_client import (
    SubmitSkillRecordArgs,
)

logger = logging.getLogger("backend.submission")
router = APIRouter(tags=["Submission"])


class SubmitRequest(BaseModel):
    skill_id: str = Field(..., description="Skill domain (e.g. 'python')")
    score: int = Field(..., ge=0, le=100)
    mode: str = Field(default="ai-graded")
    artifact_hash: Optional[str] = None
    subdomain: Optional[str] = None
    source_type: Optional[str] = None
    source_url: Optional[str] = None


class SubmitResponse(BaseModel):
    success: bool
    transaction_id: str
    skill_id: str
    score: int
    timestamp: int
    artifact_hash: str
    explorer_url: str
    mode: str


@router.post("/submit", response_model=SubmitResponse)
async def submit_record(req: SubmitRequest):
    """Submit a skill attestation record on-chain."""
    algorand, client, deployer_addr = get_clients()
    sp = send_params()

    timestamp = int(time.time())
    artifact_hash = req.artifact_hash or hashlib.sha256(
        f"{req.skill_id}:{req.score}:{timestamp}".encode()
    ).hexdigest()

    # Domain encoding: "domain:subdomain" if subdomain present
    domain = req.skill_id
    if req.subdomain:
        domain = f"{req.skill_id}:{req.subdomain}"

    # Fund MBR
    try:
        algorand.send.payment(
            algokit_utils.PaymentParams(
                amount=algokit_utils.AlgoAmount(micro_algo=500_000),
                sender=deployer_addr,
                receiver=client.app_address,
                validity_window=1000,
            ),
            send_params=sp,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"MBR funding failed: {exc}")

    # Submit
    args = SubmitSkillRecordArgs(
        mode=req.mode,
        domain=domain,
        score=req.score,
        artifact_hash=artifact_hash,
        timestamp=timestamp,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = client.send.submit_skill_record(args=args, send_params=sp)
            tx_id = result.tx_ids[0] if result.tx_ids else "N/A"

            return SubmitResponse(
                success=True,
                transaction_id=tx_id,
                skill_id=req.skill_id,
                score=req.score,
                timestamp=timestamp,
                artifact_hash=artifact_hash,
                explorer_url=f"https://testnet.explorer.perawallet.app/tx/{tx_id}",
                mode=req.mode,
            )
        except Exception as exc:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                raise HTTPException(status_code=502, detail=f"Submit failed: {exc}")
