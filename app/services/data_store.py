from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from app.core.errors import ValidationFailure


class DataStore:
    """Ejecuta filtros y agregaciones sin materializar el dataset completo."""

    def __init__(self, processed_dir: Path, query_threads: int = 4):
        self.processed_dir = processed_dir
        self.query_threads = max(1, query_threads)
        if not list(processed_dir.glob("part-*.parquet")):
            raise RuntimeError("No existen particiones procesadas para consultar")

    def statistics(self, filters: dict[str, Any]) -> dict[str, Any]:
        clauses: list[str] = []
        parameters: list[Any] = []
        mapping = {
            "GENERO": "genero = ?",
            "EDAD": "edad = ?",
            "CANAL": "canal = ?",
            "CODIGO_PRODUCTO": "sku = ?",
            "ID_PERSONA": "codigo_cliente = ?",
            "LOCAL": "local = ?",
            "FECHA_DESDE": "fecha >= ?",
            "FECHA_HASTA": "fecha <= ?",
        }
        for name, value in filters.items():
            clauses.append(mapping[name])
            parameters.append(value)

        parquet_glob = (self.processed_dir / "part-*.parquet").resolve().as_posix()
        safe_glob = parquet_glob.replace("'", "''")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        query = f"""
            SELECT
                sum(monto_aplicado),
                count(*),
                avg(monto_aplicado),
                min(monto_aplicado),
                max(monto_aplicado),
                median(monto_aplicado),
                stddev_pop(monto_aplicado)
            FROM read_parquet('{safe_glob}', union_by_name = true)
            {where}
        """

        with duckdb.connect(database=":memory:") as connection:
            connection.execute(f"SET threads = {self.query_threads}")
            row = connection.execute(query, parameters).fetchone()

        if row is None or int(row[1]) == 0:
            raise ValidationFailure(
                "La consulta es válida, pero no existen ventas para los filtros indicados"
            )

        return {
            "suma": round(float(row[0]), 2),
            "conteo": int(row[1]),
            "promedio": round(float(row[2]), 2),
            "minimo": round(float(row[3]), 2),
            "maximo": round(float(row[4]), 2),
            "mediana": round(float(row[5]), 2),
            "desviacion_estandar": round(float(row[6]), 2),
        }
