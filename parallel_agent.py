import asyncio
import sys
import time
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AgentDefinition,
    AssistantMessage,
    ResultMessage,
    ToolUseBlock,
)

PARALLEL_PROMPT = (
    "You coordinate research subagents. When subtasks are independent, "
    "spawn all of their subagents together by emitting multiple Agent tool "
    "calls in a single response."
)
SEQUENTIAL_PROMPT = (
    "You coordinate research subagents. Spawn one subagent per response, "
    "wait for its result, and only then spawn the next."
)

TASK = (
    "How has solar panel efficiency changed over the last decade? "
    "Get public web information and also summarise our internal notes in ./docs."
)


async def run(mode: str):
    options = ClaudeAgentOptions(
        system_prompt=PARALLEL_PROMPT if mode == "parallel" else SEQUENTIAL_PROMPT,
        allowed_tools=["Agent", "WebSearch", "WebFetch", "Read", "Glob", "Grep"],
        agents={
            "web_researcher": AgentDefinition(
                description="Researches a topic on the public web and returns findings.",
                prompt="You are a web research agent. Find reliable information and report it clearly.",
                tools=["WebSearch", "WebFetch"],
            ),
            "document_analyst": AgentDefinition(
                description="Analyses local documents in ./docs and reports what they say.",
                prompt="You are a document analysis agent. Read the local files and report their contents accurately.",
                tools=["Read", "Glob", "Grep"],
            ),
        },
    )

    start = time.perf_counter()
    spawn_responses = 0

    async for message in query(prompt=TASK, options=options):
        elapsed = time.perf_counter() - start

        if isinstance(message, AssistantMessage):
            blocks = [b for b in message.content if isinstance(b, ToolUseBlock)]
            agent_calls = [b for b in blocks if b.name in ("Agent", "Task")]
            if agent_calls and not getattr(message, "parent_tool_use_id", None):
                spawn_responses += 1
                print(f"[{elapsed:6.1f}s] coordinator response #{spawn_responses}: "
                      f"{len(agent_calls)} Agent call(s)")

        elif isinstance(message, ResultMessage):
            print(f"[{elapsed:6.1f}s] DONE ({mode}), "
                  f"{spawn_responses} spawning response(s)")


if __name__ == "__main__":
    asyncio.run(run(sys.argv[1] if len(sys.argv) > 1 else "parallel"))