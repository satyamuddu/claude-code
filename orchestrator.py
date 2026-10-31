import anthropic

client = anthropic.Anthropic()
FAST, SMART = "claude-haiku-5-5", "claude-sonnet-5-5"

def worker(task: str) -> str:
    """Fresh context on every call. Returns a short summary, not a transcript."""
    r = client.messages.create(
        model=FAST, max_tokens=300,
        system="Answer in at most 3 sentences.",
        messages=[{"role": "user", "content": task}],
    )
    return next(b.text for b in r.content if b.type == "text")

def orchestrator(question: str) -> str:
    subtasks = ["Explain warp divergence.", "Explain memory coalescing.", "Explain occupancy."]
    findings = [worker(t) for t in subtasks]         # independent, so could run in parallel
    notes = "\n".join(f"<note>{f}</note>" for f in findings)
    r = client.messages.create(
        model=SMART, max_tokens=500,
        messages=[{"role": "user", "content":
                   f"Using only these notes, answer: {question}\n\n{notes}"}],
    )
    print("orchestrator input tokens:", r.usage.input_tokens)
    return next(b.text for b in r.content if b.type == "text")

print(orchestrator("What are the top three things that slow down a CUDA kernel?"))