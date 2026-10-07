# Calidad: errores amigables, ruff, mypy estricto y cobertura

**Fecha:** 2026-10-07

## Errores amigables

Si OpenF1 fallaba (timeout, sin red, 429 persistente, 5xx), la tool lanzaba una excepción
de httpx y el modelo recibía un error técnico. Ahora `openf1.get` traduce todos los fallos
a `OpenF1Error` con un mensaje legible, y el decorador `friendly_errors` (en `mcp/errors.py`)
lo convierte en texto que el modelo puede explicar o reintentar. Un decorador en vez de un
try/except por tool: el manejo de errores vive en un solo sitio. `functools.wraps` conserva
nombre, docstring y firma, así que el esquema MCP no cambia (verificado).

## Herramientas de calidad

- **ruff** (lint + formato), reglas E, F, I, UP, B. Excepciones E501 en prompts (texto) y
  tests (datos de prueba).
- **mypy strict** sobre `src/`. Pasa sin cambios de código: los tipos se anotaron desde el
  principio. El decorador usa genéricos PEP 695 (`[**P]`) para conservar la firma.
- **pytest-cov** con `fail_under = 80`. Se excluye `__init__.py` (solo arranca el servidor).

## Cobertura

Al medir por primera vez: 79 %, con `laps.py` al 26 % (sus tres tools no tenían tests).
Tras añadir tests con datos sintéticos de propiedades conocidas y tests por protocolo MCP
(registro de las 8 tools con descripción, llamadas extremo a extremo): **95 %**, 32 tests.
