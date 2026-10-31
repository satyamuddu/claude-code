import time
import anthropic
client = anthropic.Anthropic()

topics = ["CUDA warps", "RDMA queue pairs", "Linux cgroups"]

batch = client.messages.batches.create(
    requests=[{
        "custom_id": f"topic_{i}",
        "params": {
            "model": "claude-sonnet-5-5",
            "max_tokens": 100,
            "messages": [{"role": "user", "content": f"Explain {topic} in simple terms."}]
        }
    } for i, topic in enumerate(topics)
    ]
)

print("batch id:", batch.id, "| status:", batch.processing_status)

# Poll until finished (in production: a scheduled job, not a sleep loop)
while True:
    batch = client.messages.batches.retrieve(batch.id)
    if batch.processing_status == "ended":
        break;
    print ("still processing...", batch.request_counts)
    time.sleep(30)

for entry in client.messages.batches.results(batch.id):
    if entry.result.type == "succeeded":
        print(f"Entry {entry.custom_id}: {next(b.text for b in entry.result.message.content if b.type == 'text')}")
    else:
        print(f"Entry {entry.custom_id}: Failed.  ", entry.result.type)
