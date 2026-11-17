from typing import Protocol


class SourceControlProvider(Protocol):
    def get_file(self, repository: str, path: str, ref: str = "HEAD") -> str: ...

    def list_files(self, repository: str, path: str = "") -> list[str]: ...
