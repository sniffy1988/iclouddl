from pathlib import Path

from iclouddownloader.api.web_static import safe_dist_file


def test_safe_dist_file_resolves_public_asset(tmp_path: Path):
    (tmp_path / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    found = safe_dist_file(tmp_path, "favicon.svg")
    assert found is not None
    assert found.name == "favicon.svg"


def test_safe_dist_file_rejects_traversal(tmp_path: Path):
    (tmp_path / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
    assert safe_dist_file(tmp_path, "../favicon.svg") is None
    assert safe_dist_file(tmp_path, "foo/../../etc/passwd") is None


def test_favicon_served_when_dist_built(client):
    dist = Path(__file__).resolve().parents[1] / "web" / "dist" / "favicon.svg"
    if not dist.is_file():
        return
    r = client.get("/favicon.svg")
    assert r.status_code == 200
    assert "svg" in r.headers.get("content-type", "").lower()
    assert r.text.strip().startswith("<svg")
