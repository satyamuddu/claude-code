import asyncio
import time
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AgentDefinition,
    AssistantMessage,
    ResultMessage,
    ToolUseBlock,
)


async def main():
    options = ClaudeAgentOptions(
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
                tools=["Read", "Glob", "Grep"],  # read-only, no web access
            ),
        },
    )

    async for message in query(
        prompt=(
            "How has solar panel efficiency changed over the last decade? "
            "Use the right subagent for public web information, and the right "
            "subagent for our internal notes in ./docs."
        ),
        options=options,
    ):

        start = time.perf_counter()
        elapsed = time.perf_counter() - start

        if isinstance(message, AssistantMessage):
            tool_blocks = [b for b in message.content if isinstance(b, ToolUseBlock)]
            agent_calls = [b for b in tool_blocks if b.name in ("Agent", "Task")]

            if agent_calls:
                print(f"[{elapsed:6.1f}s] {len(agent_calls)} Agent call(s) in ONE response")

            for block in tool_blocks:
                parent = getattr(message, "parent_tool_use_id", None)
                who = f"subagent {parent[-6:]}" if parent else "coordinator"
                print(f"[{elapsed:6.1f}s] {who}: {block.name} (id ...{block.id[-6:]})")

        elif isinstance(message, ResultMessage):
            print(f"[{elapsed:6.1f}s] DONE")
            print(message.result)


if __name__ == "__main__":
    asyncio.run(main())