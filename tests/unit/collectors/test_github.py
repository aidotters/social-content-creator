"""GitHubCollectorのテスト。"""

import logging

import httpx
import pytest

from src.collectors.github import GitHubCollector
from src.errors import CollectionError


class TestGitHubCollectorInit:
    """GitHubCollector初期化のテスト。"""

    def test_no_token_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """GITHUB_TOKEN未設定時に警告ログが出力される。"""
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setattr("src.collectors.github.load_dotenv", lambda: None)
        with caplog.at_level(logging.WARNING):
            GitHubCollector(token="")
        assert "GITHUB_TOKEN" in caplog.text

    def test_with_token_no_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """GITHUB_TOKEN設定時に警告ログが出力されない。"""
        with caplog.at_level(logging.WARNING):
            GitHubCollector(token="valid-token")
        assert "GITHUB_TOKEN" not in caplog.text


class TestGitHubCollector:
    """GitHubCollectorのテスト。"""

    async def test_collect_repository_info(self, respx_mock: object) -> None:
        """リポジトリ情報を取得できる。"""
        import respx as respx_lib

        respx_lib.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "full_name": "owner/repo",
                    "description": "A test repo",
                    "html_url": "https://github.com/owner/repo",
                    "stargazers_count": 100,
                    "forks_count": 10,
                    "language": "Python",
                    "default_branch": "main",
                },
            )
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/readme").mock(
            return_value=httpx.Response(200, text="# Test Repo\nREADME content")
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/commits").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"commit": {"message": "Initial commit"}},
                    {"commit": {"message": "Add feature"}},
                ],
            )
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/git/trees/main").mock(
            return_value=httpx.Response(
                200,
                json={"sha": "abc", "tree": [{"path": "src", "type": "tree"}]},
            )
        )

        collector = GitHubCollector(token="test-token")
        results = await collector.collect("owner/repo")

        assert len(results) == 1
        assert results[0].source == "github"
        assert results[0].title == "owner/repo"
        assert "Stars: 100" in results[0].content
        assert "README content" in results[0].content
        assert "Initial commit" in results[0].content

    async def test_collect_without_readme(self, respx_mock: object) -> None:
        """READMEがないリポジトリも取得できる。"""
        import respx as respx_lib

        respx_lib.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "full_name": "owner/repo",
                    "description": "No readme",
                    "html_url": "https://github.com/owner/repo",
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "language": None,
                    "default_branch": "main",
                },
            )
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/readme").mock(
            return_value=httpx.Response(404)
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/commits").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/git/trees/main").mock(
            return_value=httpx.Response(200, json={"sha": "abc", "tree": []})
        )

        collector = GitHubCollector(token="test-token")
        results = await collector.collect("owner/repo")

        assert len(results) == 1
        assert "README" not in results[0].content

    async def test_collect_includes_directory_tree(self, respx_mock: object) -> None:
        """ディレクトリ構造が取得でき、コンテンツに含まれる。"""
        import respx as respx_lib

        respx_lib.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "full_name": "owner/repo",
                    "description": "A test repo",
                    "html_url": "https://github.com/owner/repo",
                    "stargazers_count": 50,
                    "forks_count": 5,
                    "language": "Python",
                    "default_branch": "main",
                },
            )
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/readme").mock(
            return_value=httpx.Response(200, text="# Repo")
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/commits").mock(
            return_value=httpx.Response(200, json=[])
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/git/trees/main").mock(
            return_value=httpx.Response(
                200,
                json={
                    "sha": "abc123",
                    "tree": [
                        {"path": "src", "type": "tree"},
                        {"path": "src/main.py", "type": "blob"},
                        {"path": "README.md", "type": "blob"},
                    ],
                },
            )
        )

        collector = GitHubCollector(token="test-token")
        results = await collector.collect("owner/repo")

        assert len(results) == 1
        assert "Directory Structure" in results[0].content
        assert "src/" in results[0].content
        assert "src/main.py" in results[0].content
        assert "README.md" in results[0].content

    async def test_collect_directory_tree_api_failure(self, respx_mock: object) -> None:
        """Trees API失敗時にも他の情報は取得できる。"""
        import respx as respx_lib

        respx_lib.get("https://api.github.com/repos/owner/repo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "full_name": "owner/repo",
                    "description": "A test repo",
                    "html_url": "https://github.com/owner/repo",
                    "stargazers_count": 10,
                    "forks_count": 1,
                    "language": "Python",
                    "default_branch": "main",
                },
            )
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/readme").mock(
            return_value=httpx.Response(200, text="# Repo")
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/commits").mock(
            return_value=httpx.Response(200, json=[{"commit": {"message": "Fix bug"}}])
        )
        respx_lib.get("https://api.github.com/repos/owner/repo/git/trees/main").mock(
            return_value=httpx.Response(404)
        )

        collector = GitHubCollector(token="test-token")
        results = await collector.collect("owner/repo")

        assert len(results) == 1
        assert "Directory Structure" not in results[0].content
        assert "owner/repo" in results[0].title
        assert "Fix bug" in results[0].content

    async def test_collect_api_error_raises_collection_error(self, respx_mock: object) -> None:
        """APIエラー時にCollectionErrorが発生する。"""
        import respx as respx_lib

        respx_lib.get("https://api.github.com/repos/invalid/repo").mock(
            return_value=httpx.Response(404)
        )

        collector = GitHubCollector(token="test-token")
        with pytest.raises(CollectionError):
            await collector.collect("invalid/repo")
