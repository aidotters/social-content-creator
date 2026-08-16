"""StaticSitePublisherのテスト。"""

import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.errors import StaticSitePublishError
from src.models.blog_post import BlogPost
from src.publishers.static_site import StaticSitePublisher


@pytest.fixture
def site_repo(tmp_path: Path) -> Path:
    """記事の書き出し先となる空のgitリポジトリ。"""
    repo = tmp_path / "aidotters-web-page"
    repo.mkdir()
    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "test"],
    ):
        subprocess.run(args, cwd=repo, check=True, capture_output=True)
    (repo / "README.md").write_text("test\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-qm", "init"], cwd=repo, check=True, capture_output=True)
    return repo


@pytest.fixture
def publisher(site_repo: Path) -> StaticSitePublisher:
    return StaticSitePublisher(site_repo=site_repo)


@pytest.fixture
def weekly_post() -> BlogPost:
    return BlogPost(
        title="【2026年8月第1週】週刊AIニュースハイライト",
        subtitle="今週の動向",
        content="## 主要ニュース\n\n本文。",
        content_type="weekly-ai-news",
        slug="202681ai",
        created_at=datetime(2026, 8, 2, 7, 47, tzinfo=UTC),
    )


@pytest.fixture
def paper_post() -> BlogPost:
    return BlogPost(
        title="【論文解説】SkillClaw",
        content="## 概要\n\n本文。",
        content_type="paper-review",
        slug="skillclaw",
        created_at=datetime(2026, 4, 11, tzinfo=UTC),
    )


def test_missing_repo_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AIDOTTERS_SITE_REPO", raising=False)
    monkeypatch.setattr("src.publishers.static_site.load_dotenv", lambda: None)
    with pytest.raises(ValueError, match="AIDOTTERS_SITE_REPO"):
        StaticSitePublisher()


def test_non_git_dir_raises_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="gitリポジトリではありません"):
        StaticSitePublisher(site_repo=tmp_path)


def test_weekly_slug_uses_publish_date(
    publisher: StaticSitePublisher, weekly_post: BlogPost
) -> None:
    # タイトルの「第N週」表記は過去に重複した実績があるため使わない
    assert publisher.resolve_slug(weekly_post) == "2026-08-02"


def test_non_weekly_slug_uses_post_slug(
    publisher: StaticSitePublisher, paper_post: BlogPost
) -> None:
    assert publisher.resolve_slug(paper_post) == "skillclaw"


@pytest.mark.parametrize("bad_slug", ["日本語スラグ", "Upper-Case", "with space", "-leading"])
def test_invalid_slug_rejected(
    publisher: StaticSitePublisher, paper_post: BlogPost, bad_slug: str
) -> None:
    paper_post.slug = bad_slug
    with pytest.raises(StaticSitePublishError, match="slug"):
        publisher.resolve_slug(paper_post)


def test_frontmatter_contains_only_schema_keys(
    publisher: StaticSitePublisher, weekly_post: BlogPost
) -> None:
    front = publisher.build_frontmatter(weekly_post, published=True)
    assert "type: 'weekly-ai-news'" in front
    assert "status: 'published'" in front
    # サイト側 zod スキーマが受け付けないキーを出さない（出すとサイトのビルドが落ちる）
    for forbidden in ("slug:", "content_type:", "wordpress_url:", "categories:", "tags:"):
        assert forbidden not in front


def test_frontmatter_escapes_single_quotes(
    publisher: StaticSitePublisher, paper_post: BlogPost
) -> None:
    paper_post.title = "It's a test"
    assert "title: 'It''s a test'" in publisher.build_frontmatter(paper_post, published=False)


async def test_publish_writes_to_type_directory(
    publisher: StaticSitePublisher, weekly_post: BlogPost, site_repo: Path
) -> None:
    result = await publisher.publish(weekly_post, status="publish")

    assert result.success
    assert result.url == "/blog/weekly-ai-news/2026-08-02/"
    written = site_repo / "src/content/blog/weekly-ai-news/2026-08-02.md"
    assert written.exists()
    text = written.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "## 主要ニュース" in text


async def test_publish_draft_sets_draft_status(
    publisher: StaticSitePublisher, paper_post: BlogPost, site_repo: Path
) -> None:
    await publisher.publish(paper_post, status="draft")
    text = (site_repo / "src/content/blog/paper-review/skillclaw.md").read_text(encoding="utf-8")
    assert "status: 'draft'" in text


async def test_publish_commits_file(
    publisher: StaticSitePublisher, weekly_post: BlogPost, site_repo: Path
) -> None:
    await publisher.publish(weekly_post, status="publish")

    log = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=site_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert weekly_post.title in log.stdout
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=site_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""


async def test_publish_without_commit_leaves_file_untracked(
    publisher: StaticSitePublisher, weekly_post: BlogPost, site_repo: Path
) -> None:
    await publisher.publish(weekly_post, status="publish", commit=False)

    # -uall を付けないと未追跡ディレクトリが "?? src/" にまとめられ、ファイル名が見えない
    status = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=site_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "src/content/blog/weekly-ai-news/2026-08-02.md" in status.stdout


async def test_publish_duplicate_slug_raises(
    publisher: StaticSitePublisher, weekly_post: BlogPost
) -> None:
    await publisher.publish(weekly_post, status="publish")
    with pytest.raises(StaticSitePublishError, match="既に存在"):
        await publisher.publish(weekly_post, status="publish")


async def test_publish_overwrite_replaces_content(
    publisher: StaticSitePublisher, weekly_post: BlogPost, site_repo: Path
) -> None:
    await publisher.publish(weekly_post, status="publish")
    weekly_post.content = "## 差し替え後\n\n新しい本文。"
    result = await publisher.publish(weekly_post, status="publish", overwrite=True)

    assert result.success
    text = (site_repo / "src/content/blog/weekly-ai-news/2026-08-02.md").read_text(encoding="utf-8")
    assert "差し替え後" in text
