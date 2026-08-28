from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_host_ports_are_loopback_only():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    firecrawl = (ROOT / "infra" / "firecrawl-docker-compose.yaml").read_text(
        encoding="utf-8"
    )
    api = (ROOT / "backend" / "app" / "api.py").read_text(encoding="utf-8")

    assert '"127.0.0.1:8000:8000"' in compose
    assert '"127.0.0.1:80:80"' in compose
    assert '"127.0.0.1:${PORT:-3002}:${INTERNAL_PORT:-3002}"' in firecrawl
    assert 'host="127.0.0.1"' in api
