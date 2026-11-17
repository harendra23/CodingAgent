from dataclasses import dataclass, field
from uuid import UUID, uuid4

from ai_dev_agent.domain.enums.work_item_status import WorkItemStatus


@dataclass(slots=True)
class WorkItem:
    title: str
    description: str = ""
    id: UUID = field(default_factory=uuid4)
    status: WorkItemStatus = WorkItemStatus.OPEN
