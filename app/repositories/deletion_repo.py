"""Deletion task repository for outbox storage cleanups."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deletion_task import DeletionTask


class DeletionTaskRepository:
    async def create(
        self,
        session: AsyncSession,
        room_id: uuid.UUID,
        storage_keys: list[str],
        status: str = "pending",
    ) -> DeletionTask:
        task = DeletionTask(
            room_id=room_id,
            storage_keys=storage_keys,
            status=status,
        )
        session.add(task)
        await session.flush()
        return task

    async def get_retryable_tasks(
        self,
        session: AsyncSession,
        limit: int = 50,
    ) -> list[DeletionTask]:
        result = await session.execute(
            select(DeletionTask)
            .where(DeletionTask.status.in_(["pending", "failed"]))
            .order_by(DeletionTask.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_completed(
        self,
        session: AsyncSession,
        task_id: uuid.UUID,
    ) -> None:
        now = datetime.now(UTC)
        await session.execute(
            update(DeletionTask)
            .where(DeletionTask.id == task_id)
            .values(status="completed", updated_at=now)
        )

    async def mark_failed(
        self,
        session: AsyncSession,
        task_id: uuid.UUID,
        error_log: str,
    ) -> None:
        now = datetime.now(UTC)
        await session.execute(
            update(DeletionTask)
            .where(DeletionTask.id == task_id)
            .values(
                status="failed",
                retry_count=DeletionTask.retry_count + 1,
                error_log=error_log,
                updated_at=now,
            )
        )
