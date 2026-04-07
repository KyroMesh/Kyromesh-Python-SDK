# Kyromesh Python SDK

The official Python SDK for [Kyromesh](https://kyromesh.com) — AI Runtime Infrastructure for production workloads.

## Installation

```bash
pip install kyromesh
```

## Quick Start

```python
from kyromesh import Kyromesh

# Initialize the client
kyro = Kyromesh(api_key="km_live_your_api_key_here")

# Submit an async job
job = kyro.run_job(
    task="summarize",
    input={"text": "Long document to summarize..."},
    guardrails=["pii", "injection"],
    routing_policy="cost"
)

print(f"Job submitted: {job.id}")

# Wait for completion
result = kyro.wait_for_job(job.id, timeout=300)
print(f"Result: {result.output}")
```

## Features

- **Async Job Execution**: Submit AI tasks and retrieve results asynchronously
- **Provider Routing**: Automatic selection of the best AI provider (OpenAI, AWS Bedrock, X.Grok)
- **Security Guardrails**: Built-in PII detection, prompt injection detection, and toxicity filtering
- **Batch Processing**: Submit multiple jobs efficiently
- **Usage Tracking**: Monitor your job usage and costs
- **Webhook Support**: Receive callbacks when jobs complete

## Documentation

For comprehensive documentation, visit [docs.kyromesh.com](https://docs.kyromesh.com)

## License

MIT
