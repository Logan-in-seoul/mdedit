"""인덱스 안전 가드 회귀 테스트.

Regression: ISSUE-004 — 마지막 refresh 이후 생성된 파일에 별표를 달면
star()가 404로 조용히 실패하고 프런트 낙관 업데이트가 되돌려졌다.
Regression: ISSUE-005 — refresh cleanup이 비정상적으로 작은 walk 결과
(설정 오류·부분 walk·동시 writer)로 인덱스와 starred를 쓸어버릴 수 있었다.
Found by /qa on 2026-06-08.
Report: .gstack/qa-reports/qa-report-mdedit-2026-06-08.md
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import index as fts_index
from app.main import app, set_config
from app.schema import AppConfig, RootConfig


@pytest.fixture
def guard_vault(tmp_path: Path) -> AppConfig:
    root = tmp_path / "common"
    root.mkdir()
    for i in range(4):
        (root / f"note{i}.md").write_text(f"# Note {i}\n\n본문\n", encoding="utf-8")
    fts_index.init_db(tmp_path / "state")
    cfg = AppConfig(roots=[RootConfig(name="common", path=root)])
    fts_index.refresh(cfg)
    set_config(cfg)
    return cfg


@pytest.fixture
def client(guard_vault: AppConfig) -> TestClient:
    return TestClient(app)


class TestStarOnFreshFile:
    """ISSUE-004: refresh 이후 생성된 파일도 별표가 즉시 성공해야 한다."""

    def test_star_unindexed_but_existing_file(
        self, client: TestClient, guard_vault: AppConfig
    ) -> None:
        # refresh 이후 새 파일 생성 — 인덱스에 없음
        fresh = Path(guard_vault.roots[0].path) / "fresh.md"
        fresh.write_text("# 신규\n\n방금 만든 파일\n", encoding="utf-8")

        res = client.put("/api/starred", params={"path": "common://fresh.md"})
        assert res.status_code == 200, "디스크 실존 파일은 즉석 인덱싱 후 별표 성공"

        data = client.get("/api/starred").json()
        assert "common://fresh.md" in data["paths"]
        # 즉석 인덱싱으로 검색에도 잡힌다
        hit = client.get("/api/search", params={"q": "방금 만든"}).json()
        assert hit["total"] >= 1

    def test_star_nonexistent_file_still_404(self, client: TestClient) -> None:
        res = client.put("/api/starred", params={"path": "common://ghost.md"})
        assert res.status_code == 404

    def test_star_path_traversal_blocked(self, client: TestClient) -> None:
        res = client.put(
            "/api/starred", params={"path": "common://../../etc/passwd.md"}
        )
        assert res.status_code == 404


class TestCleanupMassDeleteGuard:
    """ISSUE-005: walk 결과가 인덱스의 절반 미만이면 cleanup을 건너뛴다."""

    def test_small_walk_does_not_wipe_index(self, tmp_path: Path) -> None:
        root = tmp_path / "vault"
        root.mkdir()
        # 가드 발동 조건(인덱스 100개 초과)을 만들기 위해 120개 인덱싱
        for i in range(120):
            (root / f"n{i}.md").write_text(f"# n{i}\n", encoding="utf-8")
        fts_index.init_db(tmp_path / "state")
        cfg = AppConfig(roots=[RootConfig(name="vault", path=root)])
        fts_index.refresh(cfg)
        assert fts_index.star("vault://n0.md")

        # 잘못된 설정(빈 디렉터리)으로 refresh — walk가 0건
        empty = tmp_path / "empty"
        empty.mkdir()
        bad_cfg = AppConfig(roots=[RootConfig(name="vault", path=empty)])
        stats = fts_index.refresh(bad_cfg)

        assert stats["deleted"] == 0, "대량 삭제 가드가 cleanup을 막아야 한다"
        assert fts_index.list_starred() == ["vault://n0.md"], "별표 생존"
        db = fts_index.get_db()
        assert db.execute("SELECT COUNT(*) FROM files").fetchone()[0] == 120

    def test_normal_deletion_still_works(self, tmp_path: Path) -> None:
        root = tmp_path / "vault"
        root.mkdir()
        for i in range(120):
            (root / f"n{i}.md").write_text(f"# n{i}\n", encoding="utf-8")
        fts_index.init_db(tmp_path / "state")
        cfg = AppConfig(roots=[RootConfig(name="vault", path=root)])
        fts_index.refresh(cfg)

        # 일부 삭제(절반 미만)는 정상 cleanup
        for i in range(10):
            (root / f"n{i}.md").unlink()
        stats = fts_index.refresh(cfg)
        assert stats["deleted"] == 10
