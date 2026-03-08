# NewAPI Cursor BYOK Adapter

[English README](./README.en.md)

一个很小的转发工具，用来给 Cursor 的 BYOK 场景做格式转换。

## 这是什么

Cursor 的 BYOK 会把请求发到 `/v1/chat/completions`，但请求体实际更接近 Responses API 的格式。

问题在于：

- 请求路径是 Chat Completions：`/v1/chat/completions`
- 请求体更像 Responses API
- Cursor 期望返回值还是 Chat Completions 格式

这个项目就是处理中间这层转换。

## 使用方法

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

启动前修改 `.env`：

```env
UPSTREAM_BASE_URL=https://api.openai.com/v1/responses
UPSTREAM_API_KEY=sk-your-upstream-api-key
UPSTREAM_API_KEY_HEADER=authorization
RELAY_API_KEY=change-me-to-a-long-random-string
```

`UPSTREAM_BASE_URL` 现在直接配置为完整接口地址（endpoint），默认建议配置 `/v1/responses`。
如果你填的是 `/chat/completions`，项目也会自动在需要时映射到 `/responses`。

`UPSTREAM_API_KEY_HEADER` 支持两种：

- `authorization`（默认）：上游请求头为 `Authorization: Bearer <UPSTREAM_API_KEY>`
- `x-api-key`：上游请求头为 `x-api-key: <UPSTREAM_API_KEY>`

默认地址：

- 服务地址：`http://localhost:8082`
- 接口地址：`http://localhost:8082/v1/chat/completions`

在 Cursor BYOK 里填写：

- Base URL: `http://your-server:8082/v1`
- API Key: 你的 `RELAY_API_KEY`

## How it works

1. Cursor 把请求发到 `/v1/chat/completions`
2. 这个项目监听这个接口
3. 如果请求体看起来是 Responses API 风格，就转发到 `UPSTREAM_BASE_URL`（默认就是 `/v1/responses`）
4. 上游返回 Responses API 的结果后，这个项目再把响应转换成 Chat Completions 格式
5. 最终返回给 Cursor，让它继续按 Completions 的方式处理

流式响应也是同样的思路：接收 Responses 的 SSE 事件，再转换成 Chat Completions 的 chunk 格式返回。

## 说明

- 本项目部署时必须使用公网可访问地址，因为 Cursor BYOK 的请求链路是：用户请求 -> Cursor 服务器 -> 你设置的 Base URL 服务器 -> OpenAI 服务器
- 因此你配置给 Cursor 的 Base URL 必须能被公网访问
- 运行时必须有 `.env`

## License

MIT. See `LICENSE`.
