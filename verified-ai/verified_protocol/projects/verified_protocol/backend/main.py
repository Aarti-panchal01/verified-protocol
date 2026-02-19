"""
Verified Protocol — FastAPI Backend
=====================================

REST API for interacting with the VerifiedProtocol smart contract
on Algorand Testnet.

Endpoints:
    POST /submit         — Submit a new skill record
    GET  /records/{wallet} — Fetch decoded records for a wallet
    GET  /verify/{wallet}  — Verify records + return verification status

Run:
    cd projects/verified_protocol
    poetry run uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import hashlib
import logging
import struct
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Fix import path so we can import from parent ────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import algokit_utils
from algokit_utils.models.transaction import SendParams
from dotenv import load_dotenv

from smart_contracts.artifacts.verified_protocol.verified_protocol_client import (
    GetRecordCountArgs,
    GetSkillRecordsArgs,
    SubmitSkillRecordArgs,
    VerifiedProtocolClient,
)

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
APP_ID = 755779875
MAX_RETRIES = 3
RETRY_DELAY = 4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("backend")

# ── Load .env from project root ─────────────────────────────────────────────
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ─────────────────────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Verified Protocol API",
    description="REST API for the Verified Protocol skill reputation ledger on Algorand Testnet",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Models
# ─────────────────────────────────────────────────────────────────────────────
class SubmitRequest(BaseModel):
    skill_id: str = Field(..., description="Skill domain (e.g. 'python', 'solidity')")
    score: int = Field(..., ge=0, le=100, description="Score between 0 and 100")
    mode: str = Field(default="ai-graded", description="Evaluation mode")
    artifact_hash: str | None = Field(default=None, description="Optional artifact hash (auto-generated if omitted)")


class SubmitResponse(BaseModel):
    success: bool
    transaction_id: str
    skill_id: str
    score: int
    timestamp: int
    artifact_hash: str
    explorer_url: str


class SkillRecord(BaseModel):
    mode: str
    domain: str
    score: int
    artifact_hash: str
    timestamp: int


class RecordsResponse(BaseModel):
    wallet: str
    record_count: int
    records: list[SkillRecord | dict]


class VerifyResponse(BaseModel):
    wallet: str
    verified: bool
    record_count: int
    records: list[SkillRecord | dict]
    message: str


# ─────────────────────────────────────────────────────────────────────────────
# Algorand Client (singleton-ish)
# ─────────────────────────────────────────────────────────────────────────────
_algorand: algokit_utils.AlgorandClient | None = None
_client: VerifiedProtocolClient | None = None
_deployer_addr: str | None = None


def _get_clients() -> tuple[algokit_utils.AlgorandClient, VerifiedProtocolClient, str]:
    """Lazy-init Algorand + VerifiedProtocol clients."""
    global _algorand, _client, _deployer_addr

    if _algorand is None:
        _algorand = algokit_utils.AlgorandClient.from_environment()
        _algorand.set_default_validity_window(1000)

        deployer = _algorand.account.from_environment("DEPLOYER")
        _deployer_addr = deployer.address

        _client = VerifiedProtocolClient(
            algorand=_algorand,
            app_id=APP_ID,
            default_sender=_deployer_addr,
        )
        logger.info("Algorand client initialized — deployer: %s", _deployer_addr)

    return _algorand, _client, _deployer_addr  # type: ignore[return-value]


def _send_params() -> SendParams:
    return SendParams(max_rounds_to_wait=1000, populate_app_call_resources=True)


# ─────────────────────────────────────────────────────────────────────────────
# ARC-4 Decoder
# ─────────────────────────────────────────────────────────────────────────────
def _decode_skill_records(raw: bytes) -> list[dict]:
    """Decode length-prefixed ARC-4 SkillRecord structs from raw Box bytes."""
    records: list[dict] = []
    offset = 0
    data_len = len(raw)

    while offset < data_len:
        if offset + 2 > data_len:
            break
        record_len = struct.unpack(">H", raw[offset : offset + 2])[0]
        offset += 2

        if offset + record_len > data_len:
            break

        rec = raw[offset : offset + record_len]
        offset += record_len

        try:
            mode_off = struct.unpack(">H", rec[0:2])[0]
            domain_off = struct.unpack(">H", rec[2:4])[0]
            score = struct.unpack(">Q", rec[4:12])[0]
            artifact_off = struct.unpack(">H", rec[12:14])[0]
            timestamp = struct.unpack(">Q", rec[14:22])[0]

            def _read_str(data: bytes, start: int) -> str:
                str_len = struct.unpack(">H", data[start : start + 2])[0]
                return data[start + 2 : start + 2 + str_len].decode("utf-8", errors="replace")

            records.append({
                "mode": _read_str(rec, mode_off),
                "domain": _read_str(rec, domain_off),
                "score": score,
                "artifact_hash": _read_str(rec, artifact_off),
                "timestamp": timestamp,
            })
        except Exception as e:
            records.append({"raw_hex": rec.hex(), "decode_error": str(e)})

    return records


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "name": "Verified Protocol API",
        "version": "1.0.0",
        "app_id": APP_ID,
        "network": "algorand-testnet",
    }


@app.post("/submit", response_model=SubmitResponse)
async def submit_record(req: SubmitRequest):
    """Submit a new skill attestation record on-chain."""
    algorand, client, deployer_addr = _get_clients()
    sp = _send_params()

    timestamp = int(time.time())
    artifact_hash = req.artifact_hash or hashlib.sha256(
        f"{req.skill_id}:{req.score}:{timestamp}".encode()
    ).hexdigest()

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
        domain=req.skill_id,
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
            )
        except Exception as exc:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
            else:
                raise HTTPException(status_code=502, detail=f"submit failed: {exc}")


@app.get("/records/{wallet}", response_model=RecordsResponse)
async def get_records(wallet: str):
    """Fetch and decode all skill records for a wallet."""
    _, client, _ = _get_clients()
    sp = _send_params()

    # Get count
    try:
        count_result = client.send.get_record_count(
            args=GetRecordCountArgs(wallet=wallet), send_params=sp
        )
        count = count_result.abi_return or 0
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"get_record_count failed: {exc}")

    if count == 0:
        return RecordsResponse(wallet=wallet, record_count=0, records=[])

    # Get raw data
    try:
        raw_result = client.send.get_skill_records(
            args=GetSkillRecordsArgs(wallet=wallet), send_params=sp
        )
        raw_bytes: bytes = raw_result.abi_return  # type: ignore[assignment]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"get_skill_records failed: {exc}")

    records = _decode_skill_records(raw_bytes)
    return RecordsResponse(wallet=wallet, record_count=len(records), records=records)


@app.get("/verify/{wallet}", response_model=VerifyResponse)
async def verify_wallet(wallet: str):
    """Verify a wallet's on-chain skill records and return verification status."""
    _, client, _ = _get_clients()
    sp = _send_params()

    try:
        count_result = client.send.get_record_count(
            args=GetRecordCountArgs(wallet=wallet), send_params=sp
        )
        count = count_result.abi_return or 0
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"get_record_count failed: {exc}")

    if count == 0:
        return VerifyResponse(
            wallet=wallet,
            verified=False,
            record_count=0,
            records=[],
            message="No skill records found for this wallet.",
        )

    try:
        raw_result = client.send.get_skill_records(
            args=GetSkillRecordsArgs(wallet=wallet), send_params=sp
        )
        raw_bytes: bytes = raw_result.abi_return  # type: ignore[assignment]
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"get_skill_records failed: {exc}")

    records = _decode_skill_records(raw_bytes)

    return VerifyResponse(
        wallet=wallet,
        verified=True,
        record_count=len(records),
        records=records,
        message=f"Wallet verified with {len(records)} on-chain skill record(s).",
    )
