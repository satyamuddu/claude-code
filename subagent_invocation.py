import asyncio
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
        # "Agent" is the tool the coordinator uses to spawn subagents
        # (called "Task" in older SDK versions and in the exam material).
        # WebSearch and WebFetch are pre-approved so the subagent can use them.
        allowed_tools=["Agent", "WebSearch", "WebFetch"],
        agents={
            "web_researcher": AgentDefinition(
                # description: what the coordinator reads to select this subagent
                description="Researches a topic on the web and returns findings.",
                # prompt: the subagent's system prompt (its instructions)
                prompt="You are a web research agent. Find reliable information and report it clearly.",
                # tools: the subagent's tool restrictions (scoped to its role)
                tools=["WebSearch", "WebFetch"],
            ),
        },
    )

    async for message in query(
        prompt=(
            "Use the web_researcher agent to find out how solar panel "
            "efficiency has changed over the last decade."
        ),
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    print(f"[tool call] {block.name}")
        elif isinstance(message, ResultMessage):
            print(message.result)
            print("Denials:", getattr(message, "permission_denials", None))


if __name__ == "__main__":
    asyncio.run(main())