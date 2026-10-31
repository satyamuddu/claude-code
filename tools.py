import json
import anthropic

client = anthropic.Anthropic()
MODEL = "claude-haiku-5-5"

ORDERS = {
    "A100": {"status": "shipped", "total": 59.90},
    "A200": {"status": "processing", "total": 120.00},
}

tools = [
    {
        "name": "get_order_status",
        "description": (
            "Look up the status and total of ONE customer order by order ID "
            "(format: 'A' followed by digits). Use for questions about where an "
            "order is or what it cost. Read-only; never modifies anything."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID, e.g. 'A100'"}
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "cancel_order",
        "description": (
            "Cancel an order that has NOT shipped yet. Irreversible. "
            "Only call when the user explicitly asks to cancel."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
]

def run_tool(name: str, args: dict) -> str:
    if name == "get_order_status":
        order = ORDERS.get(args["order_id"])
        if order is None:
            raise KeyError(f"no such order: {args['order_id']}")
        return json.dumps(order)

    if name == "cancel_order":
        order = ORDERS.get(args["order_id"])
        if order is None:
            raise KeyError(f"no such order: {args['order_id']}")
        if order["status"] == "shipped":
            raise ValueError("order already shipped, cannot cancel")
        # Approval pattern: a human confirms destructive actions
        if input(f"Approve cancel of {args['order_id']}? [y/N] ").lower() != "y":
            return "DENIED: the user did not approve this cancellation"
        order["status"] = "canceled"
        return "order canceled"

    raise ValueError(f"unknown tool: {name}")

def run_agent(user_text: str, max_turns: int = 8) -> str:
    messages = [{"role": "user", "content": user_text}]

    for turn in range(max_turns):                      # hard cap: no infinite loops
        r = client.messages.create(
            model=MODEL, max_tokens=1000, tools=tools, messages=messages
        )
        messages.append({"role": "assistant", "content": r.content})  # keep ALL blocks

        if r.stop_reason != "tool_use":
            return "".join(b.text for b in r.content if b.type == "text")

        results = []
        for block in r.content:
            if block.type != "tool_use":
                continue
            print(f"[turn {turn}] tool call: {block.name}({block.input})")
            try:
                out = run_tool(block.name, block.input)
                results.append({"type": "tool_result",
                                "tool_use_id": block.id, "content": out})
            except Exception as e:
                # Report the failure to Claude instead of crashing
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": f"Error: {e}", "is_error": True})

        messages.append({"role": "user", "content": results})  # ONE message, all results

    raise RuntimeError("max_turns exceeded")

for q in [
    "Where is order A100 and what did it cost?",
    "Which is more expensive, A100 or A200?",
    "What's the status of order Z999?",
    "Please cancel order A200.",
]:
    print("\nQ:", q)
    print("A:", run_agent(q))