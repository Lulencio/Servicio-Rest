from __future__ import annotations


def test_post_sin_body_devuelve_totales(client):
    response = client.post("/v1/estadisticas/ventas")
    assert response.status_code == 200
    assert response.json()["conteo"] == 6


def test_post_con_un_filtro(client):
    response = client.post(
        "/v1/estadisticas/ventas",
        json={"consultas": [{"consulta": "CANAL", "valor": "WEB"}]},
    )
    assert response.status_code == 200
    assert response.json()["suma"] == 200.0


def test_post_con_varios_filtros(client):
    response = client.post(
        "/v1/estadisticas/ventas",
        json={
            "consultas": [
                {"consulta": "GENERO", "valor": "Femenino"},
                {"consulta": "EDAD", "valor": "30"},
                {"consulta": "CODIGO_PRODUCTO", "valor": "101"},
            ]
        },
    )
    assert response.status_code == 200
    assert response.json()["conteo"] == 2


def test_post_acepta_valor_entero(client):
    response = client.post(
        "/v1/estadisticas/ventas",
        json={"consultas": [{"consulta": "LOCAL", "valor": 2}]},
    )
    assert response.status_code == 200
    assert response.json()["conteo"] == 2
