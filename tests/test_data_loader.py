from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.core.config import PROJECT_ROOT, Settings
from app.core.errors import DataLoadError
from app.services.data_loader import DataLoader, REQUIRED_COLUMNS


def _records() -> list[dict]:
    return json.loads((PROJECT_ROOT / "data" / "datos.json").read_text(encoding="utf-8"))


def _write_csv(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(
            destination, fieldnames=list(records[0]), delimiter=";", quoting=csv.QUOTE_MINIMAL
        )
        writer.writeheader()
        writer.writerows(records)


def _settings(source: Path, processed: Path, workers: int = 1) -> Settings:
    return Settings(
        data_file=source,
        processed_dir=processed,
        chunk_rows=2,
        workers=workers,
        query_threads=1,
    )


def test_carga_json_y_reutiliza_manifest(tmp_path):
    settings = _settings(PROJECT_ROOT / "data" / "datos.json", tmp_path / "processed")
    first = DataLoader(settings).prepare()
    second = DataLoader(settings).prepare()
    assert first == second
    assert first["rows_loaded"] == 6
    assert first["rows_rejected"] == 0


def test_carga_csv_punto_y_coma_en_chunks_paralelos(tmp_path):
    source = tmp_path / "ventas.csv"
    _write_csv(source, _records())
    manifest = DataLoader(_settings(source, tmp_path / "processed", workers=2)).prepare()
    assert manifest["delimiter"] == ";"
    assert manifest["rows_loaded"] == 6
    assert len(manifest["partitions"]) == 3


def test_registra_fila_invalida_sin_ocultarla(tmp_path):
    source = tmp_path / "ventas.csv"
    records = _records()
    records[1]["MONTO APLICADO"] = "no-numérico"
    _write_csv(source, records)
    manifest = DataLoader(_settings(source, tmp_path / "processed")).prepare()
    assert manifest["rows_loaded"] == 5
    assert manifest["rows_rejected"] == 1
    assert manifest["sample_errors"]


def test_falla_si_no_existe_fuente(tmp_path):
    with pytest.raises(DataLoadError, match="No existe"):
        DataLoader(_settings(tmp_path / "ausente.csv", tmp_path / "processed")).prepare()


def test_falla_si_faltan_columnas(tmp_path):
    source = tmp_path / "incompleto.csv"
    source.write_text("FECHA;CANAL\n2026-01-01;POS\n", encoding="utf-8")
    with pytest.raises(DataLoadError, match="columnas obligatorias"):
        DataLoader(_settings(source, tmp_path / "processed")).prepare()


def test_lista_de_columnas_incluye_los_campos_requeridos():
    assert len(REQUIRED_COLUMNS) == 15
    assert {"SKU", "MONTO APLICADO", "CODIGO CLIENTE", "GENERO"} <= REQUIRED_COLUMNS
