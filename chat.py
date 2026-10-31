import anthropic

client = anthropic.Anthropic()

messages = []


def ask(prompt: str) -> str:
    request = messages + [{"role": "user", "content": prompt}]

    try:
        response = client.messages.create(
            model="claude-sonnet-5-5",
            max_tokens=1500,
            system="You are a concise assistant for software engineers.",
            messages=request,
        )
    except anthropic.APIError as e:
        print(f"API error: {e}")
        return ""

    text = next((b.text for b in response.content if b.type == "text"), "")
    if response.stop_reason == "max_tokens":
        print("Response truncated due to token limit.")

    # Commit the turn to history only after a successful response.
    messages.append({"role": "user", "content": prompt})
    messages.append({"role": "assistant", "content": text})
    print(f"[input tokens: {response.usage.input_tokens}, output tokens: {response.usage.output_tokens}]")
    return text


if __name__ == "__main__":
    print("first question:")
    print(ask("What is CUDA warp?"))
    print("second question:")
    print(ask("How does it work?"))
    print("third question:")    
    print(ask("What are the benefits of using warps?"))
