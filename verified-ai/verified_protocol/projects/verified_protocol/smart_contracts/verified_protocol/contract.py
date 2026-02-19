"""
Verified Protocol — Skill Reputation Smart Contract
=====================================================

A production-safe, append-only skill reputation ledger on Algorand.

Architecture:
  • One Box per wallet, keyed by the sender's 32-byte address.
  • Each Box stores a contiguous sequence of ARC-4 encoded SkillRecord structs.
  • New records are appended; existing records are never mutated (append-only).
  • No global or local state is used — all data lives in Boxes.

Box layout (per wallet):
  ┌──────────────────────────────────────────────────────────────┐
  │ SkillRecord₁ bytes ‖ SkillRecord₂ bytes ‖ … ‖ SkillRecordₙ │
  └──────────────────────────────────────────────────────────────┘
  Records are ARC-4 encoded structs containing dynamic-length fields
  (mode, domain, artifact_hash) so each encoded record is variable-length.
  We prefix every record with a 2-byte big-endian length header so the
  reader can walk the buffer and split individual records deterministically.

  Per-record wire format:
    [2 bytes: record_len (big-endian)] [record_len bytes: ARC-4 encoded SkillRecord]
"""

from algopy import ARC4Contract, Account, Bytes, Txn, UInt64, op, subroutine
from algopy.arc4 import String as ARC4String, UInt64 as ARC4UInt64, Struct, abimethod


# ---------------------------------------------------------------------------
# ARC-4 Struct — SkillRecord
# ---------------------------------------------------------------------------
class SkillRecord(Struct, kw_only=True):
    """A single, immutable skill attestation record.

    Fields
    ------
    mode : ARC4String
        The evaluation mode (e.g. "ai-graded", "peer-review", "self-assessed").
    domain : ARC4String
        The skill domain (e.g. "solidity", "rust", "python").
    score : ARC4UInt64
        Numeric score (0–100 or any uint64 range).
    artifact_hash : ARC4String
        IPFS CID / SHA-256 hash of the proof artifact.
    timestamp : ARC4UInt64
        Unix epoch timestamp of when the record was created.
    """

    mode: ARC4String
    domain: ARC4String
    score: ARC4UInt64
    artifact_hash: ARC4String
    timestamp: ARC4UInt64


# ---------------------------------------------------------------------------
# Helper subroutines (pure logic, no state)
# ---------------------------------------------------------------------------
@subroutine
def _uint16_to_bytes(value: UInt64) -> Bytes:
    """Encode a uint64 value as a 2-byte big-endian prefix (max 65535)."""
    return op.extract(op.itob(value), 6, 2)


@subroutine
def _bytes_to_uint16(raw: Bytes) -> UInt64:
    """Decode a 2-byte big-endian value back to UInt64."""
    # Pad to 8 bytes so btoi works correctly.
    return op.btoi(op.bzero(6) + raw)


# ---------------------------------------------------------------------------
# Contract
# ---------------------------------------------------------------------------
class VerifiedProtocol(ARC4Contract):
    """Skill Reputation Protocol — append-only Box ledger per wallet.

    Every wallet (Algorand account) gets its own Box whose key is the
    raw 32-byte sender address.  Skill records are ARC-4 encoded and
    length-prefixed so they can be deterministically parsed off-chain.

    ABI Methods
    -----------
    submit_skill_record(mode, domain, score, artifact_hash, timestamp)
        Append a new SkillRecord to the caller's Box.
    get_skill_records(wallet) → Bytes
        Return the raw Box bytes for any wallet (read-only).
    """

    # ── Write ─────────────────────────────────────────────────────────
    @abimethod()
    def submit_skill_record(
        self,
        mode: ARC4String,
        domain: ARC4String,
        score: ARC4UInt64,
        artifact_hash: ARC4String,
        timestamp: ARC4UInt64,
    ) -> None:
        """Append a new SkillRecord to the sender's Box.

        • If the Box does not exist yet, it is created with exactly the
          bytes of the first length-prefixed record.
        • If the Box already exists, the new record is appended at the end.
        • The caller must ensure adequate MBR (Minimum Balance Requirement)
          funding for box creation / growth via an accompanying payment txn.
        """
        # 1. Build the ARC-4 encoded record
        record = SkillRecord(
            mode=mode,
            domain=domain,
            score=score,
            artifact_hash=artifact_hash,
            timestamp=timestamp,
        )
        record_bytes: Bytes = record.bytes

        # 2. Build the length-prefixed payload: [2-byte len][record bytes]
        record_len = record_bytes.length
        payload = _uint16_to_bytes(record_len) + record_bytes

        # 3. Sender key (raw 32-byte address)
        sender_key = Txn.sender.bytes

        # 4. Safe box handling — check existence first
        _existing_data, box_exists = op.Box.get(sender_key)

        if box_exists:
            # Box already exists — compute current size and resize + append.
            current_length = op.Box.length(sender_key)[0]
            payload_length = payload.length
            new_total = current_length + payload_length

            # Resize the box to accommodate the new record
            op.Box.resize(sender_key, new_total)
            # Write the new payload at the old end offset
            op.Box.replace(sender_key, current_length, payload)
        else:
            # Box does not exist — create with the initial payload via put.
            op.Box.put(sender_key, payload)

    # ── Read ──────────────────────────────────────────────────────────
    @abimethod(readonly=True)
    def get_skill_records(self, wallet: Account) -> Bytes:
        """Return the raw Box bytes for a given wallet address.

        Returns empty bytes if the wallet has no records.
        Callers can decode the result off-chain by iterating:
          1. Read 2-byte big-endian length prefix → record_len
          2. Read next record_len bytes → ARC-4 SkillRecord
          3. Repeat until buffer exhausted.
        """
        box_data, box_exists = op.Box.get(wallet.bytes)
        if box_exists:
            return box_data
        return Bytes(b"")

    # ── Utility ───────────────────────────────────────────────────────
    @abimethod(readonly=True)
    def get_record_count(self, wallet: Account) -> UInt64:
        """Return the number of skill records stored for a wallet.

        Walks the length-prefixed buffer and counts entries.
        Returns 0 if the wallet has no Box.
        """
        box_data, box_exists = op.Box.get(wallet.bytes)
        if not box_exists:
            return UInt64(0)

        count = UInt64(0)
        offset = UInt64(0)
        data_len = box_data.length

        while offset < data_len:
            # Read the 2-byte length prefix
            record_len = _bytes_to_uint16(op.extract(box_data, offset, 2))
            # Advance past the prefix + record body
            offset = offset + UInt64(2) + record_len
            count = count + UInt64(1)

        return count
