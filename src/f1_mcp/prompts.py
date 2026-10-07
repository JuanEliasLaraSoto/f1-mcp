"""Prompts MCP: plantillas que el usuario elige en el cliente (suelen aparecer como
un menú o comandos con /). Cada una arranca un análisis guiando al modelo sobre
qué tools encadenar y en qué orden."""

from f1_mcp.server import mcp_server


@mcp_server.prompt()
def analizar_carrera(year: int, circuit: str) -> str:
    """Análisis completo de una carrera: resultado, estrategias, ritmo de los de
    delante y gestión de neumáticos del ganador."""
    return (
        f"Analiza la carrera de F1 de {year} en {circuit}.\n\n"
        f"1. Usa list_sessions con year={year} y circuit='{circuit}' para encontrar el "
        "session_key de la sesión 'Race'.\n"
        "2. get_results para el resultado final y los abandonos.\n"
        "3. race_strategy para ver qué estrategias funcionaron y si alguna parada "
        "fue anormalmente lenta.\n"
        "4. compare_drivers entre el ganador y el segundo.\n"
        "5. get_stints del ganador para ver su degradación de neumáticos.\n\n"
        "Escribe un resumen claro para un aficionado: qué decidió la carrera, qué "
        "estrategia fue la buena y quién gestionó mejor los neumáticos. Apoya cada "
        "afirmación en los números de las tools y no inventes datos que no aparezcan."
    )


@mcp_server.prompt()
def comparar_pilotos(year: int, circuit: str, piloto_a: str, piloto_b: str) -> str:
    """Duelo detallado entre dos pilotos en una carrera: ritmo, consistencia,
    estrategia y degradación."""
    return (
        f"Compara a {piloto_a} y {piloto_b} en la carrera de F1 de {year} en {circuit}.\n\n"
        f"1. list_sessions (year={year}, circuit='{circuit}') para el session_key de la carrera.\n"
        "2. list_drivers para obtener el driver_number de cada uno.\n"
        "3. compare_drivers para ritmo, consistencia y duelo vuelta a vuelta.\n"
        "4. get_stints de ambos para comparar estrategia y degradación.\n"
        "5. get_results para saber dónde terminó cada uno.\n\n"
        "Concluye quién fue realmente más rápido y por qué. Distingue entre ritmo puro "
        "(diferencia vuelta a vuelta en condiciones comparables) y resultado final, que "
        "puede depender de la estrategia, de una parada lenta o de un abandono."
    )
