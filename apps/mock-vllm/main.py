"""mock-vllm — 模拟 vLLM 推理服务。

无 GPU 时用此服务模拟真实的大模型推理端点，
让 ai-svc 的 MODEL_ENDPOINT 指向这里，从而跑通「推理链路」。
真实环境替换为 vLLM / TGI 即可。
"""
import time
from fastapi import FastAPI, Request
from pydantic import BaseModel

app = FastAPI(title="Mock vLLM")


class CompletionReq(BaseModel):
    model: str = "default"
    prompt: str = ""
    max_tokens: int = 64
    temperature: float = 0.7
    stream: bool = False


@app.get("/v1/models")
async def models():
    return {"object": "list", "data": [{"id": "default", "owned_by": "mock"}]}


@app.post("/v1/completions")
async def completions(req: CompletionReq):
    time.sleep(0.08)  # 模拟推理耗时
    text = (f"[模拟推理] 针对输入'{req.prompt[:30]}...'，"
            "运维建议：检查最近一次部署与节点负载。")
    return {
        "id": f"cmpl-{int(time.time()*1000)}",
        "object": "text_completion",
        "model": req.model,
        "choices": [{"index": 0, "text": text, "finish_reason": "stop"}],
    }
