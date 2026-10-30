"""
Customer support agent with three tools and a programmatic prerequisite gate.

Tools:
  get_customer   -> returns customer_id + verified flag
  lookup_order   -> returns order details (including amount)
  process_refund -> refunds an amount for a VERIFIED customer

Key exam idea: the rule "never refund before the customer is verified" is
enforced in CODE (the gate), not just in the prompt. Prompts are probabilistic
(the "8% failure rate"); code is deterministic.
"""

import json                      # to serialize tool results into strings for Claude
import anthropic                 # official Anthropic SDK

# ---------------------------------------------------------------------------
# 1. TOOL DEFINITIONS (what Claude sees)
# ---------------------------------------------------------------------------
# Each tool is a dict with: name, description, input_schema (JSON Schema).
# Claude reads the description to decide WHEN to call the tool, and the
# input_schema to know HOW to call it.
tools = [
    {
        "name": "get_customer",                                   # unique tool name Claude will call
        "description": "Look up and verify a customer by name or email. "
                       "Returns customer_id and a verified boolean. "
                       "Must be called before process_refund.",   # hints at the workflow dependency
        "input_schema": {
            "type": "object",                                     # input is always a JSON object
            "properties": {
                "query": {"type": "string",
                          "description": "Customer name or email"}
            },
            "required": ["query"],                                # Claude must supply 'query'
        },
    },
    {
        "name": "lookup_order",
        "description": "Look up order details (items, amount, status) by order ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Order ID, e.g. A1001"}
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "process_refund",
        "description": "Process a refund for a verified customer. "
                       "Requires the customer_id returned by get_customer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "amount": {"type": "number", "description": "Refund amount in USD"},
            },
            "required": ["customer_id", "amount"],            # both fields mandatory
        },
    },
]

# ---------------------------------------------------------------------------
# 2. MOCK BACKEND DATA (stand-in for a real database / API)
# ---------------------------------------------------------------------------
CUSTOMERS = {
    "alice@example.com": {"customer_id": "C100", "name": "Alice Smith", "verified": True},
    "bob@example.com":   {"customer_id": "C200", "name": "Bob Jones",   "verified": False},
}
ORDERS = {
    "A1001": {"order_id": "A1001", "customer_id": "C100", "item": "Headphones",
              "amount": 79.99, "status": "delivered"},
    "B2002": {"order_id": "B2002", "customer_id": "C200", "item": "Keyboard",
              "amount": 49.00, "status": "delivered"},
}

# ---------------------------------------------------------------------------
# 3. TOOL IMPLEMENTATIONS (what actually runs when Claude calls a tool)
# ---------------------------------------------------------------------------
def get_customer(query: str) -> dict:
    q = query.strip().lower()                                  # normalize input
    for email, record in CUSTOMERS.items():                    # search by email or name
        if q == email or q == record["name"].lower():
            # Return ONLY what's needed; 'verified' is the key field for the gate.
            return {"customer_id": record["customer_id"],
                    "name": record["name"],
                    "verified": record["verified"]}
    return {"error": "customer_not_found"}                     # structured error, not an exception


def lookup_order(order_id: str) -> dict:
    return ORDERS.get(order_id, {"error": "order_not_found"})  # dict.get with fallback


def process_refund(customer_id: str, amount: float) -> dict:
    # (A real system would call a payments API here.)
    return {"status": "refund_processed", "customer_id": customer_id, "amount": amount}


# ---------------------------------------------------------------------------
# 4. THE PREREQUISITE GATE (programmatic enforcement)
# ---------------------------------------------------------------------------
# Session state: customer_ids that get_customer has returned as verified=True.
verified_customers: set[str] = set()


def execute_tool(name: str, tool_input: dict) -> dict:
    """Single choke point: every tool call from Claude passes through here."""

    if name == "get_customer":
        result = get_customer(**tool_input)                    # **tool_input unpacks {'query': ...}
        if result.get("verified") is True:                     # record successful verification
            verified_customers.add(result["customer_id"])
        return result

    if name == "lookup_order":
        return lookup_order(**tool_input)

    if name == "process_refund":
        # GATE: block the call unless this customer was verified earlier.
        if tool_input["customer_id"] not in verified_customers:
            return {"error": "prerequisite_not_met",
                    "message": "Customer must be verified via get_customer "
                               "before a refund can be processed."}
        return process_refund(**tool_input)

    return {"error": f"unknown_tool: {name}"}                  # defensive default


# ---------------------------------------------------------------------------
# 5. THE AGENTIC LOOP
# ---------------------------------------------------------------------------
client = anthropic.Anthropic()                                 # reads ANTHROPIC_API_KEY from env

SYSTEM_PROMPT = ("You are a customer support agent. Verify the customer first, "
                 "check the order, then refund only if appropriate.")


def run_agent(user_message: str, max_turns: int = 10) -> str:
    messages = [{"role": "user", "content": user_message}]     # conversation history

    for _ in range(max_turns):                                 # safety cap against infinite loops
        response = client.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=tools,                                       # advertise the three tools
            messages=messages,
        )

        # stop_reason != "tool_use" means Claude is done -> return its final text.
        if response.stop_reason != "tool_use":
            return "".join(b.text for b in response.content if b.type == "text")

        # Claude's tool-call turn must be appended to history as-is.
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:                         # may contain several tool_use blocks
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input) # runs through the gate
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,                   # links result to the request
                    "content": json.dumps(result),             # results must be strings
                    # Flag errors so Claude knows the call failed and can adapt.
                    "is_error": "error" in result,
                })

        # Tool results go back as a USER message; then the loop calls Claude again.
        messages.append({"role": "user", "content": tool_results})

    return "Stopped: max turns reached."


if __name__ == "__main__":
    print(run_agent("Hi, I'm alice@example.com. Please refund my order A1001."))