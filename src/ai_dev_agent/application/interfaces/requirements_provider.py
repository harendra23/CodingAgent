from typing import Protocol


class RequirementsProvider(Protocol):
    def get_item(self, item_key: str) -> dict[str, object]: ...

    def search(self, query: str) -> list[dict[str, object]]: ...


class KnowledgeBaseProvider(Protocol):
    def search(self, query: str) -> list[dict[str, object]]: ...
