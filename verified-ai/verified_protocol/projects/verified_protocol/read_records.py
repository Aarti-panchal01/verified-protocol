"""
Verified Protocol — Read & Decode Skill Records
=================================================

Reads on-chain Box data for a given wallet address and decodes
the ARC-4 encoded SkillRecord structs into a JSON array.

Usage:
    poetry run python read_records.py <wallet_address>
    poetry run python read_records.py <wallet_address> --pretty
    poetry run python read_records.py <wallet_address> --output records.json

ARC-4 Decoding Note:
    The contract stores each record as a length-prefixed ARC-4 struct.
    The struct uses dynamic fields (mode, domain, artifact_hash) which
    require offset-based parsing. This script handles all of that
    automatically — no manual decoding step is needed.
"""

from __future__ import annotations

import argparse
import json
import logging
import struct
import sys
import time
from pathlib import Path

import algokit_utils
from algokit_utils.models.transaction import SendParams
from dotenv import load_dotenv

from smart_contracts.artifacts.verified_protocol.verified_protocol_client import (
    GetRecordCountArgs,
    GetSkillRecordsArgs,
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
logger = logging.getLogger("read_records")


# ─────────────────────────────────────────────────────────────────────────────
# ARC-4 Decoder
# ─────────────────────────────────────────────────────────────────────────────
def decode_skill_records(raw: bytes) -> list[dict]:
    """Decode length-prefixed ARC-4 SkillRecord structs from raw Box bytes.

    Wire format (per record):
        [2 bytes: big-endian record_len][record_len bytes: ARC-4 SkillRecord]

    ARC-4 SkillRecord struct:
        The struct has 3 dynamic fields (ARC4String) and 2 static fields
        (ARC4UInt64). The header layout is:

        Bytes 0-1   : offset to `mode` string data
        Bytes 2-3   : offset to `domain` string data
        Bytes 4-11  : `score` (uint64, big-endian)
        Bytes 12-13 : offset to `artifact_hash` string data
        Bytes 14-21 : `timestamp` (uint64, big-endian)

        Each ARC-4 string at its offset: [2-byte length][UTF-8 bytes]

    No manual decoding step is needed — this function handles everything.
    """
    records: list[dict] = []
    offset = 0
    data_len = len(raw)

    while offset < data_len:
        # Read 2-byte record length prefix
        if offset + 2 > data_len:
            break
        record_len = struct.unpack(">H", raw[offset : offset + 2])[0]
        offset += 2

        if offset + record_len > data_len:
            logger.warning("Truncated record at byte %d — stopping", offset)
            break

        rec = raw[offset : offset + record_len]
        offset += record_len

        try:
            # Static header parse
            mode_off = struct.unpack(">H", rec[0:2])[0]
            domain_off = struct.unpack(">H", rec[2:4])[0]
            score = struct.unpack(">Q", rec[4:12])[0]
            artifact_off = struct.unpack(">H", rec[12:14])[0]
            timestamp = struct.unpack(">Q", rec[14:22])[0]

            def _read_arc4_string(data: bytes, start: int) -> str:
                str_len = struct.unpack(">H", data[start : start + 2])[0]
                return data[start + 2 : start + 2 + str_len].decode(
                    "utf-8", errors="replace"
                )

            records.append(
                {
                    "mode": _read_arc4_string(rec, mode_off),
                    "domain": _read_arc4_string(rec, domain_off),
                    "score": score,
                    "artifact_hash": _read_arc4_string(rec, artifact_off),
                    "timestamp": timestamp,
                }
            )
        except Exception as e:
            logger.warning("Decode error: %s — raw hex: %s", e, rec.hex())
            records.append({"raw_hex": rec.hex(), "decode_error": str(e)})

    return records


# ─────────────────────────────────────────────────────────────────────────────
# Main logic
# ─────────────────────────────────────────────────────────────────────────────
def read_records(wallet_address: str) -> list[dict]:
    """Fetch and decode all skill records for a wallet."""
    load_dotenv(Path(__file__).parent / ".env")

    algorand = algokit_utils.AlgorandClient.from_environment()
    algorand.set_default_validity_window(1000)

    deployer = algorand.account.from_environment("DEPLOYER")

    client = VerifiedProtocolClient(
        algorand=algorand,
        app_id=APP_ID,
        default_sender=deployer.address,
    )

    send_params = SendParams(
        max_rounds_to_wait=1000,
        populate_app_call_resources=True,
    )

    # ── Get record count ─────────────────────────────────────────────
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            count_result = client.send.get_record_count(
                args=GetRecordCountArgs(wallet=wallet_address),
                send_params=send_params,
            )
            record_count = count_result.abi_return
            logger.info("Record count for %s: %s", wallet_address, record_count)
            break
        except Exception as exc:
            if attempt < MAX_RETRIES:
                logger.warning("Attempt %d failed — retrying…", attempt)
                time.sleep(RETRY_DELAY)
            else:
                raise

    if not record_count:
        logger.info("No records found for wallet %s", wallet_address)
        return []

    # ── Get raw box data ─────────────────────────────────────────────
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            raw_result = client.send.get_skill_records(
                args=GetSkillRecordsArgs(wallet=wallet_address),
                send_params=send_params,
            )
            raw_bytes: bytes = raw_result.abi_return  # type: ignore[assignment]
            break
        except Exception as exc:
            if attempt < MAX_RETRIES:
                logger.warning("Attempt %d failed — retrying…", attempt)
                time.sleep(RETRY_DELAY)
            else:
                raise

    return decode_skill_records(raw_bytes)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="read_records",
        description="Read & decode on-chain skill records for a wallet",
    )
    parser.add_argument(
        "wallet",
        type=str,
        help="Algorand wallet address (58-char base32)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON output",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Write JSON output to file instead of stdout",
    )

    args = parser.parse_args()

    try:
        records = read_records(args.wallet)

        indent = 2 if args.pretty else None
        json_str = json.dumps(records, indent=indent, ensure_ascii=False)

        if args.output:
            Path(args.output).write_text(json_str, encoding="utf-8")
            logger.info("Written %d records to %s", len(records), args.output)
        else:
            print(json_str)

    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        logger.error("Fatal: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
