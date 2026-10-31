import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    params = StdioServerParameters(command="python", args=["mcp_server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()

            for t in tools.tools:
                print("TOOL:", t.name, "|", (t.description or "").strip()[:60])
                print("  schema:", t.input_schema)
            ok = await session.call_tool("get_order_status", {"order_id": "A100"})
            print("RESULT:", ok.content[0].text)

            bad = await session.call_tool("get_order_status", {"order_id": "A999"})
            print("RESULT:", bad.is_error, bad.content[0].text)

            res = await session.read_resource("orders://A200")
            print("RESOURCE:", res.contents[0].text)

            prompts = await session.list_prompts()
            print("PROMPTS:", [p.name for p in prompts.prompts])
        

if __name__ == "__main__":
    asyncio.run(main())
