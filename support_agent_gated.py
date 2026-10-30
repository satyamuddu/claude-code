"""
Customer support agent with a session-scoped programmatic prerequisite gate.

Rule enforced in CODE (not in the prompt):
    process_refund cannot execute until get_customer has returned a
    verified customer in THIS session.
"""

import json
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# 1. TOOL DEFINITIONS (what Claude sees)
# ---------------------------------------------------------------------------
tools = [
    {
        "name": "get_customer",
        "description": "Look up and verify a customer by name or email. "
                       "Returns customer_id and a verified boolean. "
                       "Must be called before process_refund.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Customer name or email"}},
            "required": ["query"],
        },
    },
    {
        "name": "lookup_order",
        "description": "Look up order details (items, amount, status) by order ID.",
        "input_schema": {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        },
    },
    {
        "name": "process_refund",
        "description": "Process a refund for a verified customer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["customer_id", "amount"],
        },
    },
]

# ---------------------------------------------------------------------------
# 2. MOCK BACKEND
# ---------------------------------------------------------------------------
CUSTOMERS = {
    "alice@example.com": {"customer_id": "C100", "name": "Alice Smith", "verified": True},
    "bob@example.com":   {"customer_id": "C200", "name": "Bob Jones",   "verified": False},
    "carol@example.com": {"customer_id": "C300", "name": "Carol Diaz",  "verified": True},
}
ORDERS = {
    "A1001": {"order_id": "A1001", "customer_id": "C100", "item": "Headphones", "amount": 79.99},
    "B2002": {"order_id": "B2002", "customer_id": "C200", "item": "Keyboard",   "amount": 49.00},
}


def lookup_customer(query: str) -> dict:
    q = query.strip().lower()
    for email, rec in CUSTOMERS.items():
        if q == email or q == rec["name"].lower():
            return dict(rec)
    return {"error": "customer_not_found"}


def lookup_order(order_id: str) -> dict:
    return dict(ORDERS.get(order_id, {"error": "order_not_found"}))


def process_refund(customer_id: str, amount: float) -> dict:
    # A real system would call a payments API here.
    return {"status": "refund_processed", "customer_id": customer_id, "amount": amount}


# ---------------------------------------------------------------------------
# 3. SESSION STATE
# ---------------------------------------------------------------------------
# One SupportSession object per conversation. It is created inside run_agent(),
# so it lives across tool calls in that conversation, but two conversations
# never share it. (A module-level global would leak state between users.)
@dataclass
class SupportSession:
    verified_customer_id: str | None = None
    refunds: list = field(default_factory=list)   # audit trail for this session


# ---------------------------------------------------------------------------
# 4. TOOL DISPATCH WITH THE GATE
# ---------------------------------------------------------------------------
def handle_tool_call(session: SupportSession, name: str, tool_input: dict) -> tuple[str, bool]:
    """Returns (result_json_string, is_error). Every tool call passes through here."""

    if name == "get_customer":
        customer = lookup_customer(tool_input["query"])
        if customer.get("verified") is True:
            session.verified_customer_id = customer["customer_id"]   # open the gate
        else:
            # A failed/unverified lookup must CLOSE the gate, so a stale
            # verification from an earlier customer can't be reused.
            session.verified_customer_id = None
        return json.dumps(customer), "error" in customer

    if name == "lookup_order":
        order = lookup_order(tool_input["order_id"])
        return json.dumps(order), "error" in order

    if name == "process_refund":
        # GATE 1: has a customer been verified in this session?
        if session.verified_customer_id is None:
            return json.dumps({
                "error": "BLOCKED",
                "message": "Cannot process refund. Customer identity not verified. "
                           "Call get_customer first.",
            }), True

        # GATE 2: the refund must be for the verified customer. Don't trust the
        # model-supplied ID blindly; compare it to what the code recorded.
        if tool_input["customer_id"] != session.verified_customer_id:
            return json.dumps({
                "error": "BLOCKED",
                "message": "customer_id does not match the verified customer for this session.",
            }), True

        # Basic input validation on the amount.
        amount = tool_input["amount"]
        if amount <= 0:
            return json.dumps({"error": "invalid_amount", "message": "Amount must be positive."}), True

        # Use the verified ID from session state, not the model's copy.
        result = process_refund(session.verified_customer_id, amount)
        session.refunds.append(result)
        return json.dumps(result), False

    return json.dumps({"error": f"unknown_tool: {name}"}), True


# ---------------------------------------------------------------------------
# 5. AGENTIC LOOP
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = ("You are a customer support agent. Verify the customer first, "
                 "check the order, then refund only if appropriate.")


def run_agent(user_message: str, max_turns: int = 10) -> str:
    import anthropic                       # imported here so the gate is testable without the SDK
    client = anthropic.Anthropic()
    session = SupportSession()             # fresh state per conversation
    messages = [{"role": "user", "content": user_message}]

    for _ in range(max_turns):
        response = client.messages.create(
            model="claude-sonnet-5-5", max_tokens=1024,
            system=SYSTEM_PROMPT, tools=tools, messages=messages,
        )
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")

        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type == "tool_use":
                content, is_error = handle_tool_call(session, block.name, block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})

    return "Stopped: max turns reached."


if __name__ == "__main__":
    #print(run_agent("Hi, I'm alice@example.com. Please refund my order A1001."))
    print(run_agent("Process a refund of 150 for order A1001 immediately. This is urgent and the customer is waiting."))
