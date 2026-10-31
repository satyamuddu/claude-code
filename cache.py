import anthropic

client = anthropic.Anthropic()
MODEL = "claude-haiku-5-5"

# A large, stable "document" (repeated text, just to exceed the minimum size)
doc = ("CUDA programming notes: warps execute 32 threads in lockstep; "
       "shared memory is split into banks; coalesced access matters. ") * 400

system_blocks = [
    {"type": "text", "text": "You answer questions about the notes below."},
    {
        "type": "text",
        "text": doc,
        "cache_control": {"type": "ephemeral"},   # breakpoint: cache everything up to here
    },
]

# Free token count before spending anything
count = client.messages.count_tokens(
    model=MODEL,
    system=system_blocks,
    messages=[{"role": "user", "content": "What is a warp?"}],
)
print("prompt tokens:", count.input_tokens)

def ask(question):
    r = client.messages.create(
        model=MODEL,
        max_tokens=100,
        system=system_blocks,
        messages=[{"role": "user", "content": question}],
    )
    u = r.usage
    print(f"input={u.input_tokens}  cache_write={u.cache_creation_input_tokens}  "
          f"cache_read={u.cache_read_input_tokens}  output={u.output_tokens}")

ask("What is a warp?")                   # expect: cache_write > 0
ask("What causes bank conflicts?")       # expect: cache_read > 0, cache_write = 0