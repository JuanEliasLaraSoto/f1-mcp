def main() -> None:
    from f1_mcp import config
    from f1_mcp.mcp.server import mcp_server

    if config.TRANSPORT == "http":
        mcp_server.run("streamable-http", host=config.HOST, port=config.PORT, stateless_http=True)
    else:
        mcp_server.run()
