# 本地 kube-prometheus-stack 部署 + 自定义 alert rules 参考

> ⚠️ **本目录文件分为两类，注意区分：**
>
> | 类型 | 文件 | 说明 |
> |------|------|------|
> | ✅ **实际生效** | `ai-svc-alerts.yaml`（PrometheusRule）<br>`ai-svc-servicemonitor.yaml`（ServiceMonitor）<br>`alertmanager-aiops-route.yaml`（AlertmanagerConfig）| 通过 kubectl apply 生效，集群正在使用 |
> | 📖 **仅作参考** | `prometheus.yml`、`alertmanager.yml`、`alert-rules.yml`（本文档）| 「手搭 Prometheus」路径的示例配置，**当前环境未使用**——实际由 kube-prometheus-stack（Helm + Operator）托管，抓取目标通过 ServiceMonitor 声明，规则通过 PrometheusRule 声明 |
>
> 排查问题时请以集群实际配置为准：
> ```bash
> kubectl get prometheusrule,servicemonitor,alertmanagerconfig -n monitoring
> kubectl get secret prometheus-kube-prom-kube-prometheus-prometheus -n monitoring \
>   -o jsonpath='{.data.prometheus\.yaml\.gz}' | base64 -d | gunzip | head -40
> ```

> 目的：快速搭出 Prometheus/Grafana/Alertmanager/Loki/cAdvisor/node-exporter 全家桶。
> 路径 A（推荐）：直接用 kube-prometheus-stack Helm chart。
> 路径 B：用本目录下配置文件手搭（适合讲原理）。

## 路径 A — kube-prometheus-stack (推荐，省时)

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# 安装全家桶（含 prometheus/grafana/alertmanager/kube-state-metrics/node-exporter）
helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.service.type=NodePort

# Loki 集群日志
helm repo add grafana https://grafana.github.io/helm-charts
helm upgrade --install loki grafana/loki-stack \
  --namespace monitoring \
  --set grafana.enabled=true,prometheus.enabled=false
```

## 采集业务服务 ai-svc 的指标

kube-prometheus-stack 使用 **ServiceMonitor** 而不是静默抓取：

```bash
cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: ai-svc
  namespace: monitoring
spec:
  namespaceSelector:
    matchNames: ["app"]
  selector:
    matchLabels:
      app: ai-svc
  endpoints:
    - port: http
      path: /metrics
EOF
```

## 自定义告警规则

把 `alert-rules.yml` 内容挂进 stack（建议做进 PrometheusRule CRD）：

```bash
cat <<EOF | kubectl apply -f -
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: ai-ops-rules
  namespace: monitoring
spec:
  groups:
    - name: app-alerts
      rules:
        - alert: AiSvcLatencyHigh
          expr: histogram_quantile(0.99, sum by(le) (rate(ai_svc_request_duration_seconds_bucket[5m]))) > 1
          for: 2m
          labels: {severity: warning}
          annotations:
            summary: "ai-svc P99 延迟超 1s"
EOF
```

## Alertmanager → AIOps

用 `alertmanager.yml` 里 webhook 指向 `aiops-assistant.aiops/api/alert`，
这样每个告警都会自动触发 P3 的 AI 智能分析。

## 验证
- `kubectl get pods -n monitoring`
- 端口转发 Grafana / Prometheus / Alertmanager 到本机浏览器查看
