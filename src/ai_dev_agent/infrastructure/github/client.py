from github import Auth, Github


class GitHubClient:
    def __init__(self, token: str) -> None:
        if not token:
            raise ValueError("A GitHub token is required")
        self._client = Github(auth=Auth.Token(token))

    def get_file(self, repository: str, path: str, ref: str = "HEAD") -> str:
        remote = self._client.get_repo(repository)
        content = remote.get_contents(path) if ref == "HEAD" else remote.get_contents(path, ref=ref)
        if isinstance(content, list):
            raise ValueError(f"{path!r} is a directory, not a file")
        return content.decoded_content.decode("utf-8")

    def list_files(self, repository: str, path: str = "") -> list[str]:
        content = self._client.get_repo(repository).get_contents(path)
        entries = content if isinstance(content, list) else [content]
        return [entry.path for entry in entries]
