"""
Verified Protocol — Artifact Hash Engine
==========================================

Computes a SHA-256 hash of any file, suitable for on-chain attestation
as the `artifact_hash` field in a SkillRecord.

Usage (standalone):
    poetry run python hash_artifact.py <file_path>
    poetry run python hash_artifact.py <file_path> --algo sha512

Usage (as module):
    from hash_artifact import hash_file
    digest = hash_file("path/to/artifact.pdf")
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Core hash function
# ─────────────────────────────────────────────────────────────────────────────
SUPPORTED_ALGORITHMS = ("sha256", "sha384", "sha512", "sha3_256", "blake2b")
CHUNK_SIZE = 8192  # 8 KB — memory-efficient for large files


def hash_file(file_path: str | Path, algorithm: str = "sha256") -> str:
    """Compute the hex digest of a file using the given hash algorithm.

    Parameters
    ----------
    file_path : str | Path
        Path to the file to hash.
    algorithm : str
        Hash algorithm name (default: sha256).

    Returns
    -------
    str
        Lowercase hex digest string.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    ValueError
        If the algorithm is not supported.
    """
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported algorithm '{algorithm}'. "
            f"Choose from: {', '.join(SUPPORTED_ALGORITHMS)}"
        )

    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)

    return h.hexdigest()


def hash_string(data: str, algorithm: str = "sha256") -> str:
    """Compute the hex digest of a UTF-8 string.

    Parameters
    ----------
    data : str
        The string to hash.
    algorithm : str
        Hash algorithm name (default: sha256).

    Returns
    -------
    str
        Lowercase hex digest string.
    """
    if algorithm not in SUPPORTED_ALGORITHMS:
        raise ValueError(
            f"Unsupported algorithm '{algorithm}'. "
            f"Choose from: {', '.join(SUPPORTED_ALGORITHMS)}"
        )
    return hashlib.new(algorithm, data.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        prog="hash_artifact",
        description="Compute SHA-256 (or other) hash of an artifact file",
    )
    parser.add_argument(
        "file_path",
        type=str,
        help="Path to the artifact file",
    )
    parser.add_argument(
        "--algo",
        type=str,
        default="sha256",
        choices=SUPPORTED_ALGORITHMS,
        help="Hash algorithm (default: sha256)",
    )

    args = parser.parse_args()

    try:
        digest = hash_file(args.file_path, args.algo)
        print(f"{args.algo}:{digest}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
