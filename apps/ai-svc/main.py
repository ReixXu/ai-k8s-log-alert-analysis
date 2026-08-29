"""
ai-svc — AI 推理业务服务 (FastAPI)
==================================
对外提供「智能运维助手」的模型推理 API。
本服务在生产环境调用 vLLM / 远端模型；本地开发可用 mock。
同时暴露 Prometheus 指标与结构化日志，供 AIOps 分析。

启动:  uvicorn main:app --host 0.0.0.0 --port 8000
"""
import json
import os
import time
import random

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    _HAS_PROM = True
except Exception:
    _HAS_PROM = False

app = FastAPI(title="AI Cloud-Native Ops - Inference API", version="1.0.0")

# ---------- 可配置项 ----------
MODEL_ENDPOINT = os.getenv("MODEL_ENDPOINT", "http://vllm-svc:8001/v1/completions")
USE_MOCK = os.getenv("USE_MOCK", "true").lower() == "true"
MOCK_LATENCY_MS = int(os.getenv("MOCK_LATENCY_MS", "50"))
FAIL_RATE = float(os.getenv("FAIL_RATE", "0"))  # 制造故障用：0~1 模拟错误率
# -----------------------------

# ---------- Prometheus 指标 ----------
if _HAS_PROM:
    REQS = Counter("ai_svc_requests_total", "Total requests", ["endpoint"])
    LATENCY = Histogram("ai_svc_request_duration_seconds",
                        "Request latency", ["endpoint"],
                        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5))
# -------------------------------------


class InferRequest(BaseModel):
    prompt: str
    max_tokens: int = 64
    temperature: float = 0.7


class InferResponse(BaseModel):
    id: str
    model: str
    choices: list
    latency_ms: float
    cached: bool = False


def _log(level: str, msg: str, **ctx):
    entry = {"ts": time.time(), "level": level, "service": "ai-svc", "msg": msg, **ctx}
    print(json.dumps(entry), flush=True)  # 结构化日志 → 交给 Loki/AIOps


def _mock_infer(prompt: str, max_tokens: int):
    """本地 mock：模拟一次模型调用，返回一段占位补全。"""
    time.sleep(MOCK_LATENCY_MS / 1000.0)
    filler = (" 根据您的请求，建议检查节点负载并核对最近一次部署变更。"
              * max(1, max_tokens // 20))[: max_tokens * 4]
    return [
        {
            "index": 0,
            "text": f"<mock-ans>{filler}</mock-ans>",
            "logprobs": None,
            "finish_reason": "length",
        }
    ]


async def _real_infer(prompt: str, max_tokens: int):
    import httpx
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            MODEL_ENDPOINT,
            json={"model": "default", "prompt": prompt, "max_tokens": max_tokens},
        )
        r.raise_for_status()
        data = r.json()
        return data.get("choices", [])


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    if _HAS_PROM:
        # 注意：必须返回纯文本（Prometheus 文本格式），不能用 JSONResponse，
        # 否则会被包成 JSON 字符串导致 Prometheus 解析失败 (expected valid start token)
        from fastapi import Response
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    return {"status": "prometheus disabled"}


@app.post("/v1/infer", response_model=InferResponse)
async def infer(req: InferRequest, request: Request):
    if _HAS_PROM:
        REQS.labels("/v1/infer").inc()
    if random.random() < FAIL_RATE:
        _log("error", "inference failed", prompt_prefix=req.prompt[:20], fail_rate=FAIL_RATE)
        if _HAS_PROM:
            REQS.labels("/v1/infer").inc()
        return JSONResponse(status_code=503, content={"error": "model overloaded"})

    start = time.time()
    try:
        choices = (_mock_infer(req.prompt, req.max_tokens)
                   if USE_MOCK else await _real_infer(req.prompt, req.max_tokens))
        latency = (time.time() - start) * 1000
        if _HAS_PROM:
            LATENCY.labels("/v1/infer").observe(time.time() - start)
        _log("info", "infer_ok", latency_ms=round(latency, 2))
        return InferResponse(
            id=f"chatcmpl-{int(time.time()*1000)}",
            model="ai-ops-1",
            choices=choices,
            latency_ms=round(latency, 2),
        )
    except Exception as e:  # noqa
        _log("error", "infer_exception", exc=str(e))
        return JSONResponse(status_code=500, content={"error": str(e)})
