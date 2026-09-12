"""Package shim: re-export the public API from db_manager.py/db_manager.py."""

from .db_manager import (  # noqa: F401
    DatabaseManager,
    init_db,
    save_claim,
    update_claim_status,
    save_verdict,
    save_evidence,
    get_all_claims,
    get_claim_by_id,
    get_stats,
    get_connection,
)
