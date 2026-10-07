"""MCP prompts: templates the user picks in the client (usually shown as a menu or
as /commands). Each one starts an analysis by telling the model which tools to
chain and in what order."""

from f1_mcp.mcp.server import mcp_server


@mcp_server.prompt()
def analyze_race(year: int, circuit: str) -> str:
    """Full race analysis: result, strategies, pace at the front and the winner's
    tyre management."""
    return (
        f"Analyse the {year} F1 race at {circuit}.\n\n"
        f"1. Use list_sessions with year={year} and circuit='{circuit}' to find the "
        "session_key of the 'Race' session.\n"
        "2. get_results for the final classification and retirements.\n"
        "3. race_strategy to see which strategies worked and whether any pit stop was "
        "unusually slow.\n"
        "4. compare_drivers between the winner and the runner-up.\n"
        "5. get_stints for the winner to see their tyre degradation.\n\n"
        "Write a clear summary for a fan: what decided the race, which strategy was the "
        "right one and who managed their tyres best. Back every claim with numbers from "
        "the tools and do not invent data that does not appear in them."
    )


@mcp_server.prompt()
def driver_duel(year: int, circuit: str, driver_a: str, driver_b: str) -> str:
    """Detailed duel between two drivers in a race: pace, consistency, strategy and
    degradation."""
    return (
        f"Compare {driver_a} and {driver_b} in the {year} F1 race at {circuit}.\n\n"
        f"1. list_sessions (year={year}, circuit='{circuit}') for the race session_key.\n"
        "2. list_drivers to get each driver's driver_number.\n"
        "3. compare_drivers for pace, consistency and the lap-by-lap duel.\n"
        "4. get_stints for both drivers to compare strategy and degradation.\n"
        "5. get_results to see where each of them finished.\n\n"
        "Conclude who was really faster and why. Distinguish raw pace (lap-by-lap gap "
        "in comparable conditions) from the final result, which can depend on strategy, "
        "a slow pit stop or a retirement."
    )
