from typing import Optional

from sqlalchemy.orm import Session

from app import models


def record_status(
    db: Session,
    entity_type: str,
    entity_id: int,
    status: str,
    changed_by: Optional[int] = None,
    commit: bool = False,
) -> models.StatusHistory:
    entry = models.StatusHistory(
        entity_type=entity_type, entity_id=entity_id, status=status, changed_by=changed_by,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry
