from __future__ import annotations

import math

import pytest

from app.services.data_store import DataStore


def test_calculos_totales(client):
    response = client.get("/v1/estadisticas/ventas")
    assert response.status_code == 200
    assert response.json() == {
        "suma": 2100.0,
        "conteo": 6,
        "promedio": 350.0,
        "minimo": 100.0,
        "maximo": 600.0,
        "mediana": 350.0,
        "desviacion_estandar": 170.78,
    }


def test_desviacion_estandar_es_poblacional():
    expected = math.sqrt(sum((value - 350) ** 2 for value in range(100, 601, 100)) / 6)
    assert round(expected, 2) == 170.78


def test_mediana_con_conteo_par(client):
    response = client.get("/v1/estadisticas/ventas", params={"LOCAL": "1"})
    assert response.json()["mediana"] == 150.0


def test_un_solo_resultado_tiene_desviacion_cero(client):
    response = client.get(
        "/v1/estadisticas/ventas", params={"CODIGO_PRODUCTO": "105"}
    )
    assert response.status_code == 200
    assert response.json()["conteo"] == 1
    assert response.json()["desviacion_estandar"] == 0.0


def test_data_store_rechaza_directorio_sin_particiones(tmp_path):
    with pytest.raises(RuntimeError, match="No existen particiones"):
        DataStore(tmp_path)
