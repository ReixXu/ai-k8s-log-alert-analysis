"""ContextCollector — 从真实集群收集上下文，让 AI 的回答有据可依。

对接:
  - Loki: 日志 (如果部署了 Loki, 通过 HTTP API 查询)
  - Prometheus: 指标 (通过 PromQL API 查询)
  - kubectl: 集群状态 (Pod / Event/ 部署状态)

全部用环境变量控制开关，保证「没有这些组件也能跑」(返回提示文案)。
"""
import os
import subprocess
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta

LOKI_URL = os.getenv("LOKI_URL", "http://loki.monitoring:3100")
PROM_URL = os.getenv("PROM_URL", "http://prometheus.monitoring:9090")


class ContextCollector:
    # ---------- 日志 ----------
    def fetch_logs(self, namespace: str = "app", since: str = "15m", quiet: bool = True):
        """从 Loki 拉取一段时间日志，返回合并后的文本行。组件缺失时返回空。"""
        try:
            mins = int("".join(c for c in since if c.isdigit())) or 15
            end = datetime.utcnow()
            start = end - timedelta(minutes=mins)
            expr = f'{{namespace="{namespace}"}}'
            # Loki query_range 需要 start/end 时间戳（纳秒），否则查不到
            url = (
                f"{LOKI_URL}/loki/api/v1/query_range"
                f"?query={urllib.parse.quote(expr)}"
                f"&start={int(start.timestamp() * 1e9)}"
                f"&end={int(end.timestamp() * 1e9)}"
                f"&limit=50"
            )
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.load(r)
            lines = []
            for res in data.get("data", {}).get("result", []):
                for val in res.get("values", []):
                    lines.append(val[1])
            return lines
        except Exception:
            return [] if quiet else ["[info] Loki 不可用，未采集到日志"]

    # ---------- 指标 ----------
    def query_metric(self, expr: str):
        """对 Prometheus 跑一条 PromQL，返回数值列表。"""
        try:
            q = urllib.parse.quote(expr)
            with urllib.request.urlopen(
                f"{PROM_URL}/api/v1/query?query={q}", timeout=5
            ) as r:
                data = json.load(r)
            out = []
            for res in data.get("data", {}).get("result", []):
                out.append((res.get("metric", {}), res.get("value")))
            return out
        except Exception:
            return []

    # ---------- kubectl ----------
    def kubectl(self, args: list, max_lines: int = 20):
        try:
            out = subprocess.run(
                ["kubectl"] + args,
                capture_output=True, text=True, timeout=10,
            )
            text = out.stdout.strip() or out.stderr.strip()
            return "\n".join(text.splitlines()[:max_lines])
        except Exception:
            return "[kubectl 不可用(需在集群内运行本服务或配置 kubeconfig)]"

    # ---------- 汇总 ----------
    def collect_for_alert(self, namespace: str, alert_name: str) -> str:
        parts = []
        parts.append("## 节点 CPU 使用率\n" + str(self.query_metric(
            '100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')))
        parts.append("## 最近事件\n" + self.kubectl(
            ["get", "events", "-n", namespace, "--sort-by=.lastTimestamp"], 20))
        parts.append("## Pod 状态\n" + self.kubectl(["get", "pods", "-n", namespace], 25))
        parts.append("## 部署状态\n" + self.kubectl(["get", "deploy", "-n", namespace], 15))
        logs = self.fetch_logs(namespace)
        if logs:
            parts.append("## 日志片段(最近)\n" + "\n".join(logs[-50:]))
        return "\n\n".join(parts)
