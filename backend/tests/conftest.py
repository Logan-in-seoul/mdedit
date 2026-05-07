from pathlib import Path

import pytest
import yaml


@pytest.fixture
def synthetic_vault(tmp_path: Path) -> Path:
    """합성 4개 루트 디렉터리를 tmp_path에 생성하고 루트 경로를 담은 dict를 반환한다."""
    roots = {}
    for name in ["common", "skills", "memory", "tour"]:
        root = tmp_path / name
        root.mkdir()
        (root / "hello.md").write_text("# hello\n\n본문", encoding="utf-8")
        roots[name] = root
    return tmp_path


@pytest.fixture
def config_file(tmp_path: Path, synthetic_vault: Path) -> Path:
    """synthetic_vault를 가리키는 임시 config.yaml을 만들어 경로를 돌려준다."""
    cfg = {
        "roots": [
            {"name": name, "path": str(synthetic_vault / name)}
            for name in ["common", "skills", "memory", "tour"]
        ],
        "exclude": ["node_modules", ".git"],
        "respect_gitignore": True,
        "server": {"host": "127.0.0.1", "port": 8787},
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return path
