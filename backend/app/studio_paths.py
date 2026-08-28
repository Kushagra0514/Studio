import os
from dataclasses import dataclass
from pathlib import Path

APPLICATION_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class DataPaths:
    root: Path
    qdrant: Path
    chat: Path
    documents: Path
    models: Path
    model_cache: Path
    model_local: Path

    @property
    def history_file(self) -> Path:
        return self.chat / "history.json"


def resolve_data_paths() -> DataPaths:
    configured_root = os.getenv("STUDIO_DATA_DIR")
    root = (
        Path(configured_root).expanduser()
        if configured_root
        else APPLICATION_ROOT / "data"
    )
    if not root.is_absolute():
        root = APPLICATION_ROOT / root
    root = root.resolve()

    models = root / "models"
    return DataPaths(
        root=root,
        qdrant=root / "qdrant",
        chat=root / "chat",
        documents=root / "documents",
        models=models,
        model_cache=models / "cache",
        model_local=models / "local",
    )


def ensure_data_directories() -> DataPaths:
    paths = resolve_data_paths()
    for directory in (
        paths.qdrant,
        paths.chat,
        paths.documents,
        paths.model_cache,
        paths.model_local,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return paths
