from __future__ import annotations

import pytest


@pytest.mark.parametrize(
    ("params", "expected_count"),
    [
        ({"GENERO": "Femenino"}, 2),
        ({"EDAD": "30"}, 2),
        ({"CANAL": "POS"}, 1),
        ({"CODIGO_PRODUCTO": "101"}, 2),
        ({"ID_PERSONA": "7c44465b-9e50-3914-923f-9b4f6fbee508"}, 1),
        ({"LOCAL": "3"}, 2),
        ({"FECHA_DESDE": "2026-04-01"}, 3),
        ({"FECHA_HASTA": "2026-03-10"}, 3),
    ],
)
def test_get_filtros_soportados(client, params, expected_count):
    response = client.get("/v1/estadisticas/ventas", params=params)
    assert response.status_code == 200
    assert response.json()["conteo"] == expected_count


def test_get_combina_filtros_con_and(client):
    response = client.get(
        "/v1/estadisticas/ventas",
        params={"GENERO": "Femenino", "CODIGO_PRODUCTO": "101"},
    )
    assert response.status_code == 200
    assert response.json()["conteo"] == 2
    assert response.json()["suma"] == 400.0


def test_fecha_hasta_incluye_el_dia_completo(client):
    response = client.get(
        "/v1/estadisticas/ventas", params={"FECHA_HASTA": "2026-01-15"}
    )
    assert response.status_code == 200
    assert response.json()["conteo"] == 1


def test_swagger_documenta_los_ocho_query_params(client):
    schema = client.get("/openapi.json").json()
    parameters = schema["paths"]["/v1/estadisticas/ventas"]["get"]["parameters"]
    assert {item["name"] for item in parameters} == {
        "GENERO",
        "EDAD",
        "CANAL",
        "CODIGO_PRODUCTO",
        "ID_PERSONA",
        "LOCAL",
        "FECHA_DESDE",
        "FECHA_HASTA",
    }


def test_swagger_ui_abre_correctamente(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()
