# Personal Finance Analysis API

A FastAPI application that answers questions about a user's financial
transactions. It uses an LLM-based input guardrail, a financial analysis agent
with Pandas and chart tools, an output guardrail, and optional Langfuse tracing.

## Requirements

- Python 3.11
- An Open Router provider API key and model access
- The source Excel transaction workbook
- Optional: a Langfuse project and its API keys

## Setup

Run these commands from the project root in PowerShell:

```powershell
python3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .\sample.env .\.env
```

Open `.env` in an editor and fill in the required values. Do not commit `.env`
or share its API keys.

| Variable | Required | Purpose |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes for the configured OpenRouter models | API key used by the guardrail LLM requests. |
| `GUARDRAIL_MODEL` | Yes | LiteLLM model name for the input/output guardrails and response rewriter. |
| `BASE_MODEL` | Yes | LiteLLM model name for the financial agent. |
| `SOURCE_FILE_PATH` | Yes | Path to the Excel workbook. Relative paths are resolved from the project root when starting the API there. |
| `APP_NAME` | No | FastAPI/ADK application name and Langfuse trace name. |
| `AGENT_NAME` | No | ADK agent name and agent observation/generation label. |
| `FALLBACK_MODEL` | No | Optional fallback model used by the guardrail completion client. |
| `MAX_GAURDRAILS_TOKENS` | No | Token limit passed to the financial agent and guardrail completion calls; defaults to `50000`. The response rewriter has a separate `4000` token limit. |
| `MAX_RETRIES` | No | Number of retries for guardrail and response-rewriter LLM requests; defaults to `1`. |
| `LAST_N` | No | Maximum number of recent interactions kept in the in-memory conversation history; defaults to `10`. |
| `LANGFUSE_PUBLIC_KEY` | No | Enables Langfuse tracing when set together with the secret key. |
| `LANGFUSE_SECRET_KEY` | No | Enables Langfuse tracing when set together with the public key. |
| `LANGFUSE_BASE_URL` | No | Langfuse host for your region or self-hosted instance. |

Use the model identifiers and provider credentials appropriate for your
LiteLLM configuration. For example, an OpenRouter model identifier typically
uses the `openrouter/` prefix. Do not put keys in source code.

`sample.env` is a template, not a complete working configuration. The workbook
must contain the transaction columns used by the application: `user_id`,
`user_name`, `transaction_date`, `transaction_amount`, `merchant_name`, and
`transaction_category_detail`.

## Run the API

Start the development server from the project root:

```powershell
python -m uvicorn src.app.main:app
```

The API is available at `http://127.0.0.1:8000`.

- Interactive Swagger UI: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

The workbook is loaded when the application starts. If `SOURCE_FILE_PATH` is
missing or the workbook cannot be read, startup fails.

## Call the chat endpoint

Send a `POST` request to `/chat` with a user ID and a question. Example for
PowerShell:

```powershell
$body = @{
    user_id = "user-id-from-your-workbook"
    prompt = "How much did I spend by category last month?"
} | ConvertTo-Json

Invoke-RestMethod `
    -Uri "http://127.0.0.1:8000/chat" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

Equivalent JSON request:

```json
{
  "user_id": "user-id-from-your-workbook",
  "prompt": "How much did I spend by category last month?"
}
```

The response contains:

| Field | Description |
|---|---|
| `response` | The rewritten, user-facing answer, after output-guardrail validation. |
| `data_summary` | The user's transaction profile summary. |
| `visualizations` | Relative paths to chart images generated during this request. |
| `cache_hit` | Whether the user's profile was already cached in this process. |
| `latency_ms` | Pipeline latency in milliseconds. |
| `guardrail_flags` | Input/output guardrail flags, if any. |

The API returns `404` if the user ID has no matching transactions and `500`
for unexpected processing errors. Conversation history and user profiles are
kept in memory; they are not persisted across server restarts.

## View generated charts

When useful for the question, the agent can generate charts with the
visualization tools. Chart PNG files are saved under:

```text
output/visualizations/
```

The response's `visualizations` array lists the relative path or paths, for
example:

```json
{
  "visualizations": [
    "output/visualizations/monthly_spending_a1b2c3d4.png"
  ]
}
```

From the project root, open the returned file in an image viewer or In
PowerShell, for example:

```powershell
Invoke-Item ".\output\visualizations\monthly_spending_a1b2c3d4.png"
```

The API currently returns paths on the server's filesystem; it does not expose
a public HTTP route for downloading or viewing chart images. If the API is
running on another machine, access the image on that server or add an
authenticated static-file/download route before expecting a remote client to
open the returned path. Generated PNGs are ignored by Git.

The agent may also reuse a previous chart path in its response text when
relevant. The `visualizations` array currently lists only charts generated
during the current request; a reused path is not automatically added to that
array.

## Conversation context

Recent questions, answers, and chart paths are cached per user in process
memory. Follow-up prompts can refer to an earlier question or chart, for
example, "show that as a bar chart." The cache contains prior answers and
visualization paths, not the underlying calculation tables; changed metrics,
date ranges, or groupings are recomputed from the transaction data. Set
`LAST_N` to change how many recent interactions are retained.

## Pandas analysis execution

The Pandas tool receives the current user's transaction data as `user_df` and
has Pandas available as `pd`; generated code must not import modules. Execution
allows only a limited set of built-ins: `abs`, `all`, `any`, `bool`, `dict`,
`enumerate`, `float`, `int`, `len`, `list`, `max`, `min`, `range`, `round`,
`sorted`, `str`, `sum`, `tuple`, and `zip`. In particular, `print`, `open`,
`eval`, and `exec` are unavailable inside generated analysis code.

Generated code must put its final JSON-compatible result in a variable named
`result`. Printed output is not captured or used as the analysis result. The
executor returns either a normalized result or an error to the agent, which
may retry with corrected code.

## Response rewriting and guardrails

After the agent responds, a response-rewriter LLM call removes internal
reasoning and tool narration before the output guardrail evaluates the
user-facing answer. The rewriter is instructed to preserve facts, figures,
caveats, chart paths, and a user name already present in the draft without
adding or recalculating information. The output guardrail checks relevance and supported scope; a chart filename
containing the current user's name alone is not treated as evidence that
another user's private data was exposed.

## Langfuse tracing (optional)

Set both `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` to enable tracing.
Configure `LANGFUSE_BASE_URL` for your Langfuse region or self-hosted instance.
When credentials are absent, the API runs without Langfuse tracing.

Each `/chat` request is traced with the submitted request JSON as trace input
and the API response JSON as trace output. Child observations cover the input
guardrail, financial agent, Pandas code execution, response rewriter, and
output guardrail in that order; LiteLLM model generations are associated with
the trace. The agent draft and rewritten user-facing response are recorded
separately. The Pandas execution observation includes generated code and the
executor result, which may contain transaction-derived data. Each child
records its relevant input and result; raised exceptions are recorded with
their type and a redacted message. Guardrail validation failures that are
handled internally are marked as validation failures with their reason and
risk flags.

LLM traces may include user prompts, transaction-derived content, and model
responses. Use an appropriately secured Langfuse project and configure access
and retention policies for financial data.
