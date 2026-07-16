from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser().resolve() if value else default.resolve()


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    value = int(raw) if raw is not None else default
    return max(minimum, value)


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuración explícita para producción y pruebas."""

    data_file: Path = field(
        default_factory=lambda: _env_path(
            "REST_DATA_FILE", PROJECT_ROOT / "data" / "input" / "ventas_completas.csv.gz"
        )
    )
    processed_dir: Path = field(
        default_factory=lambda: _env_path(
            "REST_PROCESSED_DIR", PROJECT_ROOT / "data" / "processed"
        )
    )
    chunk_rows: int = field(
        default_factory=lambda: _env_int("REST_CHUNK_ROWS", 250_000)
    )
    workers: int = field(
        default_factory=lambda: _env_int(
            "REST_WORKERS", min(4, max(1, (os.cpu_count() or 2) - 1))
        )
    )
    query_threads: int = field(
        default_factory=lambda: _env_int(
            "REST_QUERY_THREADS", min(4, max(1, os.cpu_count() or 1))
        )
    )
