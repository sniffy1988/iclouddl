from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from iclouddownloader.db.models import AppLog


class LogService:
    def __init__(self, db: Session):
        self.db = db

    def list_logs(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        level: str | None = None,
        search: str | None = None,
    ) -> tuple[list[AppLog], int]:
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        q = select(AppLog)
        count_q = select(func.count(AppLog.id))
        if level:
            q = q.where(AppLog.level == level.upper())
            count_q = count_q.where(AppLog.level == level.upper())
        if search and search.strip():
            pattern = f"%{search.strip()}%"
            q = q.where(AppLog.message.ilike(pattern))
            count_q = count_q.where(AppLog.message.ilike(pattern))
        total = self.db.scalar(count_q) or 0
        rows = list(
            self.db.scalars(q.order_by(AppLog.id.desc()).offset(offset).limit(limit)).all()
        )
        return rows, int(total)

    def clear_logs(self) -> int:
        result = self.db.execute(delete(AppLog))
        self.db.commit()
        return result.rowcount or 0

    def log_count(self) -> int:
        return int(self.db.scalar(select(func.count(AppLog.id))) or 0)

    @staticmethod
    def serialize(row: AppLog) -> dict:
        return {
            "id": row.id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "level": row.level,
            "logger_name": row.logger_name,
            "message": row.message,
            "exception": row.exception,
            "source": row.source,
        }
