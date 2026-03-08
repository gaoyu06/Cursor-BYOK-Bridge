# NewAPI Cursor BYOK Adapter

[中文说明](./README.md)

A very small relay for Cursor BYOK.

## What it is

Cursor BYOK sends requests to `/v1/chat/completions`, but the request body is often closer to the Responses API format.

That means:

- the path is Chat Completions: `/v1/chat/completions`
- the body looks like Responses API
- Cursor still expects a Chat Completions style response

This project handles that conversion layer.

## Usage

```bash
git clone https://github.com/your-username/newapi-cursor-byok-adapter.git
cd newapi-cursor-byok-adapter
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

Edit `.env` before starting:

```env
UPSTREAM_BASE_URL=https://api.openai.com/v1/responses
UPSTREAM_API_KEY=sk-your-upstream-api-key
UPSTREAM_API_KEY_HEADER=authorization
RELAY_API_KEY=change-me-to-a-long-random-string
```

`UPSTREAM_BASE_URL` is now a full endpoint URL, and `/v1/responses` is the recommended default.
If you set `/chat/completions`, the relay will map it to `/responses` when needed.

`UPSTREAM_API_KEY_HEADER` supports two modes:

- `authorization` (default): sends `Authorization: Bearer <UPSTREAM_API_KEY>`
- `x-api-key`: sends `x-api-key: <UPSTREAM_API_KEY>`

Default addresses:

- Service: `http://localhost:8082`
- Endpoint: `http://localhost:8082/v1/chat/completions`

In Cursor BYOK:

- Base URL: `http://your-server:8082/v1`
- API Key: your `RELAY_API_KEY`

## How it works

1. Cursor sends a request to `/v1/chat/completions`
2. This project listens on that endpoint
3. If the body looks like a Responses API payload, it forwards to `UPSTREAM_BASE_URL` (default `/v1/responses`)
4. When the upstream returns a Responses API result, this project converts it into Chat Completions format
5. The converted response is returned to Cursor

Streaming follows the same idea: Responses SSE events come in, Chat Completions chunks go out.

## Notes

- This is a small utility, not a highly configurable platform
- `.env` is required at runtime
- Do not commit `.env` to GitHub

## License

MIT. See `LICENSE`.
