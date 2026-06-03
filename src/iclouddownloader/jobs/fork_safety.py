"""Reset process-global clients after RQ fork (unsafe to share with parent).

Only call from ``os.register_at_fork(after_in_child=...)``. Do not call from
in-process SimpleWorker jobs — that closes the live RQ Redis pubsub connection.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def reset_fork_unsafe_globals() -> None:
    """Drop DB engine and event Redis clients inherited from the RQ parent process."""
    import logging as stdlib_logging

    from iclouddownloader import logging_setup
    from iclouddownloader.db import session as db_session
    from iclouddownloader.redis import client as redis_client
    from iclouddownloader.services.runtime_settings_service import get_effective_settings

    stdlib_logging.shutdown()
    logging_setup._configured = False

    try:
        get_effective_settings.cache_clear()
    except Exception:
        pass

    if db_session._engine is not None:
        try:
            db_session._engine.dispose()
        except Exception:
            logger.debug("Failed disposing SQLAlchemy engine after fork", exc_info=True)
        db_session._engine = None
        db_session._SessionLocal = None

    # Event pub/sub only — never close get_rq_redis(); RQ worker owns that socket.
    for attr in ("_client", "_subscriber_client"):
        conn = getattr(redis_client, attr, None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                logger.debug("Failed closing Redis client %s after fork", attr, exc_info=True)
            setattr(redis_client, attr, None)

    logging_setup._db_queue = None
    logging_setup._db_worker = None
