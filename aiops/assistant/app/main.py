"""aiops-assistant — AI 驱动的智能运维助手
=========================================
功能：
  1. 日志智能分析  : 拉取 Loki/应用日志 → LLM 归纳异常与根因
  2. 告警根因定位  : Alertmanager webhook → 关联指标+日志 → LLM 推根因与处置建议
  3. RAG 知识库    : 检索运维知识(常见故障/架构文档)辅助回答，降低幻觉

设计：
  - LLM 可插拔：OpenAI / DeepSeek / 本地 Ollama，统一走 OpenAI SDK 兼容接口。
  - 上下文收集器 ContextCollector 对接真实集群(Loki/Prometheus/kubectl)，
    让「AI 的答案有据可依」。
"""
import os
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request
from pydantic import BaseModel

from .llm import LLMClient
from .context import ContextCollector

app = FastAPI(title="AIOps Assistant", version="0.1.0")

llm = LLMClient()
ctx = ContextCollector()


class AlertPayload(BaseModel):
    status: str
    alerts: list = []
    groupLabels: dict = {}
    commonAnnotations: dict = {}
    # kube-prometheus webhook 会带 alertname / annotations / labels 等


class Question(BaseModel):
    question: str
    namespace: str = "app"
    time_window: str = "15m"


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/api/alert")
async def on_alert(payload: AlertPayload, request: Request):
    """Alertmanager 告警 webhook 入口 → 触发 AI 根因分析。"""
    uid = os.urandom(4).hex()
    alerts = payload.alerts or []
    # 注意：Alertmanager webhook 的 status 在顶层(payload.status)，
    # 每个 alert 内部没有 status 字段（alert 只有 labels/annotations/startsAt 等）
    payload_status = getattr(payload, "status", "firing")
    if payload_status == "resolved":
        # 故障恢复：发恢复通知（不调用 LLM，直接告知）
        resolved_alerts = []
        for a in alerts:
            name = (a.get("labels") or {}).get("alertname", "unknown")
            summary = (a.get("annotations") or {}).get("summary", "")
            resolved_alerts.append((name, summary))
        try:
            from .notify import notify_resolved
            for name, summary in resolved_alerts:
                notify_resolved(name, summary)
        except Exception as e:  # noqa
            print(f"[notify-resolved] 异常: {e}", flush=True)
        return {"uid": uid, "action": "resolved-notified", "alerts": [n for n, _ in resolved_alerts]}
    if payload_status != "firing":
        return {"uid": uid, "action": "ignored", "reason": f"payload status={payload_status}"}
    if not alerts:
        return {"uid": uid, "action": "no-alerts"}

    alert = alerts[0]
    alert_name = (alert.get("labels") or {}).get("alertname", "unknown")
    namespace = (alert.get("labels") or {}).get("namespace", "app")
    annotations = alert.get("annotations") or {}
    summary = annotations.get("summary", alert_name)

    # 1) 收集上下文（指标 + 日志 + 集群状态）
    snapshot = ctx.collect_for_alert(namespace=namespace, alert_name=alert_name)
    # 2) 组装 prompt
    user_prompt = f"""请作为资深 SRE 分析这个告警。
告警: {summary}
命名空间: {namespace}
集群上下文快照:
{snapshot[:4000]}

请给出: 1)最可能的根因 2)处置步骤 3)如何验证恢复。回答要具体、可执行、控制在300字内。"""
    diagnosis = llm.ask(user_prompt)

    # 3) 打印完整分析结果到日志（kubectl logs 可查看，方便人工/演示）
    print(f"\n===== AIOps ALERT ANALYSIS [{uid}] =====", flush=True)
    print(f"alert: {alert_name}", flush=True)
    print(f"namespace: {namespace}", flush=True)
    print(f"summary: {summary}", flush=True)
    print(f"--- diagnosis ---\n{diagnosis}", flush=True)
    print("===== END ANALYSIS =====", flush=True)

    # 4) 多渠道通知（钉钉/企业微信/邮件，未配置的自动跳过）
    try:
        from .notify import notify_all
        notify_all(alert_name, summary, diagnosis)
    except Exception as e:  # noqa
        print(f"[notify] 通知发送异常: {e}", flush=True)

    return {
        "uid": uid,
        "alert": alert_name,
        "diagnosis": diagnosis,
        "collected": True,
    }


@app.post("/api/analyze-log")
async def analyze_log(req: Question):
    """手动/定时: 分析某命名空间近段时间的日志，找异常。"""
    logs = ctx.fetch_logs(namespace=req.namespace, since=req.time_window)
    if not logs:
        return {"logs_found": 0, "answer": "近段时间未采集到日志（确认 Loki/promtail 已部署）。"}
    sample = "\n".join(logs[-200:])   # 取最近 200 行，转成字符串
    answer = llm.ask(
        "你是 SRE 日志分析助手。以下是近期日志片段，请提炼异常、看是否存在错误/重启/超时，"
        "并给出建议。不要臆测未出现的信息。\n---\n" + sample
    )
    return {"logs_found": len(logs), "sample": logs[-15:], "answer": answer}


@app.post("/api/ask")
async def ask(req: Question):
    """通用问答：结合 RAG 知识库回答运维问题。"""
    from .rag import rag_search
    hits = rag_search(req.question, top_k=3)
    context = "\n".join(f"[{h['source']}] {h['text'][:500]}" for h in hits)
    prompt = (
        "你是一位云原生运维专家。请基于以下知识库资料回答。若资料不足，明确说明。\n\n"
        f"知识库:\n{context if context else '(空)'}\n\n问题: {req.question}"
    )
    return {"answer": llm.ask(prompt), "sources": [h["source"] for h in hits]}
