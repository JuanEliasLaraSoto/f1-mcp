"""Resources MCP: datos de solo lectura con dirección (URI) que el cliente puede
listar y adjuntar al contexto, como un documento. Devuelven JSON, no texto formateado."""

from typing import Any

from f1_mcp import openf1
from f1_mcp.server import mcp_server


@mcp_server.resource("f1://sessions/{year}", mime_type="application/json")
async def sessions_resource(year: str) -> dict[str, Any]:
    """Calendario de sesiones de un año: session_key, nombre, circuito, país y fecha."""
    sessions = await openf1.get("sessions", year=int(year))
    return {
        "year": int(year),
        "sessions": [
            {
                "session_key": s["session_key"],
                "session_name": s["session_name"],
                "circuit": s["circuit_short_name"],
                "country": s["country_name"],
                "date": s["date_start"][:10],
            }
            for s in sessions
        ],
    }


@mcp_server.resource("f1://session/{session_key}/results", mime_type="application/json")
async def results_resource(session_key: str) -> dict[str, Any]:
    """Clasificación final de una sesión en JSON, con siglas y equipo de cada piloto."""
    results = await openf1.get("session_result", session_key=int(session_key))
    drivers = await openf1.get("drivers", session_key=int(session_key))
    info = {d["driver_number"]: d for d in drivers}
    return {
        "session_key": int(session_key),
        "results": [
            {
                "position": r.get("position"),
                "driver_number": r["driver_number"],
                "driver": info.get(r["driver_number"], {}).get("name_acronym"),
                "team": info.get(r["driver_number"], {}).get("team_name"),
                "laps": r.get("number_of_laps"),
                "gap_to_leader": r.get("gap_to_leader"),
                "dnf": r.get("dnf"),
                "dns": r.get("dns"),
                "dsq": r.get("dsq"),
            }
            for r in sorted(
                results, key=lambda r: (r.get("position") is None, r.get("position") or 0)
            )
        ],
    }
