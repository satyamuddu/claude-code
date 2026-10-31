import asyncio
from claude_agent_sdk import ClaudeAgentOptions, query

async def main():
    async for message in query(
         prompt="List the .py files in this directory and describe each in one line.",
         options = ClaudeAgentOptions(
             allowed_tools=["Read", "Glob"], 
             max_turns=5
         )
    ):
        print(message)

if __name__ == "__main__":
    asyncio.run(main())
