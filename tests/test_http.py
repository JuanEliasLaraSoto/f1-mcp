from starlette.testclient import TestClient

from f1_mcp.mcp.server import mcp_server

ACCEPT = {"Accept": "application/json, text/event-stream"}


def test_http_app_serves_health_and_tools() -> None:
    # host="0.0.0.0" as in Docker; with 127.0.0.1 the SDK's DNS-rebinding
    # protection rejects any other Host header with 421.
    app = mcp_server.streamable_http_app(stateless_http=True, host="0.0.0.0")
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        listed = client.post(
            "/mcp",
            headers=ACCEPT,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        assert listed.status_code == 200
        assert '"name":"compare_drivers"' in listed.text
