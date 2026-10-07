"""Cliente MCP de prueba: hace de "Claude" contra nuestro servidor.

Uso:
  uv run python probar_cliente.py                       -> lista tools y sus esquemas
  uv run python probar_cliente.py TOOL '{"arg": valor}' -> llama a una tool
"""

import asyncio
import json
import sys

from mcp.client._memory import InMemoryTransport
from mcp.client.session import ClientSession

from f1_mcp.server import mcp_server


async def main() -> None:
    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Sin argumentos: enseña lo que vería Claude (tools + esquemas)
            if len(sys.argv) == 1:
                tools = await session.list_tools()
                for t in tools.tools:
                    print(f"=== {t.name} ===")
                    print(json.dumps(t.input_schema, indent=2))
                return

            # Con argumentos: llama a la tool indicada
            tool = sys.argv[1]
            args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
            result = await session.call_tool(tool, args)
            print(f"=== {tool}({args}) ===")
            print(result.content[0].text)


asyncio.run(main())
