import anthropic
client = anthropic.Anthropic()

with client.messages.stream(
    model="claude-haiku-5-5",
    max_tokens=1024,
    messages=[{"role": "user", "content": "Explain shared memory bank conflicts in CUDA?"}]
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)

    final_response= stream.get_final_message()

print ("\n stop reason: ", final_response.stop_reason)
print("\n usage: ", final_response.usage)
