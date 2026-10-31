import random
import time
import anthropic

client = anthropic.Anthropic(max_retries=2, timeout=60.0)

RETRYABLE_STATUS = {429, 500,502,503,504,529}

def call_with_retry(max_attempts=4, **params):
    """App-level retry logic on the top of the SDK's own retries"""

    for attempt in range(1, max_attempts + 1):
        try:
            return client.messages.create(**params)
        except anthropic.APIConnectionError as e:
            err = f"connection problem: {e.__cause__}"
        except anthropic.APIStatusError as e:
            if e.status_code not in RETRYABLE_STATUS:
                raise
            err = f"HTTP {e.status_code}: {e.message}"
        if attempt == max_attempts:
            raise RuntimeError(f"Failed after {max_attempts} attempts: {err}")

        delay = (2**attempt - 1) + random.uniform(0,0.5)
        print(f"Retrying in {delay:.2f} seconds...")
        time.sleep(delay)

# Test 1: happy path
r = call_with_retry(
    model="claude-sonnet-5-5",
    max_tokens=100,
    messages=[{"role": "user", "content": "Say hello."}],
)
print(next(b.text for b in r.content if b.type == "text"))

# Test 2: non-retryable error. Bad model name should fail fast with a 404.
try:
    call_with_retry(
        model="claude-does-not-exist",
        max_tokens=100,
        messages=[{"role": "user", "content": "Hi"}],
    )
except anthropic.NotFoundError as e:
    print("Failed fast, as expected:", e.status_code)