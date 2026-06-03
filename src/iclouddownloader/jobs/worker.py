"""RQ worker factory (SQLite-safe SimpleWorker for local installs)."""

from __future__ import annotations

import logging

from redis import Redis
from rq import Queue
from rq.worker import SimpleWorker, Worker

from iclouddownloader.config import get_settings
from iclouddownloader.db.session import sqlite_file_path

logger = logging.getLogger(__name__)


def create_rq_worker(queues: list[Queue], connection: Redis) -> Worker | SimpleWorker:
    """Use in-process SimpleWorker for SQLite; forked Worker for server DBs."""
    if sqlite_file_path(get_settings().database_url):
        logger.info("RQ SimpleWorker enabled (in-process jobs; required for SQLite)")
        return SimpleWorker(queues, connection=connection)
    logger.info("RQ Worker enabled (forked job processes)")
    return Worker(queues, connection=connection)
