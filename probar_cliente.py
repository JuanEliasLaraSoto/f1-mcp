import asyncio
import json

from mcp.client._memory import InMemoryTransport
from mcp.client.session import ClientSession

from f1_mcp.server import mcp_server


async def main() -> None:
    # Conecta un cliente MCP a nuestro servidor, en memoria (sin stdio ni red)
    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Lo que Claude ve: la lista de tools con su esquema JSON
            tools = await session.list_tools()
            for t in tools.tools:
                print(f"=== {t.name} ===")
                print(json.dumps(t.input_schema, indent=2))

            # 2. Lo que Claude haría: llamar a una tool con argumentos
            result = await session.call_tool("list_sessions", {"year": 2025, "country": "Italy"})
            print("\n=== Resultado de list_sessions ===")
            print(result.content[0].text)


asyncio.run(main())
