# Resources y prompts: las otras dos primitivas de MCP

**Fecha:** 2026-10-07

## Criterio: ¿tool, resource o prompt?

- **Tool**: la decide el modelo y suele calcular algo con argumentos
  (compare_drivers, race_strategy). Devuelve texto pensado para que el modelo lo interprete.
- **Resource**: dato de solo lectura con URI que la aplicación o el usuario adjunta al
  contexto, como un documento. Devuelve JSON. `f1://sessions/{year}` y
  `f1://session/{session_key}/results`.
- **Prompt**: plantilla que elige el usuario. Encapsula conocimiento del dominio: qué
  tools encadenar y qué criterio aplicar al concluir. `analizar_carrera`, `comparar_pilotos`.

## Decisiones

- Los resources devuelven JSON y no tablas: su consumidor es una máquina o un contexto,
  no una lectura directa.
- `comparar_pilotos` pide explícitamente distinguir ritmo puro de resultado final. Motivo
  real: en Monza 2025 NOR terminó P2 con una parada de 5,9 s frente a 1,9 s de PIA;
  el resultado no refleja solo el ritmo.
- Registro por import al final de `server.py` (evita el import circular), mismo patrón
  que spotify-mcp.

## Verificación

Tests a través del protocolo MCP real (cliente en memoria): resources y prompts
registrados, lectura del resource de resultados con datos simulados y contenido del prompt.
