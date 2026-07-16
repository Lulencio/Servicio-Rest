from __future__ import annotations

import re

import pytest


ERROR_KEYS = {
    "detail",
    "instance",
    "status",
    "title",
    "type",
    "timestamp",
    "errorCode",
    "errorLabel",
    "method",
}
TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T.*\d{9}Z$")


def assert_error_contract(payload: dict, status: int, method: str) -> None:
    assert set(payload) == ERROR_KEYS
    assert payload["instance"] == "/v1/estadisticas/ventas"
    assert payload["status"] == status
    assert payload["method"] == method
    assert TIMESTAMP_PATTERN.match(payload["timestamp"])
    assert payload["type"].endswith(f"/{status}")
    if status == 400:
        assert payload["title"] == "Bad Request"
        assert payload["errorCode"] == "VF"
        assert payload["errorLabel"] == "Validación Fallida"
    else:
        assert payload["title"] == "Internal Server Error"
        assert payload["errorCode"] == "IE"
        assert payload["errorLabel"] == "Error Interno"


@pytest.mark.parametrize(
    "params",
    [
        {"DESCONOCIDO": "x"},
        {"EDAD": "treinta"},
        {"EDAD": "131"},
        {"CANAL": "TIENDA"},
        {"GENERO": "No binario"},
        {"LOCAL": "1.5"},
        {"CODIGO_PRODUCTO": "abc"},
        {"ID_PERSONA": "no-es-uuid"},
        {"FECHA_DESDE": "ayer"},
        {"FECHA_DESDE": "2026-12-01", "FECHA_HASTA": "2026-01-01"},
        {"LOCAL": "999"},
    ],
)
def test_get_invalido_devuelve_400_exacto(client, params):
    response = client.get("/v1/estadisticas/ventas", params=params)
    assert response.status_code == 400
    assert_error_contract(response.json(), 400, "GET")


@pytest.mark.parametrize(
    "body",
    [
        {"consultas": []},
        {"consultas": None},
        {"consultas": [{"consulta": "CANAL", "valor": None}]},
        {"consultas": [{"consulta": "CANAL", "valor": ""}]},
        {
            "consultas": [
                {"consulta": "LOCAL", "valor": "1"},
                {"consulta": "LOCAL", "valor": "2"},
            ]
        },
        {"campo": "inesperado"},
    ],
)
def test_post_invalido_devuelve_400_exacto(client, body):
    response = client.post("/v1/estadisticas/ventas", json=body)
    assert response.status_code == 400
    assert_error_contract(response.json(), 400, "POST")


def test_error_500_simulado_respeta_contrato(client):
    class BrokenStore:
        def statistics(self, filters):
            raise RuntimeError("fallo simulado")

    client.app.state.store = BrokenStore()
    response = client.get("/v1/estadisticas/ventas")
    assert response.status_code == 500
    assert_error_contract(response.json(), 500, "GET")
    assert "fallo simulado" not in response.json()["detail"]
