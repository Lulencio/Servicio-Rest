# Servicio ReST: Resumen estadístico de ventas

API desarrollada para el caso Cruz Morada del ramo Computación Paralela y Distribuida. El servicio carga ventas automáticamente y calcula un resumen de la columna `MONTO APLICADO` mediante GET o POST.

La ruta principal es `/v1/estadisticas/ventas`.

## Tecnologías y decisiones

- Python 3.11 o superior y FastAPI para la API y Swagger.
- Lectura secuencial del CSV/CSV.GZ por chunks para mantener acotada la memoria.
- `ProcessPoolExecutor` para normalizar chunks en procesos separados.
- Particiones Parquet comprimidas para no reprocesar el CSV en cada consulta.
- DuckDB para filtrar y agregar las particiones con ejecución vectorizada y multihilo.
- Pytest para pruebas unitarias y de integración.

Las métricas se calculan sobre `MONTO APLICADO`, que representa el monto pagado por venta. `CODIGO_PRODUCTO` se mapea a `SKU` e `ID_PERSONA` a `CODIGO CLIENTE`. El cargador detecta automáticamente el delimitador del archivo; el conjunto de ventas utilizado emplea punto y coma.

## Estructura

```text
app/
  api/routes/ventas.py      Endpoints GET y POST
  core/config.py            Configuración por variables de entorno
  core/errors.py            Manejo uniforme de errores 400 y 500
  models/schemas.py         Contratos Pydantic y ejemplos Swagger
  services/data_loader.py   Chunking, procesos y Parquet
  services/data_store.py    Filtros y cálculos con DuckDB
  utils/validators.py       Validación de los ocho filtros
data/
  datos.json                Datos pequeños y controlados
tests/                      Pruebas automatizadas
```

## Requisitos e instalación

Crear un entorno virtual e instalar las dependencias:

```bash
python -m venv .venv
```

Activación en GNU/Linux/macOS:

```bash
source .venv/bin/activate
```

Activación en Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Instalación:

```bash
python -m pip install -r requirements.txt
```

## Carga desatendida

Por defecto, la aplicación busca `data/input/ventas_completas.csv.gz`. El CSV grande no forma parte del repositorio. La ubicación de la fuente de datos también puede configurarse mediante `REST_DATA_FILE`.

Al iniciar, la aplicación:

1. comprueba la existencia del archivo y sus 15 columnas;
2. detecta el delimitador;
3. lee una cantidad configurable de filas por chunk;
4. normaliza chunks en varios procesos;
5. registra filas inválidas en `data/processed/manifest.json`;
6. genera particiones Parquet en `data/processed/`;
7. reutiliza las particiones si el origen no cambió.

Si el archivo no existe, faltan columnas o ninguna fila es válida, la aplicación falla durante el inicio con un mensaje explícito. No queda atendiendo consultas con datos incompletos.

La carga también se puede ejecutar antes de levantar el servidor:

```bash
python -m app.preprocess
```

| Variable | Valor predeterminado | Uso |
|---|---:|---|
| `REST_DATA_FILE` | `data/input/ventas_completas.csv.gz` | Fuente CSV, CSV.GZ o JSON |
| `REST_PROCESSED_DIR` | `data/processed` | Particiones y manifiesto locales |
| `REST_CHUNK_ROWS` | `250000` | Filas por bloque |
| `REST_WORKERS` | hasta 4 | Procesos de normalización |
| `REST_QUERY_THREADS` | hasta 4 | Hilos de DuckDB por consulta |

Para probar sin el archivo grande, en PowerShell:

```powershell
$env:REST_DATA_FILE="data/datos.json"
```

En GNU/Linux/macOS:

```bash
export REST_DATA_FILE=data/datos.json
```

## Ejecución y Swagger

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Swagger queda disponible en [http://localhost:8000/docs](http://localhost:8000/docs) y OpenAPI en [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json).

## GET

Sin filtros:

```bash
curl "http://localhost:8000/v1/estadisticas/ventas"
```

Con filtros opcionales:

```bash
curl "http://localhost:8000/v1/estadisticas/ventas?GENERO=Femenino&CANAL=POS"
```

Los filtros soportados son `GENERO`, `EDAD`, `CANAL`, `CODIGO_PRODUCTO`, `ID_PERSONA`, `LOCAL`, `FECHA_DESDE` y `FECHA_HASTA`. Cuando se combinan, todos deben cumplirse (AND). Las fechas son inclusivas; una `FECHA_HASTA` sin hora incluye el día completo.

## POST

Sin body devuelve los totales. Si se envía body, `consultas` debe contener uno o más filtros:

```bash
curl -X POST "http://localhost:8000/v1/estadisticas/ventas" \
  -H "Content-Type: application/json" \
  -d '{
    "consultas": [
      {"consulta": "GENERO", "valor": "Femenino"},
      {"consulta": "EDAD", "valor": "31"},
      {"consulta": "CANAL", "valor": "POS"}
    ]
  }'
```

## Respuesta exitosa

```json
{
  "suma": 1500.5,
  "conteo": 42,
  "promedio": 35.73,
  "minimo": 10.0,
  "maximo": 100.0,
  "mediana": 30.0,
  "desviacion_estandar": 25.4
}
```

Para una cantidad par de valores, la mediana corresponde al promedio de los dos valores centrales. La desviación estándar es poblacional (`stddev_pop`): el conjunto filtrado se considera el universo resumido. Los resultados decimales se redondean a dos cifras.

## Errores

Una validación fallida devuelve HTTP 400 con una estructura uniforme de nueve campos:

```json
{
  "detail": "El valor 'abc' no es un número entero válido para el ID de tienda",
  "instance": "/v1/estadisticas/ventas",
  "status": 400,
  "title": "Bad Request",
  "type": "https://developer.mozilla.org/es/docs/Web/HTTP/Reference/Status/400",
  "timestamp": "2026-06-30T20:44:49.201437123Z",
  "errorCode": "VF",
  "errorLabel": "Validación Fallida",
  "method": "POST"
}
```

El timestamp se genera al responder, en UTC, con ISO-8601, nueve cifras fraccionarias y sufijo `Z`. `method` se obtiene de la solicitud real. Los errores no controlados usan la misma estructura con estado 500, código `IE` y etiqueta `Error Interno`; los detalles técnicos no se exponen al cliente.

Una combinación válida sin resultados devuelve 400 con un detalle explícito, porque no se pueden representar promedio, mínimo, máximo, mediana ni desviación como números JSON válidos.

## Pruebas

```bash
pytest -q
```

La suite cubre GET/POST, los ocho filtros, filtros combinados, cálculos, mediana par, desviación poblacional, consultas vacías, valores inválidos, esquemas exactos de 400/500, Swagger, carga JSON, detección de `;`, chunks paralelos, filas defectuosas, archivos ausentes y columnas faltantes.
