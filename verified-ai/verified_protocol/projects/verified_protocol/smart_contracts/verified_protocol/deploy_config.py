"""Deploy configuration for the Verified Protocol smart contract.

Targets Algorand TestNet via public nodes (AlgoNode / Nodely).
Uses a widened validity window (50 rounds) and extended confirmation
polling to prevent "txn dead: round outside of range" errors.
"""

import logging
import time

import algokit_utils
from algokit_utils.models.transaction import SendParams

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5


def _is_txn_dead(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "txn dead" in msg or "round outside of" in msg


def deploy() -> None:
    """Deploy the Verified Protocol to TestNet."""

    from smart_contracts.artifacts.verified_protocol.verified_protocol_client import (
        VerifiedProtocolFactory,
    )

    # ── Client setup ─────────────────────────────────────────────────
    algorand = algokit_utils.AlgorandClient.from_environment()
    algorand.set_default_validity_window(1000)

    deployer_ = algorand.account.from_environment("DEPLOYER")
    logger.info(f"Deployer address: {deployer_.address}")

    factory = algorand.client.get_typed_app_factory(
        VerifiedProtocolFactory, default_sender=deployer_.address
    )

    # ── Send params ──────────────────────────────────────────────────
    send_params = SendParams(
        max_rounds_to_wait=1000,
        populate_app_call_resources=True,
    )

    # ── Deploy with retry ────────────────────────────────────────────
    app_client = None
    result = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"Deploy attempt {attempt}/{MAX_RETRIES}…")
            app_client, result = factory.deploy(
                on_update=algokit_utils.OnUpdate.AppendApp,
                on_schema_break=algokit_utils.OnSchemaBreak.AppendApp,
                send_params=send_params,
            )
            logger.info(
                f"Deploy succeeded: {app_client.app_name} "
                f"(app_id={app_client.app_id})"
            )
            break
        except Exception as exc:
            if _is_txn_dead(exc) and attempt < MAX_RETRIES:
                logger.warning(
                    f"Attempt {attempt} hit 'txn dead' — "
                    f"retrying in {RETRY_DELAY_SECONDS}s…\n  {exc}"
                )
                time.sleep(RETRY_DELAY_SECONDS)
            else:
                logger.error(f"Deploy failed: {exc}")
                raise

    if app_client is None or result is None:
        raise RuntimeError("Deployment did not produce a valid result")

    # ── Fund app for Box MBR ─────────────────────────────────────────
    if result.operation_performed in [
        algokit_utils.OperationPerformed.Create,
        algokit_utils.OperationPerformed.Replace,
    ]:
        logger.info(f"Funding app {app_client.app_id} with 1 ALGO for Box MBR…")
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                algorand.send.payment(
                    algokit_utils.PaymentParams(
                        amount=algokit_utils.AlgoAmount(algo=1),
                        sender=deployer_.address,
                        receiver=app_client.app_address,
                        validity_window=1000,
                    ),
                    send_params=send_params,
                )
                logger.info("Funding confirmed.")
                break
            except Exception as exc:
                if _is_txn_dead(exc) and attempt < MAX_RETRIES:
                    logger.warning(
                        f"Funding attempt {attempt} hit 'txn dead' — "
                        f"retrying in {RETRY_DELAY_SECONDS}s…"
                    )
                    time.sleep(RETRY_DELAY_SECONDS)
                else:
                    raise

    logger.info(
        f"✅ Deployed {app_client.app_name} (app_id={app_client.app_id}) "
        f"at {app_client.app_address}"
    )
