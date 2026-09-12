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
        """按告警类型智能选择上下文，支持业务告警与集群级告警。

        - 业务告警（有 namespace）：收集该命名空间的 Pod/事件/部署/日志
        - 节点类告警（Node*/Disk*/Memory*）：收集节点状态与全集群异常 Pod
        - 控制平面类告警（etcd/scheduler/controller/apiserver/kubelet/proxy）：
          收集 kube-system 组件状态与全集群事件
        """
        parts = []
        aw = (alert_name or "").lower()

        # 1) 通用：节点资源（所有告警都看）
        parts.append("## 节点 CPU 使用率(%)\n" + str(self.query_metric(
            '100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100)')))
        parts.append("## 节点内存使用率(%)\n" + str(self.query_metric(
            '(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100')))

        # 2) 按告警类型选择上下文
        node_kw = ("node", "disk", "memorypressure", "disckpressure", "notready", "kubelet")
        cp_kw = ("etcd", "scheduler", "controller", "apiserver", "proxy", "coredns", "targetdown")

        if any(k in aw for k in node_kw):
            # 节点类告警：看节点状态 + 全集群异常 Pod
            parts.append("## 节点状态\n" + self.kubectl(["get", "nodes", "-o", "wide"], 10))
            parts.append("## 全集群非 Running Pod\n" + self.kubectl(
                ["get", "pods", "-A", "--field-selector=status.phase!=Running"], 25))
            parts.append("## 节点相关事件\n" + self.kubectl(
                ["get", "events", "-A", "--sort-by=.lastTimestamp"], 20))
        elif any(k in aw for k in cp_kw):
            # 控制平面类告警：看 kube-system 组件
            parts.append("## kube-system 组件状态\n" + self.kubectl(
                ["get", "pods", "-n", "kube-system", "-o", "wide"], 30))
            parts.append("## 全集群事件\n" + self.kubectl(
                ["get", "events", "-A", "--sort-by=.lastTimestamp"], 20))
            parts.append("## 服务端点(Endpoints)\n" + self.kubectl(["get", "endpoints", "-A"], 20))
        else:
            # 业务类告警（默认）：按命名空间收集
            parts.append("## 最近事件\n" + self.kubectl(
                ["get", "events", "-n", namespace, "--sort-by=.lastTimestamp"], 20))
            parts.append("## Pod 状态\n" + self.kubectl(["get", "pods", "-n", namespace, "-o", "wide"], 25))
            parts.append("## 部署状态\n" + self.kubectl(["get", "deploy", "-n", namespace], 15))
            parts.append("## 该命名空间非 Running Pod\n" + self.kubectl(
                ["get", "pods", "-n", namespace, "--field-selector=status.phase!=Running"], 15))
            logs = self.fetch_logs(namespace)
            if logs:
                parts.append("## 日志片段(最近)\n" + "\n".join(logs[-50:]))

        # 3) 兜底：全集群异常 Pod 概况（帮助 AI 发现关联影响）
        if not any(k in aw for k in node_kw):
            parts.append("## 全集群异常 Pod 概况\n" + self.kubectl(
                ["get", "pods", "-A", "--field-selector=status.phase!=Running"], 15))

        return "\n\n".join(parts)
