from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Iterable
from uuid import UUID

from app.core.errors import ValidationFailure


ALLOWED_FILTERS = {
    "GENERO",
    "EDAD",
    "CANAL",
    "CODIGO_PRODUCTO",
    "ID_PERSONA",
    "LOCAL",
    "FECHA_DESDE",
    "FECHA_HASTA",
}
ALLOWED_GENDERS = {"No especificado", "Masculino", "Femenino", "Otro"}
ALLOWED_CHANNELS = {"POS", "WEB", "APP", "CCT", "APR", "WPR"}
INTEGER_PATTERN = re.compile(r"^[+-]?\d+$")
CHILE_TZ = timezone(timedelta(hours=-4))


def _integer(value: Any, label: str) -> int:
    text = str(value).strip()
    if not INTEGER_PATTERN.fullmatch(text):
        raise ValidationFailure(
            f"El valor '{value}' no es un número entero válido para {label}"
        )
    return int(text)


def _iso_datetime(value: Any, label: str, *, end_of_day: bool) -> datetime:
    text = str(value).strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationFailure(
            f"El valor '{value}' no es una fecha ISO-8601 válida para {label}"
        ) from exc

    date_only = "T" not in text and " " not in text
    if date_only:
        parsed = datetime.combine(
            parsed.date(), time.max if end_of_day else time.min
        )
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(CHILE_TZ).replace(tzinfo=None)
    return parsed


def validate_filters(items: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    validated: dict[str, Any] = {}

    for name, value in items:
        if name not in ALLOWED_FILTERS:
            raise ValidationFailure(
                f"La consulta '{name}' no corresponde a un filtro permitido"
            )
        if name in validated:
            raise ValidationFailure(f"La consulta '{name}' está repetida")
        if value is None or (isinstance(value, str) and not value.strip()):
            raise ValidationFailure(f"El valor de la consulta '{name}' está vacío o nulo")

        if name == "GENERO":
            converted = str(value).strip()
            if converted not in ALLOWED_GENDERS:
                raise ValidationFailure(
                    f"El valor '{value}' no es un género permitido"
                )
        elif name == "CANAL":
            converted = str(value).strip()
            if converted not in ALLOWED_CHANNELS:
                raise ValidationFailure(
                    f"El valor '{value}' no es un canal permitido"
                )
        elif name == "EDAD":
            converted = _integer(value, "la edad")
            if converted < 0 or converted > 130:
                raise ValidationFailure(f"El valor '{value}' no es una edad válida")
        elif name == "CODIGO_PRODUCTO":
            converted = _integer(value, "el código de producto")
        elif name == "LOCAL":
            converted = _integer(value, "el ID de tienda")
        elif name == "ID_PERSONA":
            try:
                converted = str(UUID(str(value).strip()))
            except (ValueError, AttributeError) as exc:
                raise ValidationFailure(
                    f"El valor '{value}' no es un UUID válido para ID_PERSONA"
                ) from exc
        elif name == "FECHA_DESDE":
            converted = _iso_datetime(value, name, end_of_day=False)
        else:
            converted = _iso_datetime(value, name, end_of_day=True)

        validated[name] = converted

    start = validated.get("FECHA_DESDE")
    end = validated.get("FECHA_HASTA")
    if start is not None and end is not None and start > end:
        raise ValidationFailure("FECHA_DESDE no puede ser posterior a FECHA_HASTA")

    return validated
