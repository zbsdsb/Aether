from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.database import Provider


def disable_provider_for_import_failure(
    *,
    db: Session,
    provider_id: str | None,
) -> Provider | None:
    """导入态验证失败时停用当前 Provider，避免继续参与调度。"""

    if not provider_id:
        return None

    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if provider is None:
        return None

    provider.is_active = False
    provider.updated_at = datetime.now(timezone.utc)
    return provider
