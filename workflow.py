import anthropic

client = anthropic.Anthropic()
FAST, SMART = "claude-haiku-5-5", "claude-sonnet-5-5"

SYSTEM = {
    "billing":   "You are a billing support agent. Be brief and polite. Never promise refunds.",
    "technical": "You are a technical support agent. Ask for logs or steps to reproduce.",
    "other":     "You are a general support agent. Be brief and polite.",
}


def classify(text:str) -> str: # step 1: Haiku
    r = client.messages.create(
        model=FAST, max_tokens=300,
        system="Reply with exactly one word: billing, technical, or other.",
        messages=[{"role": "user", "content": f"<message>{text}</message>"}],
    
    )
    label = next(b.text for b in r.content if b.type == "text").strip().lower()
    return label if label in SYSTEM else "other"

def handle(text:str) -> str: # step 2: Sonnet
    label = classify(text)
    r = client.messages.create(
        model=SMART,
        system=SYSTEM[label],
        max_tokens=1000,
        messages=[{"role": "user", "content": f"<message>{text}</message>"}],
    )
    draft = next(b.text for b in r.content if b.type == "text").strip()
    if "refund" in draft.lower() and label == "billing":   # step 3: deterministic check in code
        draft += "\n\n(Flagged for human review: mentions refund.)"
    print(f"[route={label}]")
    return draft
print(handle("I was charged twice this month."))
print(handle("The export button throws a 500 error."))