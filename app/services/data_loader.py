from __future__ import annotations

import csv
import gzip
import json
import math
import shutil
from concurrent.futures import (
    ALL_COMPLETED,
    FIRST_COMPLETED,
    Future,
    ProcessPoolExecutor,
    wait,
)
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, TextIO
from uuid import UUID, uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from app.core.config import Settings
from app.core.errors import DataLoadError


LOADER_VERSION = 1
REQUIRED_COLUMNS = {
    "FECHA",
    "CANAL",
    "SKU",
    "PRODUCTO",
    "UNIDADES",
    "PORCENTAJE DESCUENTO",
    "MONTO APLICADO",
    "BOLETA",
    "LOCAL",
    "CODIGO CLIENTE",
    "RUN CLIENTE",
    "NOMBRES",
    "APELLIDOS",
    "FECHA NACIMIENTO",
    "GENERO",
}
NORMALIZED_SCHEMA = pa.schema(
    [
        ("fecha", pa.timestamp("us")),
        ("canal", pa.string()),
        ("sku", pa.int64()),
        ("monto_aplicado", pa.float64()),
        ("local", pa.int64()),
        ("codigo_cliente", pa.string()),
        ("genero", pa.string()),
        ("edad", pa.int16()),
    ]
)


def _open_source(path: Path) -> TextIO:
    if path.suffix.lower() == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def _detect_delimiter(path: Path) -> str:
    with _open_source(path) as source:
        sample = source.read(8192)
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error as exc:
        raise DataLoadError("No fue posible detectar el delimitador del CSV") from exc


def _age_at_sale(birth: date, sale: date) -> int:
    return sale.year - birth.year - ((sale.month, sale.day) < (birth.month, birth.day))


def _gender(value: Any) -> str:
    text = str(value or "").strip()
    mapping = {
        "": "No especificado",
        "0": "No especificado",
        "1": "Masculino",
        "2": "Femenino",
        "3": "Otro",
        "No especificado": "No especificado",
        "Masculino": "Masculino",
        "Femenino": "Femenino",
        "Otro": "Otro",
    }
    return mapping.get(text, "Otro")


def _normalize(record: dict[str, Any]) -> dict[str, Any]:
    sale = datetime.fromisoformat(str(record["FECHA"]).strip().replace("Z", "+00:00"))
    if sale.tzinfo is not None:
        sale = sale.replace(tzinfo=None)
    birth = date.fromisoformat(str(record["FECHA NACIMIENTO"]).strip())
    amount = float(str(record["MONTO APLICADO"]).strip())
    if not math.isfinite(amount):
        raise ValueError("MONTO APLICADO no es finito")

    return {
        "fecha": sale,
        "canal": str(record["CANAL"]).strip().upper(),
        "sku": int(str(record["SKU"]).strip()),
        "monto_aplicado": amount,
        "local": int(str(record["LOCAL"]).strip()),
        "codigo_cliente": str(UUID(str(record["CODIGO CLIENTE"]).strip())),
        "genero": _gender(record["GENERO"]),
        "edad": _age_at_sale(birth, sale.date()),
    }


def _write_batch(writer: pq.ParquetWriter, batch: list[dict[str, Any]]) -> None:
    if batch:
        writer.write_table(pa.Table.from_pylist(batch, schema=NORMALIZED_SCHEMA))
        batch.clear()


def _records_to_parquet(
    records: Iterator[tuple[int, dict[str, Any]]], output_path: Path
) -> dict[str, Any]:
    loaded = 0
    rejected = 0
    sample_errors: list[str] = []
    buffer: list[dict[str, Any]] = []

    with pq.ParquetWriter(output_path, NORMALIZED_SCHEMA, compression="zstd") as writer:
        for row_number, record in records:
            try:
                buffer.append(_normalize(record))
                loaded += 1
                if len(buffer) >= 10_000:
                    _write_batch(writer, buffer)
            except (KeyError, TypeError, ValueError) as exc:
                rejected += 1
                if len(sample_errors) < 5:
                    sample_errors.append(f"Fila {row_number}: {exc}")
        _write_batch(writer, buffer)

    return {
        "loaded": loaded,
        "rejected": rejected,
        "sample_errors": sample_errors,
        "partition": output_path.name,
    }


def _process_csv_chunk(input_path: str, output_path: str, delimiter: str) -> dict[str, Any]:
    source_path = Path(input_path)
    with source_path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter=delimiter)
        return _records_to_parquet(
            ((index, row) for index, row in enumerate(reader, start=2)),
            Path(output_path),
        )


class DataLoader:
    """Convierte la fuente grande en particiones consultables y reutilizables."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def manifest_path(self) -> Path:
        return self.settings.processed_dir / "manifest.json"

    def prepare(self) -> dict[str, Any]:
        source = self.settings.data_file
        if not source.is_file():
            raise DataLoadError(
                f"No existe el archivo de datos configurado: {source}"
            )
        if self._is_current():
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return self._build()

    def _signature(self) -> dict[str, Any]:
        stat = self.settings.data_file.stat()
        return {
            "source": str(self.settings.data_file.resolve()),
            "source_size": stat.st_size,
            "source_mtime_ns": stat.st_mtime_ns,
            "loader_version": LOADER_VERSION,
        }

    def _is_current(self) -> bool:
        if not self.manifest_path.is_file():
            return False
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if any(manifest.get(key) != value for key, value in self._signature().items()):
            return False
        parts = manifest.get("partitions", [])
        return bool(parts) and all(
            (self.settings.processed_dir / name).is_file() for name in parts
        )

    def _build(self) -> dict[str, Any]:
        target = self.settings.processed_dir
        staging = target.parent / f".{target.name}-build-{uuid4().hex}"
        staging.mkdir(parents=True, exist_ok=False)
        try:
            if self.settings.data_file.suffix.lower() == ".json":
                results = [self._build_json(staging)]
                delimiter = None
            else:
                delimiter = _detect_delimiter(self.settings.data_file)
                results = self._build_csv(staging, delimiter)

            loaded = sum(item["loaded"] for item in results)
            rejected = sum(item["rejected"] for item in results)
            if loaded == 0:
                raise DataLoadError("La carga no produjo ninguna fila válida")

            manifest = {
                **self._signature(),
                "delimiter": delimiter,
                "chunk_rows": self.settings.chunk_rows,
                "workers": self.settings.workers,
                "rows_loaded": loaded,
                "rows_rejected": rejected,
                "partitions": [item["partition"] for item in results],
                "sample_errors": [
                    message for item in results for message in item["sample_errors"]
                ][:10],
            }
            (staging / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if target.exists():
                shutil.rmtree(target)
            staging.replace(target)
            return manifest
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def _build_json(self, staging: Path) -> dict[str, Any]:
        try:
            content = json.loads(self.settings.data_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise DataLoadError("El archivo datos.json no es válido") from exc
        records = content.get("datos") if isinstance(content, dict) else content
        if not isinstance(records, list):
            raise DataLoadError("datos.json debe contener una lista de registros")
        output = staging / "part-00000.parquet"
        return _records_to_parquet(iter(enumerate(records, start=1)), output)

    def _validate_headers(self, headers: list[str] | None) -> list[str]:
        if not headers:
            raise DataLoadError("El CSV no contiene una fila de encabezados")
        missing = sorted(REQUIRED_COLUMNS.difference(headers))
        if missing:
            raise DataLoadError(
                "El CSV no contiene las columnas obligatorias: " + ", ".join(missing)
            )
        return headers

    def _build_csv(self, staging: Path, delimiter: str) -> list[dict[str, Any]]:
        raw_dir = staging / "raw_chunks"
        raw_dir.mkdir()
        results: list[dict[str, Any]] = []

        with _open_source(self.settings.data_file) as source:
            reader = csv.DictReader(source, delimiter=delimiter)
            headers = self._validate_headers(reader.fieldnames)
            if self.settings.workers == 1:
                for index, chunk_path in self._write_chunks(reader, headers, raw_dir, delimiter):
                    output = staging / f"part-{index:05d}.parquet"
                    results.append(_process_csv_chunk(str(chunk_path), str(output), delimiter))
                    chunk_path.unlink(missing_ok=True)
            else:
                results.extend(
                    self._parallel_chunks(reader, headers, raw_dir, staging, delimiter)
                )

        shutil.rmtree(raw_dir, ignore_errors=True)
        return sorted(results, key=lambda item: item["partition"])

    def _write_chunks(
        self,
        reader: csv.DictReader,
        headers: list[str],
        raw_dir: Path,
        delimiter: str,
    ) -> Iterator[tuple[int, Path]]:
        index = 0
        exhausted = False
        while not exhausted:
            path = raw_dir / f"chunk-{index:05d}.csv"
            count = 0
            with path.open("w", encoding="utf-8", newline="") as destination:
                writer = csv.DictWriter(destination, fieldnames=headers, delimiter=delimiter)
                writer.writeheader()
                while count < self.settings.chunk_rows:
                    try:
                        writer.writerow(next(reader))
                        count += 1
                    except StopIteration:
                        exhausted = True
                        break
            if count == 0:
                path.unlink(missing_ok=True)
                break
            yield index, path
            index += 1

    def _parallel_chunks(
        self,
        reader: csv.DictReader,
        headers: list[str],
        raw_dir: Path,
        staging: Path,
        delimiter: str,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        pending: dict[Future[dict[str, Any]], Path] = {}
        limit = self.settings.workers * 2

        with ProcessPoolExecutor(max_workers=self.settings.workers) as executor:
            for index, chunk_path in self._write_chunks(reader, headers, raw_dir, delimiter):
                output = staging / f"part-{index:05d}.parquet"
                future = executor.submit(
                    _process_csv_chunk, str(chunk_path), str(output), delimiter
                )
                pending[future] = chunk_path
                if len(pending) >= limit:
                    self._collect_completed(pending, results, wait_all=False)
            self._collect_completed(pending, results, wait_all=True)
        return results

    @staticmethod
    def _collect_completed(
        pending: dict[Future[dict[str, Any]], Path],
        results: list[dict[str, Any]],
        *,
        wait_all: bool,
    ) -> None:
        if not pending:
            return
        done, _ = wait(
            pending,
            return_when=ALL_COMPLETED if wait_all else FIRST_COMPLETED,
        )
        for future in done:
            chunk_path = pending.pop(future)
            try:
                results.append(future.result())
            finally:
                chunk_path.unlink(missing_ok=True)
