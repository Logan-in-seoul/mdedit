from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app, set_config
from app.schema import AppConfig, RootConfig


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.fixture
def configured_client(tmp_path: Path) -> TestClient:
    root = tmp_path / "common"
    root.mkdir()
    (root / "a.md").write_text("# a", encoding="utf-8")
    config = AppConfig(roots=[RootConfig(name="common", path=root)])
    set_config(config)
    return TestClient(app)


def test_tree_endpoint_returns_configured_roots(configured_client: TestClient):
    response = configured_client.get("/api/tree")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "common"
    assert data[0]["kind"] == "dir"
    assert data[0]["children"][0]["path"] == "common://a.md"


def test_file_endpoint_returns_content(configured_client: TestClient, tmp_path: Path):
    (tmp_path / "common" / "hello.md").write_text(
        "---\ntype: user\n---\n\n# 안녕\n", encoding="utf-8"
    )
    response = configured_client.get("/api/file", params={"path": "common://hello.md"})
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "안녕"
    assert data["frontmatter"] == {"type": "user"}


def test_file_endpoint_returns_404_for_missing(configured_client: TestClient):
    response = configured_client.get("/api/file", params={"path": "common://nope.md"})
    assert response.status_code == 404


def test_config_endpoint_returns_root_names(configured_client: TestClient):
    response = configured_client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert data["roots"] == [{"name": "common"}]
    assert data["server"]["port"] == 8787


def test_flat_endpoint_returns_sorted_files(configured_client: TestClient, tmp_path: Path):
    import time
    (tmp_path / "common" / "old.md").write_text("old")
    time.sleep(0.01)
    (tmp_path / "common" / "new.md").write_text("new")

    response = configured_client.get("/api/files/flat")
    assert response.status_code == 200
    data = response.json()
    paths = [e["path"] for e in data]
    assert "common://new.md" in paths
    assert "common://old.md" in paths
    # new.md is more recent, should appear before old.md
    assert paths.index("common://new.md") < paths.index("common://old.md")


def test_flat_endpoint_respects_limit(configured_client: TestClient, tmp_path: Path):
    for i in range(5):
        (tmp_path / "common" / f"file{i}.md").write_text("x")
    response = configured_client.get("/api/files/flat?limit=2")
    data = response.json()
    assert len(data) == 2


def test_backlinks_finds_wiki_style_reference(
    configured_client: TestClient, tmp_path: Path
):
    (tmp_path / "common" / "target.md").write_text("# target", encoding="utf-8")
    (tmp_path / "common" / "ref.md").write_text(
        "see [[target]] for context", encoding="utf-8"
    )
    response = configured_client.get(
        "/api/backlinks", params={"path": "common://target.md"}
    )
    assert response.status_code == 200
    paths = [e["path"] for e in response.json()]
    assert "common://ref.md" in paths
    assert "common://target.md" not in paths  # excludes self


def test_backlinks_finds_markdown_link(
    configured_client: TestClient, tmp_path: Path
):
    (tmp_path / "common" / "spec.md").write_text("# spec", encoding="utf-8")
    (tmp_path / "common" / "summary.md").write_text(
        "details in [the spec](spec.md)", encoding="utf-8"
    )
    response = configured_client.get(
        "/api/backlinks", params={"path": "common://spec.md"}
    )
    paths = [e["path"] for e in response.json()]
    assert "common://summary.md" in paths


def test_backlinks_returns_empty_when_no_references(
    configured_client: TestClient, tmp_path: Path
):
    (tmp_path / "common" / "lonely.md").write_text("# lonely", encoding="utf-8")
    (tmp_path / "common" / "other.md").write_text(
        "unrelated content", encoding="utf-8"
    )
    response = configured_client.get(
        "/api/backlinks", params={"path": "common://lonely.md"}
    )
    assert response.json() == []


def test_backlinks_handles_invalid_virtual_path(configured_client: TestClient):
    response = configured_client.get("/api/backlinks", params={"path": "garbage"})
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# D-5: /api/search 연산자 파라미터 엔드포인트 테스트
# ---------------------------------------------------------------------------


@pytest.fixture
def search_client(tmp_path: Path):
    """검색 연산자 테스트용 클라이언트: type·path·text 혼합 파일 vault."""
    import app.index as fts_index

    root = tmp_path / "vault"
    root.mkdir()
    mem = root / "memory"
    mem.mkdir()
    (mem / "user_note.md").write_text(
        "---\ntype: user\n---\n# 유저 노트\n사용자 관련 정보.\n",
        encoding="utf-8",
    )
    (root / "skill_note.md").write_text(
        "---\ntype: skill\n---\n# 스킬 노트\n자동화 스킬 설명.\n",
        encoding="utf-8",
    )
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="vault", path=root)])
    set_config(cfg)
    fts_index.refresh(cfg)
    return TestClient(app)


def test_search_path_param_filters_results(search_client: TestClient):
    response = search_client.get("/api/search", params={"q": "", "path": "memory"})
    assert response.status_code == 200
    data = response.json()
    paths = [h["path"] for h in data["hits"]]
    assert any("memory" in p for p in paths)
    assert not any("skill_note" in p for p in paths)


def test_search_type_param_filters_results(search_client: TestClient):
    response = search_client.get("/api/search", params={"q": "", "type": "user"})
    assert response.status_code == 200
    data = response.json()
    paths = [h["path"] for h in data["hits"]]
    assert any("user_note" in p for p in paths)
    assert not any("skill_note" in p for p in paths)


def test_search_type_param_unknown_returns_empty(search_client: TestClient):
    response = search_client.get("/api/search", params={"q": "", "type": "ghost"})
    assert response.status_code == 200
    data = response.json()
    assert data["hits"] == []
    assert data["total"] == 0


def test_search_path_and_type_combined(search_client: TestClient):
    response = search_client.get(
        "/api/search", params={"q": "", "path": "memory", "type": "user"}
    )
    assert response.status_code == 200
    data = response.json()
    paths = [h["path"] for h in data["hits"]]
    assert any("user_note" in p for p in paths)


def test_search_hit_has_line_number(search_client: TestClient):
    response = search_client.get("/api/search", params={"q": "자동화"})
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    hit = data["hits"][0]
    assert hit["line"] >= 1
    assert "match_start" in hit
    assert "match_end" in hit


def test_search_operator_in_query_string(search_client: TestClient):
    """쿼리 문자열에 path: 연산자 포함 시 API가 올바르게 파싱해야 한다."""
    response = search_client.get("/api/search", params={"q": "path:memory"})
    assert response.status_code == 200
    data = response.json()
    paths = [h["path"] for h in data["hits"]]
    assert any("memory" in p for p in paths)
