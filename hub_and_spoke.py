"""
Hub-and-Spoke multi-agent system using the Anthropic Python SDK.

Setup:
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."
    python hub_and_spoke_claude.py

Optional:
    CLAUDE_MODEL=claude-sonnet-5-5   (default)
    FLAKY=1                          (first research tool call fails, to demo retry)

Architecture
------------
  User -> Coordinator -> { ResearchSubagent, DocumentSubagent, SynthesisSubagent }

  * Every subagent is a separate Claude call with its own system prompt.
  * Subagents never call or see each other. Only the Coordinator holds references.
  * Coordinator: decomposes (Claude + forced tool call), dispatches, logs every
    message, applies ONE retry policy, and decides what context each subagent gets.
"""

import json
import os
import sys
import time

import anthropic

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment


# ----------------------------------------------------------------------------
# Fake "world" data (stand-ins for a real search API and a real PDF parser)
# ----------------------------------------------------------------------------
INTERNAL_SALES_REPORT = """\
Skip Hire Co. - 2025 Sales Report (internal, confidential)
City        Jobs   Revenue(GBP)  Gross margin  Avg job value(GBP)
Leeds       4,100  1,004,500     22%           245
Sheffield   3,300    775,500     18%           235
Bradford    1,900    430,000     14%           226
Notes: Leeds launched 2019, Sheffield 2021. Bradford is struggling with fuel costs.
"""

_flaky_state = {"failed_once": False}


def lookup_competitor_prices(city: str) -> dict:
    """Simulated web lookup. Replace with a real search/scrape API."""
    if os.environ.get("FLAKY") == "1" and not _flaky_state["failed_once"]:
        _flaky_state["failed_once"] = True
        raise TimeoutError("competitor site timed out")
    return {
        "city": city,
        "competitors": [
            {"name": "SkipFast", "price_6yd_gbp": 285, "market_share_pct": 30},
            {"name": "BinThere", "price_6yd_gbp": 265, "market_share_pct": 22},
            {"name": "GrabAHire", "price_6yd_gbp": 255, "market_share_pct": 15},
            {"name": "Northern Skips", "price_6yd_gbp": 250, "market_share_pct": 12},
        ],
    }


RESEARCH_TOOLS = [
    {
        "name": "lookup_competitor_prices",
        "description": "Get skip hire competitors, their 6-yard skip prices and "
                       "market share for a given UK city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    }
]

TOOL_IMPL = {"lookup_competitor_prices": lookup_competitor_prices}


# ----------------------------------------------------------------------------
# Subagents (spokes). Each one only exposes run(instructions) -> str.
# ----------------------------------------------------------------------------
def _text(response) -> str:
    return "".join(b.text for b in response.content if b.type == "text").strip()


class ResearchSubagent:
    name = "research"
    system = (
        "You are a market research subagent for a skip hire company. Use your tool "
        "to gather competitor data, then reply with a SHORT factual summary "
        "(max 120 words): competitors, price range, who leads. No recommendations."
    )

    def run(self, instructions: str) -> str:
        messages = [{"role": "user", "content": instructions}]
        for _ in range(5):  # safety cap on tool loop
            resp = client.messages.create(
                model=MODEL, max_tokens=1024, system=self.system,
                tools=RESEARCH_TOOLS, messages=messages,
            )
            if resp.stop_reason != "tool_use":
                return _text(resp)
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    output = TOOL_IMPL[block.name](**block.input)  # may raise
                    results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(output),
                    })
            messages.append({"role": "user", "content": results})
        raise RuntimeError("research subagent exceeded tool-loop limit")


class DocumentSubagent:
    name = "documents"
    system = (
        "You are a document analysis subagent. You will be given a document and "
        "instructions. Extract only what is asked and reply with a SHORT factual "
        "summary (max 120 words). No recommendations."
    )

    def __init__(self, document: str):
        self._document = document  # injected by the coordinator at setup time

    def run(self, instructions: str) -> str:
        resp = client.messages.create(
            model=MODEL, max_tokens=600, system=self.system,
            messages=[{
                "role": "user",
                "content": f"<document>\n{self._document}\n</document>\n\n{instructions}",
            }],
        )
        return _text(resp)


class SynthesisSubagent:
    name = "synthesis"
    system = (
        "You are a synthesis subagent. Write a clear executive recommendation "
        "(max 200 words) using ONLY the findings provided. If caveats are listed, "
        "state them explicitly and lower your confidence accordingly."
    )

    def run(self, instructions: str) -> str:
        resp = client.messages.create(
            model=MODEL, max_tokens=800, system=self.system,
            messages=[{"role": "user", "content": instructions}],
        )
        return _text(resp)


# ----------------------------------------------------------------------------
# Coordinator (hub)
# ----------------------------------------------------------------------------
PLAN_TOOL = {
    "name": "create_plan",
    "description": "Decompose the user's request into subtasks for subagents.",
    "input_schema": {
        "type": "object",
        "properties": {
            "subtasks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "agent": {"type": "string", "enum": ["research", "documents"]},
                        "instructions": {
                            "type": "string",
                            "description": "Self-contained instructions for that subagent.",
                        },
                    },
                    "required": ["agent", "instructions"],
                },
            }
        },
        "required": ["subtasks"],
    },
}


class Coordinator:
    MAX_RETRIES = 1  # uniform policy for ALL subagents

    def __init__(self, subagents):
        self._agents = {a.name: a for a in subagents}  # only the hub holds this
        self.log: list[dict] = []

    # --- observability: single choke point for every message -----------------
    def _log(self, src, dst, kind, content):
        entry = {"n": len(self.log) + 1, "t": time.strftime("%H:%M:%S"),
                 "from": src, "to": dst, "kind": kind}
        self.log.append(entry)
        preview = content.replace("\n", " ")
        preview = preview[:140] + ("..." if len(preview) > 140 else "")
        print(f"[{entry['n']:02d} {entry['t']}] {src} -> {dst} ({kind}): {preview}")

    # --- consistent error handling: retry once, then report failure ---------
    def dispatch(self, agent_name: str, instructions: str):
        """Returns (ok, text_or_error)."""
        agent = self._agents[agent_name]
        last_error = ""
        for attempt in range(1, self.MAX_RETRIES + 2):
            self._log("coordinator", agent_name, f"task#{attempt}", instructions)
            try:
                result = agent.run(instructions)
                self._log(agent_name, "coordinator", "result", result)
                return True, result
            except (anthropic.APIError, TimeoutError, RuntimeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                self._log(agent_name, "coordinator", "ERROR", last_error)
                time.sleep(1)
        return False, last_error

    # --- decomposition: Claude plans, with a forced tool call for clean JSON -
    def plan(self, user_request: str) -> list[dict]:
        resp = client.messages.create(
            model=MODEL, max_tokens=800,
            system=(
                "You are the coordinator of a multi-agent team. Available subagents:\n"
                "- research: looks up competitors and local prices for a city.\n"
                "- documents: extracts figures from the company's internal sales report "
                "(it already has the report; just say what to extract).\n"
                "Create at most one subtask per agent. Instructions must be "
                "self-contained because subagents see nothing else. "
                "Always respond by calling the create_plan tool."
            ),
            tools=[PLAN_TOOL],
            tool_choice={"type": "auto"},
            messages=[{"role": "user", "content": user_request}],
        )
        plan = next(b.input for b in resp.content if b.type == "tool_use")["subtasks"]
        self._log("coordinator", "coordinator", "plan", json.dumps(plan))
        return plan

    # --- main workflow -------------------------------------------------------
    def handle(self, user_request: str) -> str:
        print(f"\n=== USER REQUEST: {user_request}\n")
        findings: dict[str, str] = {}
        caveats: list[str] = []

        for task in self.plan(user_request):
            ok, out = self.dispatch(task["agent"], task["instructions"])
            if ok:
                findings[task["agent"]] = out
            else:
                caveats.append(f"{task['agent']} subagent failed after retry ({out})")

        if "documents" not in findings:
            return "Cannot proceed: internal sales analysis unavailable."

        # Controlled information flow: the coordinator assembles synthesis input.
        # The raw user request and raw sales report are NOT forwarded.
        brief = ["Question: should we expand into Manchester?", ""]
        for agent, text in findings.items():
            brief += [f"## Findings from {agent} subagent", text, ""]
        if caveats:
            brief += ["## Caveats (data is incomplete)"] + [f"- {c}" for c in caveats]

        ok, report = self.dispatch("synthesis", "\n".join(brief))
        return report if ok else "Synthesis failed; findings: " + json.dumps(findings)


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first (export ANTHROPIC_API_KEY=sk-ant-...)")

    hub = Coordinator([
        ResearchSubagent(),
        DocumentSubagent(INTERNAL_SALES_REPORT),
        SynthesisSubagent(),
    ])
    answer = hub.handle(
        "Should we expand our skip hire business into Manchester? "
        "Use competitor pricing there and our results in comparable northern cities."
    )
    print("\n=== FINAL ANSWER ===\n" + answer)
    print(f"\n({len(hub.log)} messages logged through the coordinator)")