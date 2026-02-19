"""
Verified Protocol — Interaction Script
========================================

Production-ready CLI for interacting with the deployed VerifiedProtocol
smart contract on Algorand Testnet (App ID: 755779875).

Usage:
    poetry run python interact.py submit <skill_id> <score> --artifact <file>

    poetry run python interact.py submit <skill_id> <score>
    poetry run python interact.py verify <skill_id>

Environment:
    Reads .env for ALGOD_SERVER, ALGOD_PORT, ALGOD_TOKEN, and DEPLOYER_MNEMONIC.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import struct
import sys
import time
from pathlib import Path

from hash_artifact import hash_file, hash_string

import algokit_utils
from algokit_utils.models.transaction import SendParams
from algosdk import encoding
from dotenv import load_dotenv

# ── Local typed client import ────────────────────────────────────────────────
from smart_contracts.artifacts.verified_protocol.verified_protocol_client import (
    SubmitSkillRecordArgs,
    GetRecordCountArgs,
    VerifiedProtocolClient,
)

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────
APP_ID = 755779875
MAX_RETRIES = 3
RETRY_DELAY = 4  # seconds

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("verified_protocol")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _is_retriable(exc: Exception) -> bool:
    """Return True if the error is a transient 'txn dead' round mismatch."""
    msg = str(exc).lower()
    return "txn dead" in msg or "round outside of" in msg


def _decode_skill_records(raw: bytes) -> list[dict]:
    """Walk the length-prefixed buffer and return decoded SkillRecord dicts.

    Wire format per record:
        [2 bytes: big-endian record_len] [record_len bytes: ARC-4 encoded SkillRecord]

    ARC-4 SkillRecord struct layout (dynamic — uses offset headers):
        Offsets (5 × 2 bytes = 10 bytes header):
            0-1   → offset to `mode` data
            2-3   → offset to `domain` data
            4-11  → score (uint64, 8 bytes)
            12-13 → offset to `artifact_hash` data
            14-21 → timestamp (uint64, 8 bytes)
        Each dynamic string is ARC-4 encoded: [2-byte length][utf-8 bytes]

    Since the struct has 3 dynamic fields (mode, domain, artifact_hash) and
    2 static fields (score, timestamp), the header is:
        [2B mode_offset][2B domain_offset][8B score][2B artifact_hash_offset][8B timestamp]
    Total static header = 2 + 2 + 8 + 2 + 8 = 22 bytes
    """
    records: list[dict] = []
    offset = 0
    data_len = len(raw)

    while offset < data_len:
        if offset + 2 > data_len:
            break
        record_len = struct.unpack(">H", raw[offset : offset + 2])[0]
        offset += 2

        if offset + record_len > data_len:
            logger.warning("Truncated record at offset %d — skipping remainder", offset)
            break

        rec = raw[offset : offset + record_len]
        offset += record_len

        try:
            # Parse the ARC-4 struct header offsets
            mode_off = struct.unpack(">H", rec[0:2])[0]
            domain_off = struct.unpack(">H", rec[2:4])[0]
            score = struct.unpack(">Q", rec[4:12])[0]
            artifact_off = struct.unpack(">H", rec[12:14])[0]
            timestamp = struct.unpack(">Q", rec[14:22])[0]

            # Read dynamic ARC-4 strings: [2-byte length prefix][utf-8 data]
            def read_arc4_string(data: bytes, start: int) -> str:
                str_len = struct.unpack(">H", data[start : start + 2])[0]
                return data[start + 2 : start + 2 + str_len].decode("utf-8", errors="replace")

            mode = read_arc4_string(rec, mode_off)
            domain = read_arc4_string(rec, domain_off)
            artifact_hash = read_arc4_string(rec, artifact_off)

            records.append(
                {
                    "mode": mode,
                    "domain": domain,
                    "score": score,
                    "artifact_hash": artifact_hash,
                    "timestamp": timestamp,
                }
            )
        except Exception as parse_err:
            logger.warning("Failed to decode record: %s", parse_err)
            records.append({"raw_hex": rec.hex(), "error": str(parse_err)})

    return records


# ─────────────────────────────────────────────────────────────────────────────
# Bootstrap — AlgorandClient + VerifiedProtocolClient
# ─────────────────────────────────────────────────────────────────────────────
def _bootstrap() -> tuple[algokit_utils.AlgorandClient, VerifiedProtocolClient, str]:
    """Return (algorand_client, protocol_client, deployer_address)."""
    load_dotenv(Path(__file__).parent / ".env")

    algorand = algokit_utils.AlgorandClient.from_environment()
    algorand.set_default_validity_window(1000)

    deployer = algorand.account.from_environment("DEPLOYER")
    logger.info("Deployer address : %s", deployer.address)

    client = VerifiedProtocolClient(
        algorand=algorand,
        app_id=APP_ID,
        default_sender=deployer.address,
    )
    logger.info("Connected to app : %d", client.app_id)
    logger.info("App address      : %s", client.app_address)

    return algorand, client, deployer.address


# ─────────────────────────────────────────────────────────────────────────────
# Core actions
# ─────────────────────────────────────────────────────────────────────────────
def submit_skill_record(skill_id: str, score: int, artifact_path: str | None = None) -> None:
    """Submit a new skill attestation record to the on-chain ledger.

    Parameters
    ----------
    skill_id : str
        A human-readable identifier for the skill (e.g. "python", "solidity").
    score : int
        Numeric score (0–100).
    """
    algorand, client, deployer_addr = _bootstrap()

    send_params = SendParams(
        max_rounds_to_wait=1000,
        populate_app_call_resources=True,
    )

    # Build arguments
    timestamp = int(time.time())

    # Use real file hash if artifact provided, otherwise auto-generate
    if artifact_path:
        artifact_hash = hash_file(artifact_path)
        logger.info("Hashed artifact file: %s", artifact_path)
    else:
        artifact_hash = hash_string(f"{skill_id}:{score}:{timestamp}")

    args = SubmitSkillRecordArgs(
        mode="ai-graded",
        domain=skill_id,
        score=score,
        artifact_hash=artifact_hash,
        timestamp=timestamp,
    )

    logger.info("─" * 60)
    logger.info("SUBMIT SKILL RECORD")
    logger.info("─" * 60)
    logger.info("  Skill ID       : %s", skill_id)
    logger.info("  Score           : %d", score)
    logger.info("  Timestamp       : %d", timestamp)
    logger.info("  Artifact hash   : %s", artifact_hash)

    # ── Fund MBR for Box storage ─────────────────────────────────────
    # Each new Box or Box resize requires additional Minimum Balance.
    # Send 0.5 ALGO to the app to cover potential MBR costs.
    logger.info("Funding app with 0.5 ALGO for Box MBR…")
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            algorand.send.payment(
                algokit_utils.PaymentParams(
                    amount=algokit_utils.AlgoAmount(micro_algo=500_000),
                    sender=deployer_addr,
                    receiver=client.app_address,
                    validity_window=1000,
                ),
                send_params=send_params,
            )
            logger.info("  MBR funding confirmed ✓")
            break
        except Exception as exc:
            if _is_retriable(exc) and attempt < MAX_RETRIES:
                logger.warning("  MBR funding attempt %d failed (retriable) — retrying in %ds…", attempt, RETRY_DELAY)
                time.sleep(RETRY_DELAY)
            else:
                logger.error("  MBR funding failed: %s", exc)
                raise

    # ── Submit skill record ──────────────────────────────────────────
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("Sending submit_skill_record transaction (attempt %d/%d)…", attempt, MAX_RETRIES)
            result = client.send.submit_skill_record(
                args=args,
                send_params=send_params,
            )

            tx_id = result.tx_ids[0] if result.tx_ids else "N/A"
            logger.info("─" * 60)
            logger.info("✅ SKILL RECORD SUBMITTED SUCCESSFULLY")
            logger.info("─" * 60)
            logger.info("  Transaction ID  : %s", tx_id)
            logger.info("  Confirmed round : %s", getattr(result, "confirmed_round", "N/A"))
            logger.info("  Explorer        : https://testnet.explorer.perawallet.app/tx/%s", tx_id)
            logger.info("─" * 60)
            return

        except Exception as exc:
            if _is_retriable(exc) and attempt < MAX_RETRIES:
                logger.warning("  Attempt %d hit transient error — retrying in %ds…\n  %s", attempt, RETRY_DELAY, exc)
                time.sleep(RETRY_DELAY)
            else:
                logger.error("❌ submit_skill_record failed: %s", exc)
                raise


def verify_skill_record(skill_id: str) -> None:
    """Verify / read all skill records for the deployer wallet.

    Parameters
    ----------
    skill_id : str
        Filter results to records matching this domain (skill_id).
        Pass "*" to show all records.
    """
    algorand, client, deployer_addr = _bootstrap()

    send_params = SendParams(
        max_rounds_to_wait=1000,
        populate_app_call_resources=True,
    )

    logger.info("─" * 60)
    logger.info("VERIFY SKILL RECORDS")
    logger.info("─" * 60)
    logger.info("  Wallet          : %s", deployer_addr)
    logger.info("  Filter (domain) : %s", skill_id if skill_id != "*" else "(all)")

    # ── Get record count ─────────────────────────────────────────────
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            count_result = client.send.get_record_count(
                args=GetRecordCountArgs(wallet=deployer_addr),
                send_params=send_params,
            )
            record_count = count_result.abi_return
            logger.info("  Total records   : %s", record_count)
            break
        except Exception as exc:
            if _is_retriable(exc) and attempt < MAX_RETRIES:
                logger.warning("  get_record_count attempt %d failed — retrying…", attempt)
                time.sleep(RETRY_DELAY)
            else:
                logger.error("❌ get_record_count failed: %s", exc)
                raise

    if not record_count:
        logger.info("─" * 60)
        logger.info("ℹ️  No skill records found for this wallet.")
        logger.info("─" * 60)
        return

    # ── Get raw box data ─────────────────────────────────────────────
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            from smart_contracts.artifacts.verified_protocol.verified_protocol_client import (
                GetSkillRecordsArgs,
            )

            raw_result = client.send.get_skill_records(
                args=GetSkillRecordsArgs(wallet=deployer_addr),
                send_params=send_params,
            )
            raw_bytes: bytes = raw_result.abi_return  # type: ignore[assignment]
            break
        except Exception as exc:
            if _is_retriable(exc) and attempt < MAX_RETRIES:
                logger.warning("  get_skill_records attempt %d failed — retrying…", attempt)
                time.sleep(RETRY_DELAY)
            else:
                logger.error("❌ get_skill_records failed: %s", exc)
                raise

    # ── Decode and display ───────────────────────────────────────────
    records = _decode_skill_records(raw_bytes)

    # Filter by domain if requested
    if skill_id != "*":
        records = [r for r in records if r.get("domain") == skill_id]

    logger.info("─" * 60)
    if not records:
        logger.info("ℹ️  No records found matching domain '%s'.", skill_id)
    else:
        logger.info("📋 SKILL RECORDS (%d found)", len(records))
        logger.info("─" * 60)
        for i, rec in enumerate(records, 1):
            logger.info("")
            logger.info("  Record #%d", i)
            logger.info("    Mode          : %s", rec.get("mode", "?"))
            logger.info("    Domain        : %s", rec.get("domain", "?"))
            logger.info("    Score         : %s", rec.get("score", "?"))
            logger.info("    Artifact Hash : %s", rec.get("artifact_hash", "?"))
            logger.info("    Timestamp     : %s", rec.get("timestamp", "?"))

            if rec.get("error"):
                logger.warning("    ⚠ Decode error: %s", rec["error"])

    logger.info("─" * 60)
    logger.info("✅ Verification complete.")
    logger.info("─" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="interact",
        description="Verified Protocol — Algorand Testnet Interaction CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── submit ───────────────────────────────────────────────────────
    submit_parser = subparsers.add_parser(
        "submit",
        help="Submit a new skill attestation record on-chain",
    )
    submit_parser.add_argument(
        "skill_id",
        type=str,
        help='Skill domain identifier (e.g. "python", "solidity")',
    )
    submit_parser.add_argument(
        "score",
        type=int,
        help="Numeric score (0–100)",
    )
    submit_parser.add_argument(
        "--artifact",
        type=str,
        default=None,
        help="Path to artifact file to hash (optional)",
    )

    # ── verify ───────────────────────────────────────────────────────
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify / read skill records for the deployer wallet",
    )
    verify_parser.add_argument(
        "skill_id",
        type=str,
        help='Skill domain to filter by, or "*" for all records',
    )

    args = parser.parse_args()

    try:
        if args.command == "submit":
            if not 0 <= args.score <= 100:
                logger.error("Score must be between 0 and 100 (got %d)", args.score)
                sys.exit(1)
            submit_skill_record(args.skill_id, args.score, args.artifact)

        elif args.command == "verify":
            verify_skill_record(args.skill_id)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user.")
        sys.exit(130)
    except Exception as exc:
        logger.error("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
