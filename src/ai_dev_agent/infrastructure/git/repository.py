import subprocess
from pathlib import Path


class LocalRepository:
    def __init__(self, path: Path) -> None:
        self._path = path.resolve()
        if not self._path.is_dir():
            raise ValueError("Repository path must be an existing directory")

    def status(self) -> str:
        result = subprocess.run(
            ["git", "-C", str(self._path), "status", "--short"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout
