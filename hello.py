import anthropic
client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-5-5",
    max_tokens=300,
    system="You are a concise assistant for software engineers.",
    messages=[
        {"role": "user", "content": "Explain CUDA warp in two sentences? "}
    ]   
)

print (next(b.text for b in response.content if b.type == "text"))
print ("stop_reason:", response.stop_reason)
print("input_tokens:", response.usage.input_tokens)
print("output_tokens:", response.usage.output_tokens)
