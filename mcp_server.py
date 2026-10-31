import json
import sys
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ResourceNotFoundError, ToolError

mcp= MCPServer("orders")
ORDERS = {
    "A100": {"status": "shipped", "total": 59.90},
    "A200": {"status": "processing", "total": 120.00},
}

def log(msg: str):
    # With stdio transport, stdout IS the protocol channel. Log to stderr only.
    print(msg, file=sys.stderr)

@mcp.tool("get_order_status")
def get_order_status(order_id: str) -> dict:
    """Look up the status and total of ONE customer order by order ID
    (format: 'A' followed by digits). Read-only; never modifies anything.
    """
    log(f"get_order_status({order_id})")
    order = ORDERS.get(order_id)
    if order is None:
        raise ToolError(f"no such order: {order_id}")
    return order

@mcp.resource("orders://{orders_id}")
def order_resource(orders_id: str) -> str:
    """Resource for a single order, identified by its ID."""
    log(f"order_resource({orders_id})")
    order = ORDERS.get(orders_id)
    if order is None:
        raise ResourceNotFoundError(f"no such order: {orders_id}")
    return json.dumps(order)

@mcp.prompt()
def summarize_prompt(order_id: str) -> str:
     """Template: ask for a customer-friendly order summary."""
     return f"Look up order {order_id} and write a two-sentence customer-friendly summary."

if __name__ == "__main__":
    mcp.run(transport="stdio")  # Use stdio transport for testing
