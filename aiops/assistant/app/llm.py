"""LLM 客户端 — 可插拔大模型调用。

通过 OpenAI SDK 兼容接口对接：
  - OpenAI / DeepSeek / 其他云端（设置 base_url）
  - 本地 Ollama（http://localhost:11434/v1）

环境变量:
  LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_MAX_TOKENS（可选，默认 4000）

兼容性说明（实际踩坑）：
  部分 DeepSeek 版本（如带推理能力的 flash/pro 系列）会把思考过程放在
  reasoning_content 字段，而 content 可能因为 max_tokens 被思考过程耗尽而为空。
  因此本客户端在 content 为空时会回退使用 reasoning_content，并打印诊断信息。
"""
import os
import json
from functools import lru_cache

from openai import OpenAI


@lru_cache
def _client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("LLM_API_KEY", "sk-local"),
        base_url=os.getenv("LLM_BASE_URL", "https://api.deepseek.com"),
    )


class LLMClient:
    def __init__(self):
        self.model = os.getenv("LLM_MODEL", "deepseek-v4-flash")
        # 推理类模型思考过程也消耗 token，默认给足额度避免 content 被截空
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "4000") or "4000")

    def ask(self, prompt: str, temperature: float = 0.2, max_tokens: int = None):
        """发送单轮 prompt，返回文本。temperature 偏低减少发散/幻觉。"""
        mt = max_tokens or self.max_tokens
        try:
            resp = _client().chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=mt,
                messages=[{"role": "user", "content": prompt}],
            )
            choice = resp.choices[0]
            msg = choice.message
            content = (msg.content or "").strip()
            reasoning = (getattr(msg, "reasoning_content", None) or "").strip()

            # 诊断信息（便于排查空返回问题）
            diag = {
                "finish_reason": getattr(choice, "finish_reason", None),
                "content_len": len(content),
                "reasoning_len": len(reasoning),
                "usage": str(getattr(resp, "usage", None)),
            }
            print(f"[llm] {json.dumps(diag, ensure_ascii=False)}", flush=True)

            if content:
                return content
            # content 为空但存在思考过程：回退（多为 max_tokens 被思考耗尽）
            if reasoning:
                return (
                    reasoning
                    + "\n\n[注] 模型思考过程较长，最终结论因 token 上限被截断，以上为推理内容。"
                )
            return (
                f"[LLM返回空内容] finish_reason={diag['finish_reason']} usage={diag['usage']}，"
                f"请检查 max_tokens（当前 {mt}）是否过小。"
            )
        except Exception as e:  # noqa
            # 容错：不因模型不可用而让整个 AIOps 崩溃
            return f"[LLM调用失败] {e}\n提示: 请检查 LLM_API_KEY / LLM_BASE_URL / 网络。"
