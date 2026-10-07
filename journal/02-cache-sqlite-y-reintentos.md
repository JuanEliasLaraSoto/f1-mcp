# Caché en SQLite y reintentos ante 429

**Fecha:** 2026-10-07

## Problema

El plan gratuito de OpenF1 limita a 3 peticiones/segundo y 30/minuto. Una sola pregunta
a Claude puede encadenar varias tools (list_sessions → list_drivers → compare_drivers →
get_stints), cada una con 1-3 peticiones: en una conversación normal se alcanza el límite.

## Decisión

- **Caché en SQLite** (`~/.cache/f1-mcp/openf1.sqlite`), clave = endpoint + parámetros
  serializados con `sort_keys`. Los datos de sesiones pasadas no cambian, así que no
  caducan. No se cachean respuestas vacías (sesiones aún sin datos publicados).
- **`sqlite3` de la librería estándar**, sin ORM: una sola tabla clave-valor no lo justifica.
- **Reintento ante 429** con espera exponencial (1 s, 2 s), máximo 3 intentos.

## Verificación

- Test: dos llamadas iguales → `call_count == 1` en el mock de respx.
- Test: respuesta 429 seguida de 200 → resultado correcto con 2 llamadas.
- Los tests usan una caché temporal (`conftest.py`) para no depender de la real.
- Manual: `compare_drivers` repetido baja de [rellenar] s a [rellenar] s.
