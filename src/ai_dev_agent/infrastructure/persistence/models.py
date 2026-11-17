from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ai_dev_agent.infrastructure.persistence.database import Base


class RequirementValidationModel(Base):
    __tablename__ = "requirement_validations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    jira_issue_key: Mapped[str] = mapped_column(String(128), nullable=False)
    confluence_page_id: Mapped[str] = mapped_column(String(64), nullable=False)
    assessment: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    jira_content: Mapped[str] = mapped_column(Text, nullable=False)
    confluence_content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )