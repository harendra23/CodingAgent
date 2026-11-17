from ai_dev_agent.domain.entities.work_item import WorkItem
from ai_dev_agent.domain.enums.work_item_status import WorkItemStatus


def test_work_item_defaults_to_open_with_unique_id() -> None:
    first = WorkItem(title="Add feature")
    second = WorkItem(title="Fix issue")

    assert first.status is WorkItemStatus.OPEN
    assert first.id != second.id
