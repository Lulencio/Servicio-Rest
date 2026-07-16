from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Consulta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consulta: str = Field(
        description="Nombre textual del filtro permitido.", examples=["GENERO"]
    )
    valor: Any = Field(description="Valor que se desea filtrar.", examples=["Femenino"])


class SolicitudPost(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consultas: list[Consulta] | None = Field(
        description="Uno o más filtros personalizados.",
        examples=[
            [
                {"consulta": "GENERO", "valor": "Femenino"},
                {"consulta": "CANAL", "valor": "POS"},
            ]
        ],
    )


class EstadisticasResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suma: float = Field(examples=[1500.5])
    conteo: int = Field(examples=[42])
    promedio: float = Field(examples=[35.73])
    minimo: float = Field(examples=[10.0])
    maximo: float = Field(examples=[100.0])
    mediana: float = Field(examples=[30.0])
    desviacion_estandar: float = Field(examples=[25.4])


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str
    instance: str
    status: int
    title: str
    type: str
    timestamp: str
    errorCode: str
    errorLabel: str
    method: str
