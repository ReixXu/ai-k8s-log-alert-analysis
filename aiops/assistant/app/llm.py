"""LLM 客户端 — 可插拔大模型调用。

通过 OpenAI SDK 兼容接口对接：
  - OpenAI / DeepSeek / 其他云端（设置 base_url）
  - 本地 Ollama（http://localhost:11434/v1）

环境变量:
  LLM_API_KEY, LLM_BASE_URL, LLM_MODEL
"""
import os
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

    def ask(self, prompt: str, temperature: float = 0.2, max_tokens: int = 1500):
        """发送单轮 prompt，返回文本。temperature 偏低减少发散/幻觉。"""
        try:
            resp = _client().chat.completions.create(
                model=self.model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            content = resp.choices[0].message.content
            if content is None or not content.strip():
                return "[LLM返回空内容] 模型未生成有效分析，请稍后重试或检查 prompt 长度。"
            return content.strip()
        except Exception as e:  # noqa
            # 容错：不因模型不可用而让整个 AIOps 崩溃
            return f"[LLM调用失败] {e}\n提示: 请检查 LLM_API_KEY / LLM_BASE_URL / 网络。"
