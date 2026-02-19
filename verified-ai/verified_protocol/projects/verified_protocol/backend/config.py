"""
Backend — Shared Configuration
================================

Algorand client, contract client, and shared utilities.
"""

from __future__ import annotations

import logging
import struct
from pathlib import Path

import algokit_utils
from algokit_utils.models.transaction import SendParams
from dotenv import load_dotenv

# ── Fix import path ─────────────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from smart_contracts.artifacts.verified_protocol.verified_protocol_client import (
    GetRecordCountArgs,
    GetSkillRecordsArgs,
    SubmitSkillRecordArgs,
    VerifiedProtocolClient,
)

logger = logging.getLogger("backend.config")

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────
APP_ID = 755779875
MAX_RETRIES = 3
RETRY_DELAY = 4

# ─────────────────────────────────────────────────────────────────────────────
# Load .env
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ─────────────────────────────────────────────────────────────────────────────
# Singleton clients
# ─────────────────────────────────────────────────────────────────────────────
_algorand: algokit_utils.AlgorandClient | None = None
_client: VerifiedProtocolClient | None = None
_deployer_addr: str | None = None


def get_clients() -> tuple[algokit_utils.AlgorandClient, VerifiedProtocolClient, str]:
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


def send_params() -> SendParams:
    return SendParams(max_rounds_to_wait=1000, populate_app_call_resources=True)


# ─────────────────────────────────────────────────────────────────────────────
# ARC-4 Decoder (shared)
# ─────────────────────────────────────────────────────────────────────────────
def decode_skill_records(raw: bytes) -> list[dict]:
    """Decode length-prefixed ARC-4 SkillRecord structs."""
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

            def _s(data: bytes, start: int) -> str:
                sl = struct.unpack(">H", data[start : start + 2])[0]
                return data[start + 2 : start + 2 + sl].decode("utf-8", errors="replace")

            records.append({
                "mode": _s(rec, mode_off),
                "domain": _s(rec, domain_off),
                "score": score,
                "artifact_hash": _s(rec, artifact_off),
                "timestamp": timestamp,
            })
        except Exception as e:
            records.append({"raw_hex": rec.hex(), "decode_error": str(e)})

    return records


def fetch_records(wallet: str) -> list[dict]:
    """Fetch and decode records for a wallet. Helper used by multiple routers."""
    _, client, _ = get_clients()
    sp = send_params()

    count_result = client.send.get_record_count(
        args=GetRecordCountArgs(wallet=wallet), send_params=sp
    )
    count = count_result.abi_return or 0

    if count == 0:
        return []

    raw_result = client.send.get_skill_records(
        args=GetSkillRecordsArgs(wallet=wallet), send_params=sp
    )
    raw_return = raw_result.abi_return
    raw_bytes = bytes(raw_return) if not isinstance(raw_return, bytes) else raw_return
    return decode_skill_records(raw_bytes)
