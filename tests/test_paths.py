import json

import pytest

from backend.app.api import _write_json_atomically
from backend.app.studio_paths import (
    APPLICATION_ROOT,
    ensure_data_directories,
    resolve_data_paths,
)


def test_default_data_root_does_not_depend_on_working_directory(monkeypatch, tmp_path):
    monkeypatch.delenv("STUDIO_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    paths = resolve_data_paths()

    assert paths.root == (APPLICATION_ROOT / "data").resolve()
    assert paths.qdrant == paths.root / "qdrant"
    assert paths.history_file == paths.root / "chat" / "history.json"


def test_configured_data_root_creates_separate_directories(monkeypatch, tmp_path):
    configured_root = tmp_path / "studio-data"
    monkeypatch.setenv("STUDIO_DATA_DIR", str(configured_root))

    paths = ensure_data_directories()

    assert paths.root == configured_root.resolve()
    assert paths.history_file.parent != paths.qdrant
    for directory in (
        paths.qdrant,
        paths.chat,
        paths.documents,
        paths.model_cache,
        paths.model_local,
    ):
        assert directory.is_dir()


def test_failed_history_write_preserves_existing_file(monkeypatch, tmp_path):
    history_file = tmp_path / "chat" / "history.json"
    existing_history = [{"message": "existing"}]
    _write_json_atomically(history_file, existing_history)
    assert json.loads(history_file.read_text(encoding="utf-8")) == existing_history

    def fail_after_partial_write(value, file, **kwargs):
        file.write('{"partial":')
        raise OSError("simulated write failure")

    monkeypatch.setattr(json, "dump", fail_after_partial_write)

    with pytest.raises(OSError, match="simulated write failure"):
        _write_json_atomically(history_file, [{"message": "replacement"}])

    assert json.loads(history_file.read_text(encoding="utf-8")) == existing_history
    assert list(history_file.parent.glob("*.tmp")) == []
