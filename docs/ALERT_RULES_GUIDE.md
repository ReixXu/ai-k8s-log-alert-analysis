# 告警规则扩展指南（如何添加新告警规则）

> 本项目使用 kube-prometheus-stack（Prometheus Operator），告警规则通过 **PrometheusRule CRD** 管理。
> 本文说明：现有规则在哪、如何添加新规则、如何验证、常见指标参考。

---

## 一、当前告警规则文件

| 文件 | 内容 |
|------|------|
| `monitoring/ai-svc-alerts.yaml` | 业务告警（AiSvcPodRestarting / AiSvcErrorRateHigh / AiSvcP99LatencyHigh / AiSvcDown / AiSvcGone / NodeMemoryPressure）|
| kube-prometheus-stack 内置 | 集群级告警（KubeProxy/etcd/scheduler 等，chart 自带，无需管理）|

## 二、添加新告警规则的步骤（3 步）

### 第 1 步：编辑规则文件

在 `monitoring/ai-svc-alerts.yaml` 的 `spec.groups[].rules` 下追加规则：

```yaml
spec:
  groups:
    - name: ai-svc.rules
      rules:
        # ... 现有规则 ...

        # 新规则示例：Pod CPU 使用率过高
        - alert: AiSvcPodCPUHigh
          expr: |
            sum by (pod) (rate(container_cpu_usage_seconds_total{namespace="app"}[5m])) * 100 > 80
          for: 5m
          labels:
            severity: warning
            service: ai-svc
          annotations:
            summary: "ai-svc Pod CPU 使用率超过 80%"
            description: "Pod {{ $labels.pod }} CPU 使用率超过 80% 持续 5 分钟"
```

### 第 2 步：应用并验证

```bash
# 应用规则
kubectl apply -f monitoring/ai-svc-alerts.yaml

# 验证 Prometheus 已加载（应看到新规则名）
curl -s http://10.1.171.25:9090/api/v1/rules | jq '.data.groups[] | select(.name=="ai-svc.rules") | .rules[].name'
```

### 第 3 步：验证告警触发（可选）

```bash
# 查看告警状态
curl -s 'http://10.1.171.25:9090/api/v1/alerts' | jq '.data.alerts[] | select(.labels.alertname=="新规则名") | {state}'
```

---

## 三、告警规则要点（必读）

### 1. 规则结构

```yaml
- alert: <告警名>                    # 唯一名称
  expr: <PromQL 表达式>              # 触发条件（返回非 0 值即触发）
  for: 2m                            # 持续时间确认（防抖动，pending→firing）
  labels:                            # 附加标签（用于路由/分组）
    severity: warning|critical|info
    service: <服务名>
  annotations:                       # 告警内容（发送到通知）
    summary: "简述"
    description: "详情（可用 $labels.xxx 引用标签）"
```

### 2. `for` 字段的重要性

- 不加 `for`：条件满足**立即**告警 → 指标抖一下就误报
- 加 `for: 5m`：持续 5 分钟才告警 → 避免瞬时波动
- 机制说明：pending（等待确认）→ firing（正式触发）

### 3. `absent()` 的坑（本项目踩过）

- `up == 0`：只检测「目标存在但抓取失败」
- 目标**消失**（Pod 缩容/删除）：指标不产生，`up == 0` 不触发
- **必须加 `absent()` 规则**（本项目 AiSvcGone 就是这么来的）

### 4. 通知路由

- 新规则加 `labels.service` 或 `severity` 后，Alertmanager 按 matcher 路由
- 当前路由：`severity="critical"` → aiops-webhook（AI 分析 + 三渠道通知）
- 新增渠道/路由：改 `alertmanager-kube-prom-kube-prometheus-alertmanager` secret 里的 `alertmanager.yaml`

---

## 四、常用指标参考（kube-prometheus-stack 提供）

### 节点级（node-exporter）
| 指标 | 含义 |
|------|------|
| `node_cpu_seconds_total{mode="idle"}` | CPU 空闲时间 → 算使用率 |
| `node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes` | 内存可用率 |
| `node_filesystem_avail_bytes / node_filesystem_size_bytes` | 磁盘可用率 |
| `node_network_receive_bytes_total` | 网络接收流量 |

### 容器级（cAdvisor）
| 指标 | 含义 |
|------|------|
| `container_cpu_usage_seconds_total` | 容器 CPU 使用 |
| `container_memory_usage_bytes` | 容器内存使用 |
| `container_restart_count` | 容器重启次数 |

### 集群级（kube-state-metrics）
| 指标 | 含义 |
|------|------|
| `kube_pod_container_status_restarts_total` | Pod 容器重启次数 |
| `kube_deployment_status_replicas` | Deployment 副本数 |
| `kube_node_status_condition` | 节点状态条件 |
| `kube_pod_status_phase` | Pod 阶段（Pending/Running/Failed）|

### 业务级（ai-svc 自曝）
| 指标 | 含义 |
|------|------|
| `ai_svc_requests_total{endpoint="/v1/infer"}` | 推理请求计数 |
| `ai_svc_request_duration_seconds` | 推理延迟（histogram，可算 P99）|

### Prometheus 内置
| 指标 | 含义 |
|------|------|
| `up` | 抓取目标状态（1=正常 0=失败）|
| `absent()` | 指标是否存在（消失检测）|

---

## 五、告警规则推荐清单（可直接复制使用）

```yaml
# 节点磁盘将满
- alert: NodeDiskPressure
  expr: (1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100 > 85
  for: 5m
  labels: {severity: warning}
  annotations:
    summary: "节点 {{ $labels.instance }} 磁盘使用率超过 85%"

# Pod 重启频繁
- alert: PodRestarting
  expr: increase(kube_pod_container_status_restarts_total[15m]) > 3
  for: 5m
  labels: {severity: warning}
  annotations:
    summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} 频繁重启"

# 节点不可达
- alert: NodeNotReady
  expr: kube_node_status_condition{condition="Ready", status="true"} == 0
  for: 5m
  labels: {severity: critical}
  annotations:
    summary: "节点 {{ $labels.node }} 不可用"
```

---

## 六、完整告警链路回顾

```
Prometheus 评估规则(PrometheusRule CRD)
   │ 条件满足 + for 持续
   ▼
Alertmanager（路由/分组/去重/抑制）
   │ 匹配 severity=critical（或按需放宽到 warning）
   ▼
AIOps 助手（LLM 分析 + 集群上下文）
   │
   ├→ 钉钉 / 企业微信 / 邮件（告警 + AI 分析）
   └→ 恢复时：resolved 通知（✅ 已恢复）
```

---

## 七、告警覆盖范围与 AI 分析路由

### 7.1 哪些告警会走 AI 分析

决定权在 **Alertmanager 的 route matcher**（当前为 `severity = "critical"`）：

| 告警来源 | 示例 | severity | 是否走 AI 分析 |
|---------|------|---------|--------------|
| 本项目规则 | AiSvcGone / AiSvcDown | critical | ✅ 是 |
| 集群组件规则 | etcdInsufficientMembers / TargetDown | critical | ✅ 是 |
| 工作负载规则 | KubePodCrashLooping / KubePodNotReady | **warning** | ❌ 否（受路由限制）|
| 资源配额规则 | KubeQuotaExceeded / CPUThrottlingHigh | warning/info | ❌ 否 |
| 节点规则 | NodeDown / NodeMemoryPressure | critical/warning | 视级别而定 |

### 7.2 kube-prometheus-stack 自带的工作负载规则（跨命名空间）

这些规则基于 kube-state-metrics，**作用于所有命名空间**，开箱即用（无需自己编写）：

```
KubePodCrashLooping              Pod 崩溃重启循环
KubePodNotReady                  Pod 长时间未就绪
KubeDeploymentReplicasMismatch   Deployment 副本数与期望不符
KubeDeploymentRolloutStuck       发布卡住
KubeStatefulSetReplicasMismatch  StatefulSet 副本异常
KubeDaemonSetRolloutStuck        DaemonSet 发布卡住
KubeDaemonSetNotScheduled        DaemonSet 未调度
KubeContainerWaiting             容器长时间 Waiting
KubeJobFailed / KubeJobNotCompleted  Job 失败/超时
KubeHpaReplicasMismatch          HPA 副本异常
KubeHpaMaxedOut                  HPA 已达上限
KubePdbNotEnoughHealthyPods      PDB 健康 Pod 不足
KubeCPUOvercommit / KubeMemoryOvercommit  资源超卖
KubeQuotaExceeded / KubeQuotaAlmostFull   配额超限/接近上限
CPUThrottlingHigh                CPU 被限流
```

查询当前集群实际加载的规则：
```bash
# 列出所有规则组及数量
curl -s http://<PROM_IP>:9090/api/v1/rules | jq -r '.data.groups[] | "\(.name) (\(.rules|length) rules)"'

# 查看工作负载类规则及其级别
curl -s http://<PROM_IP>:9090/api/v1/rules | jq -r '.data.groups[] | select(.name|test("kubernetes-apps|kubernetes-resources")) | .rules[] | "\(.name) [\(.labels.severity)]"'
```

### 7.3 让 warning 级告警也走 AI 分析（分级路由）

若希望所有命名空间的资源异常都由 AI 分析，将 Alertmanager 路由改为分级策略（critical 快速分析 + warning 聚合分析，避免告警风暴刷爆 LLM）：

编辑 Alertmanager 的 Secret（`alertmanager-kube-prom-kube-prometheus-alertmanager`）中 `alertmanager.yaml`：

```yaml
route:
  receiver: "null"
  group_by: [namespace]
  routes:
    # critical：立即分析（快速响应）
    - receiver: aiops-webhook
      matchers:
        - severity = "critical"
      group_wait: 10s
      group_interval: 30s
      repeat_interval: 2h
      continue: true
    # warning：聚合 5 分钟后分析（控制调用量）
    - receiver: aiops-webhook
      matchers:
        - severity = "warning"
      group_wait: 5m
      group_interval: 10m
      repeat_interval: 6h
      continue: true
    - receiver: "null"
      matchers:
        - alertname = "Watchdog"

receivers:
  - name: "null"
  - name: aiops-webhook
    webhook_configs:
      - send_resolved: true
        url: http://aiops-assistant.aiops/api/alert
```

应用方式：
```bash
kubectl get secret alertmanager-kube-prom-kube-prometheus-alertmanager -n monitoring \
  -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d > /tmp/am.yaml
vi /tmp/am.yaml
kubectl create secret generic alertmanager-kube-prom-kube-prometheus-alertmanager -n monitoring \
  --from-file=alertmanager.yaml=/tmp/am.yaml --dry-run=client -o yaml | kubectl apply -f -
kubectl delete pod -n monitoring alertmanager-kube-prom-kube-prometheus-alertmanager-0
```

> ⚠️ 权衡：warning 全量接入会增加 LLM 调用量与延迟。生产可按需只放行关键告警（如 `KubePodCrashLooping|KubePodNotReady|KubeQuotaExceeded`）。

### 7.4 AI 如何适配不同类型的告警

AIOps 助手的 `ContextCollector.collect_for_alert()` 会**按告警类型自动选择上下文**（无需为每条规则单独配置）：

| 告警类型判定 | 采集的上下文 |
|-------------|-------------|
| 节点类（Node*/Disk*/Kubelet*）| 节点状态、全集群非 Running Pod、全集群事件 |
| 控制平面类（etcd/scheduler/apiserver/proxy/TargetDown）| kube-system 组件状态、全集群事件、Endpoints |
| 业务类（其他，含任何命名空间）| 该命名空间的 Pod/事件/部署/非 Running Pod/日志 |
| 通用（所有告警）| 节点 CPU 与内存使用率 + 全集群异常 Pod 概况 |

因此**任意命名空间的业务告警**（monitoring / ingress-nginx / kube-system 等）都能被正确分析，namespace 取自告警标签而非写死。

