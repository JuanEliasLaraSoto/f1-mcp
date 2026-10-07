# Reorganización del código por responsabilidad

**Fecha:** 2026-10-07

## Problema

`server.py` superaba las 300 líneas y mezclaba creación del servidor, ocho tools de
temas distintos y funciones de formato. Cada fase nueva lo hacía crecer más.

## Decisión

Separar por responsabilidad, siguiendo la misma estructura que spotify-mcp:

- `config.py`: URL de la API, ruta de la caché y reintentos, en un solo sitio.
- `formatting.py`: fmt_time, fmt_duration, fmt_gap.
- `analysis.py`: matemáticas puras (se le añade of_driver).
- `mcp/server.py`: solo crea MCPServer, define ping e importa el resto al final.
- `mcp/tools/`: sessions.py (calendario, pilotos, resultados), laps.py (vueltas,
  comparación, stints), strategy.py (estrategia de carrera).
- `mcp/resources.py` y `mcp/prompts.py`.
- `scripts/probar_cliente.py`.

El código se movió con un script basado en `ast` (copia exacta de cada función con sus
decoradores) y `git mv` para conservar el historial.

## Verificación

Refactor sin cambios de comportamiento: los 19 tests pasan igual antes y después, y las
8 tools, 2 resources y 2 prompts siguen registrados.
