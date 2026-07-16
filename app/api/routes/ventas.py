from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Query, Request

from app.core.errors import ValidationFailure
from app.models.schemas import ErrorResponse, EstadisticasResponse, SolicitudPost
from app.services.data_store import DataStore
from app.utils.validators import validate_filters


router = APIRouter(prefix="/v1/estadisticas", tags=["Estadísticas de ventas"])
ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Validación fallida"},
    500: {"model": ErrorResponse, "description": "Error interno"},
}


def _store(request: Request) -> DataStore:
    store = getattr(request.app.state, "store", None)
    if store is None:
        raise RuntimeError("Los datos de ventas no están disponibles")
    return store


@router.get(
    "/ventas",
    response_model=EstadisticasResponse,
    responses=ERROR_RESPONSES,
    summary="Obtener estadísticas con filtros opcionales",
)
def get_ventas(
    request: Request,
    genero: Annotated[str | None, Query(alias="GENERO")] = None,
    edad: Annotated[str | None, Query(alias="EDAD")] = None,
    canal: Annotated[str | None, Query(alias="CANAL")] = None,
    codigo_producto: Annotated[str | None, Query(alias="CODIGO_PRODUCTO")] = None,
    id_persona: Annotated[str | None, Query(alias="ID_PERSONA")] = None,
    local: Annotated[str | None, Query(alias="LOCAL")] = None,
    fecha_desde: Annotated[str | None, Query(alias="FECHA_DESDE")] = None,
    fecha_hasta: Annotated[str | None, Query(alias="FECHA_HASTA")] = None,
) -> dict[str, object]:
    """Calcula las métricas de `MONTO APLICADO` sobre las ventas filtradas."""

    filters = validate_filters(request.query_params.multi_items())
    return _store(request).statistics(filters)


@router.post(
    "/ventas",
    response_model=EstadisticasResponse,
    responses=ERROR_RESPONSES,
    summary="Obtener estadísticas con consultas personalizadas",
)
def post_ventas(
    request: Request,
    solicitud: Annotated[
        SolicitudPost | None,
        Body(
            openapi_examples={
                "varios_filtros": {
                    "summary": "Género, edad y canal",
                    "value": {
                        "consultas": [
                            {"consulta": "GENERO", "valor": "Femenino"},
                            {"consulta": "EDAD", "valor": "31"},
                            {"consulta": "CANAL", "valor": "POS"},
                        ]
                    },
                }
            }
        ),
    ] = None,
) -> dict[str, object]:
    """Sin body devuelve el total; un body presente debe contener filtros."""

    if solicitud is None:
        filters = {}
    else:
        if not solicitud.consultas:
            raise ValidationFailure("consultas está vacío o nulo")
        filters = validate_filters(
            (item.consulta, item.valor) for item in solicitud.consultas
        )
    return _store(request).statistics(filters)
