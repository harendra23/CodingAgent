from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai_dev_agent.application.dtos.requirements_validation import (
    RequirementsAssessment,
    StoredRequirementValidation,
)
from ai_dev_agent.infrastructure.persistence.models import RequirementValidationModel


class RequirementValidationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def create(
        self,
        jira_issue_key: str,
        confluence_page_id: str,
        assessment: RequirementsAssessment,
        jira_content: str,
        confluence_content: str,
    ) -> StoredRequirementValidation:
        print(f"Creating RequirementValidationModel with assessment={assessment}")
        record = RequirementValidationModel(
            jira_issue_key=jira_issue_key,
            confluence_page_id=confluence_page_id,
            assessment=assessment.model_dump(mode="json"),
            jira_content=jira_content,
            confluence_content=confluence_content,
        )
        print(f"Creating RequirementValidationModel: {record}")
        async with self._sessions() as session:
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return self._to_dto(record)

    async def get(self, validation_id: UUID) -> StoredRequirementValidation | None:
        async with self._sessions() as session:
            record = await session.get(RequirementValidationModel, validation_id)
        if record is None:
            return None
        return self._to_dto(record)

    @staticmethod
    def _to_dto(record: RequirementValidationModel) -> StoredRequirementValidation:
        return StoredRequirementValidation(
            validation_id=record.id,
            jira_issue_key=record.jira_issue_key,
            confluence_page_id=record.confluence_page_id,
            assessment=record.assessment,
            jira_content=record.jira_content,
            confluence_content=record.confluence_content,
        )