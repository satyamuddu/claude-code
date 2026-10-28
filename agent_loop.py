import anthropic
import json
client = anthropic.Anthropic()
tools = [
   {
  "name": "calculator",
  "description": "Performs basic arithmetic operations (addition, subtraction, multiplication, division, exponentiation) on two numbers.",
  "input_schema": {
    "type": "object",
    "properties": {
      "operation": {
        "type": "string",
        "enum": ["add", "subtract", "multiply", "divide", "power"],
        "description": "The arithmetic operation to perform."
      },
      "x": {
        "type": "number",
        "description": "The primary number or left operand."
      },
      "y": {
        "type": "number",
        "description": "The secondary number or right operand."
      }
    },
    "required": ["operation", "x", "y"]
  }
},
{
  "name": "web_search",
  "description": "Searches the live web for real-time information, news, current events, and documentation. Use this whenever you need factual data that may have changed or occurred after your knowledge cutoff.",
  "input_schema": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "The precise search query string optimized for a search engine."
      },
      "num_results": {
        "type": "integer",
        "description": "The maximum number of search results to return (default is 5, max is 10).",
        "default": 5
      }
    },
    "required": ["query"]
  }
}
]

print("Tools defined:", [t["name"] for t in tools])


def run_calculator(operation: str, x: float, y: float) -> str:
    try:
        if operation == "add":
            return str(x + y)
        elif operation == "subtract":
            return str(x - y)
        elif operation == "multiply":
            return str(x * y)
        elif operation == "divide":
            return "Error: Division by zero" if y == 0 else str(x / y)
        elif operation == "power":
            return str(x ** y)
        return f"Error: Unknown operation {operation}"
    except Exception as e:
        return f"Error: {str(e)}"

# 2. Function to execute the web search against a search provider API
def run_web_search(query: str, num_results: int = 5) -> str:
    try:
        # Example using a hypothetical search API or tool provider
        # response = httpx.get("https://api.searchprovider.com/search", params={"q": query, "num": num_results})
        # results = response.json()
        
        # Mock implementation output format

        #return f"Found {num_results} results for '{query}':\n1. [Example Title](https://example.com) - Snippet of real-time info..."
        return json.dumps({
            "query": query,
            "num_results": num_results,
            "results": [
                {
                    "title": "Example Title",
                    "url": "https://example.com",
                    "snippet": "Snippet of real-time info..."
                }
            ]
        })
    
    except Exception as e:
        return f"Error executing search: {str(e)}"

def execute_tool(name, tool_input):
    if name == "calculator":
        return str(run_calculator(**tool_input))
    if name == "web_search":
        return run_web_search(**tool_input)
    return f"Error: unknown tool {name}"

def run_agent_loop(user_prompt):
    messages = [{"role": "user", "content": user_prompt}]
    print("User prompt:", user_prompt)
      
    while True:
        # Here you would add the logic to select and run the appropriate tool based on the user prompt.
        response = client.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=1024,
            messages=messages,
            tools=tools
        )

        if response.stop_reason == "end_turn":
            print("End turn reached.")
            break

        if response.stop_reason == "tool_use":
            print ("Tool use requested.", response.content)
            break

    print("Agent loop exited.") 

if __name__ == "__main__":
    initial_prompt = "What is 5 multiplied by 10 "
    print("Initial prompt was:", initial_prompt)
    run_agent_loop(initial_prompt)
    
    print("Tools available:", [t["name"] for t in tools])
    print("Agent loop has finished execution.")

