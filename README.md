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
UPSTREAM_BASE_URL=https://api.openai.com/v1
UPSTREAM_API_KEY=sk-your-upstream-api-key
RELAY_API_KEY=change-me-to-a-long-random-string
```

默认地址：

- 服务地址：`http://localhost:8082`
- 接口地址：`http://localhost:8082/v1/chat/completions`

在 Cursor BYOK 里填写：

- Base URL: `http://your-server:8082/v1`
- API Key: 你的 `RELAY_API_KEY`

## How it works

1. Cursor 把请求发到 `/v1/chat/completions`
2. 这个项目监听这个接口
3. 如果请求体看起来是 Responses API 风格，就转发到你配置的 `UPSTREAM_BASE_URL/v1/responses`
4. 上游返回 Responses API 的结果后，这个项目再把响应转换成 Chat Completions 格式
5. 最终返回给 Cursor，让它继续按 Completions 的方式处理

流式响应也是同样的思路：接收 Responses 的 SSE 事件，再转换成 Chat Completions 的 chunk 格式返回。

## 说明

- 运行时必须有 `.env`

## License

MIT. See `LICENSE`.
