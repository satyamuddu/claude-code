import json
import re
import anthropic
from pydantic import BaseModel, Field, ValidationError
from typing import Literal

client = anthropic.Anthropic()
MODEL = "claude-haiku-5-5"

class Ticket(BaseModel):
    category: Literal["bug", "feature_request", "question"]
    priority: int  = Field(ge=1, le=5)
    summary: str = Field(max_length=100)

TEXT = "App crashes everytime I upload a PDF over 50MB. Blocking our whole team!"
#TEXT="Thanks!"
# ---------- Approach A: prompt for JSON, parse defensively, validate, retry ----------
def extract_json(raw: str) -> dict:
    """Defensive parsing: strip code fences, grab the outermost {...}."""
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object found")
    return json.loads(raw[start:end + 1])

def approach_a(max_attempts=3) -> Ticket:
    messages = [{"role": "user", "content":
        f"Classify this support message.\n<message>{TEXT}</message>\n"
        'Reply with ONLY JSON: {"category": "bug|feature_request|question", '
        '"priority": 1-5, "summary": "<=100 chars"}'}]
    for attempt in range(1, max_attempts + 1):
        r = client.messages.create(model=MODEL, max_tokens=300, messages=messages)
        raw = next(b.text for b in r.content if b.type == "text")
        try:
            return Ticket(**extract_json(raw))
        except (ValueError, ValidationError) as e:
            print(f"[A attempt {attempt}] invalid: {e}")
            # feed the error back so the model can self-correct
            messages += [
                {"role": "assistant", "content": raw},
                {"role": "user", "content": f"That was invalid: {e}. Return corrected JSON only."},
            ]
    raise RuntimeError("could not get valid output")

# ---------- Approach B: force a tool call whose schema is the output schema ----------
def approach_b() -> Ticket:
    tool = {
        "name": "record_ticket",
        "description": "Record a classified support ticket.",
        "input_schema": Ticket.model_json_schema(),
    }
    r = client.messages.create(
        model=MODEL, max_tokens=300,
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_ticket"},
        messages=[{"role": "user", "content": f"Classify:\n<message>{TEXT}</message>"}],
    )
    block = next(b for b in r.content if b.type == "tool_use")
    return Ticket(**block.input)   # still validate!

print("A:", approach_a())
print("B:", approach_b())