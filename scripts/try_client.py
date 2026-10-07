"""Test MCP client: plays the role of Claude against our server, in memory.

Usage:
  uv run python scripts/try_client.py                         -> tools (description + schema)
  uv run python scripts/try_client.py TOOL '{"arg": value}'   -> call a tool
  uv run python scripts/try_client.py resources               -> list resources and templates
  uv run python scripts/try_client.py read URI                -> read a resource
  uv run python scripts/try_client.py prompts                 -> list prompts
  uv run python scripts/try_client.py prompt NAME '{...}'     -> render a prompt
"""

import asyncio
import json
import sys

from mcp.client._memory import InMemoryTransport
from mcp.client.session import ClientSession

from f1_mcp.mcp.server import mcp_server


async def main() -> None:
    args = sys.argv[1:]
    async with InMemoryTransport(mcp_server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            if not args:
                tools = await session.list_tools()
                for t in tools.tools:
                    print(f"=== {t.name} ===")
                    print("Description:", t.description)
                    print(json.dumps(t.input_schema, indent=2))

            elif args[0] == "resources":
                fixed = await session.list_resources()
                templates = await session.list_resource_templates()
                for r in fixed.resources:
                    print(f"{r.uri}  —  {r.description}")
                for t in templates.resource_templates:
                    print(f"{t.uri_template}  —  {t.description}")

            elif args[0] == "read":
                result = await session.read_resource(args[1])
                print(result.contents[0].text)

            elif args[0] == "prompts":
                prompts = await session.list_prompts()
                for p in prompts.prompts:
                    params = ", ".join(a.name for a in (p.arguments or []))
                    print(f"{p.name}({params})  —  {p.description}")

            elif args[0] == "prompt":
                arguments = json.loads(args[2]) if len(args) > 2 else {}
                result = await session.get_prompt(args[1], arguments)
                for m in result.messages:
                    print(f"[{m.role}]\n{m.content.text}")

            else:
                tool_args = json.loads(args[1]) if len(args) > 1 else {}
                result = await session.call_tool(args[0], tool_args)
                print(f"=== {args[0]}({tool_args}) ===")
                print(result.content[0].text)


asyncio.run(main())
