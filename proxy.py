"""
DMS MCP 代理服务
解决扣子创建 MCP 插件时的 OAuth 发现问题
"""

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import uvicorn

# 阿里云 DMS MCP 服务地址
DMS_MCP_URL = "https://dms-mcper-jxwtx-ntfuwoaqpb.cn-hangzhou.fcapp.run/sse"

# 认证信息
AUTH_TOKEN = "Bearer DMS-f9872a54-3958-407c-9da2-44b77b4f7843-1776071534"

app = FastAPI()

# 处理 OAuth 发现请求 - 返回空响应让客户端继续
@app.get("/.well-known/oauth-authorization-server")
@app.get("/.well-known/oauth-authorization-server/sse")
async def oauth_discovery():
    return JSONResponse(
        status_code=404,
        content={"error": "OAuth not supported"}
    )

# SSE 连接 - 转发到阿里云 DMS
@app.get("/sse")
async def sse_proxy(request: Request):
    headers = {
        "Authorization": AUTH_TOKEN,
        "Accept": "text/event-stream",
        "Cache-Control": "no-cache",
    }
    
    # 转发 query 参数
    params = dict(request.query_params)
    
    async def stream():
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "GET",
                DMS_MCP_URL,
                headers=headers,
                params=params
            ) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk
    
    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

# POST 请求转发 - 用于 MCP message
@app.post("/message")
async def message_proxy(request: Request):
    headers = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json",
    }
    
    body = await request.body()
    params = dict(request.query_params)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            DMS_MCP_URL.replace("/sse", "/message"),
            headers=headers,
            content=body,
            params=params
        )
        return JSONResponse(
            content=response.json() if response.headers.get("content-type", "").startswith("application/json") else {"data": response.text},
            status_code=response.status_code
        )

# 健康检查
@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)