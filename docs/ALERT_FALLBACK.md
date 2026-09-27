# 告警兜底通道配置（避免 AI 挂掉导致告警静默）

## 一、问题：AI 被放进了告警「送达」路径

当前 Alertmanager 的路由只有**一个** receiver：

```yaml
routes:
  - receiver: aiops-webhook          # 唯一出口
    matchers:
      - severity = "critical"
```

**后果**：`aiops-assistant` 一旦挂掉或持续超时，**所有 critical 告警彻底静默**——值班人既收不到 AI 分析，也收不到原始告警。

这违背了一条基本原则：**AI 是增强手段，不应成为告警送达的单点**。AI 挂掉只应让「分析」消失，不应让「告警」消失。

## 二、修复思路：双通道扇出（AI 增强 + 直投兜底）

Alertmanager 中**一个 route 只能有一个 receiver**，要同时投递两路必须用「父路由 + `continue: true` 扇出」：

```
告警
 ├─ ① aiops-webhook   （AI 增强通道：分析 + 钉钉/企微/邮件）  ← 依赖 LLM
 └─ ② direct-email    （直投兜底通道：原始告警邮件）          ← 不依赖 AI、不依赖 LLM
```

- **critical**：两路都走（扇出）
- **warning**：只走直投（省 LLM 调用）

**两路内容互补而非重复**：AI 通道给「根因 + 处置建议」，直投通道给「告警名 + 摘要 + 时间」，便于对照。

## 三、最小实现（零新增组件，用 Alertmanager 原生 email）

Alertmanager 原生支持 SMTP，因此兜底通道**不需要额外的转发服务**。

### 3.1 给 Alertmanager 注入 SMTP 环境变量

Alertmanager 的配置支持 `${VAR}` 展开，凭据从现有 Secret `aiops-notify` 注入，避免明文写进配置：

```bash
kubectl patch alertmanager kube-prom-kube-prometheus-alertmanager -n monitoring --type=merge -p '{
  "spec": {
    "containers": [
      {
        "name": "alertmanager",
        "envFrom": [
          {"secretRef": {"name": "aiops-notify"}}
        ]
      }
    ]
  }
}'
```

> Secret `aiops-notify`（aiops 命名空间）已包含 `smtp_host` / `smtp_port` / `smtp_user` / `smtp_pass` / `mail_to`。
> 若 Alertmanager 与 Secret 不在同一命名空间，需先在 `monitoring` 命名空间建一份同名 Secret。

### 3.2 替换路由配置（Alertmanager 的 Secret）

```bash
kubectl get secret alertmanager-kube-prom-kube-prometheus-alertmanager -n monitoring \
  -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d > /tmp/am.yaml
vi /tmp/am.yaml     # 按下方内容调整 route 与 receivers
kubectl create secret generic alertmanager-kube-prom-kube-prometheus-alertmanager -n monitoring \
  --from-file=alertmanager.yaml=/tmp/am.yaml --dry-run=client -o yaml | kubectl apply -f -
kubectl delete pod -n monitoring alertmanager-kube-prom-kube-prometheus-alertmanager-0
```

目标配置：

```yaml
route:
  receiver: direct-email              # 兜底：无子路由匹配时也走直投
  group_by: [alertname, namespace, severity]
  group_wait: 5s
  group_interval: 30s
  repeat_interval: 4h
  routes:
    # ① AI 增强通道：只给 critical，粗聚合省 token
    - receiver: aiops-webhook
      matchers:
        - severity = "critical"
      continue: true                  # ★ 继续匹配，保证 critical 同时落到直投
      group_by: [alertname, namespace]
      group_wait: 10s
      group_interval: 1m
      repeat_interval: 2h
    # ② 直投兜底通道：不依赖 AIOps / LLM
    - receiver: direct-email
      matchers:
        - severity =~ "critical|warning"
      continue: false
      group_wait: 5s
      group_interval: 1m
      repeat_interval: 4h

receivers:
  - name: aiops-webhook
    webhook_configs:
      - url: http://aiops-assistant.aiops/api/alert
        send_resolved: true
        http_config:
          timeout: 5s                 # ★ 远小于 Alertmanager 默认 10s
  - name: direct-email
    email_configs:
      - to: '${MAIL_TO}'
        from: '${SMTP_USER}'
        smarthost: '${SMTP_HOST}:${SMTP_PORT}'
        auth_username: '${SMTP_USER}'
        auth_password: '${SMTP_PASS}'
        send_resolved: true
        headers:
          Subject: '[告警] {{ .CommonLabels.alertname }} ({{ .Status | toUpper }})'
```

### 3.3 验证

```bash
# ① 确认 Alertmanager 加载了新配置
kubectl exec -n monitoring alertmanager-kube-prom-kube-prometheus-alertmanager-0 -- \
  sh -c 'cat /etc/alertmanager/config_out/alertmanager.env.yaml' | grep -A6 "direct-email"

# ② 模拟一条 critical 告警，确认两路都投递
#    （邮件应收到原始告警；钉钉/企微应收到 AI 分析）
curl -s -X POST http://10.9.63.169/api/alert -H "Content-Type: application/json" \
  -d '{"status":"firing","alerts":[{"labels":{"alertname":"FallbackTest","namespace":"app","severity":"critical"},"annotations":{"summary":"兜底通道测试"}}]}'

# ③ 关键验证：停掉 AIOps，确认邮件仍能收到
kubectl scale deployment aiops-assistant -n aiops --replicas=0
# 触发一条真实告警，观察是否仍收到兜底邮件
# 验证后恢复：kubectl scale deployment aiops-assistant -n aiops --replicas=1
```

## 四、注意事项与取舍

| 项 | 说明 |
|---|---|
| **SMTP 端口兼容** | Alertmanager 的 email 对隐式 TLS（465/SMTPS）支持有限，通常用 `587 + STARTTLS`；若服务商仅支持 465，改用下节的 relay 方案 |
| **正常时会收到两路通知** | 这是有意的：AI 通道给分析、直投通道给原始告警，内容互补。若觉得吵，可把直投通道限定为 `severity="critical"` |
| **silence / inhibit 无法只静默一路** | 它们是**告警级**的，对所有 receiver 生效。想在维护窗口只静默 AI 分析，需用路由级 `mute_time_intervals` |
| **`group_by` / `group_wait` 是路由级属性** | 因此两条通道可独立聚合：AI 粗聚合省 token，直投细聚合求快 |

## 五、进阶方案（后续可选）

若需要**复用现有钉钉/企微群机器人**做兜底（而非邮件），需要加一个格式转换组件，因为 Alertmanager 的 webhook 负载格式与群机器人的 markdown 格式不兼容：

```
Alertmanager → notify-relay（独立 Deployment，无 LLM 依赖）→ 钉钉/企微群机器人
```

relay 用同一镜像的独立入口实现即可（只做格式转换，不调 LLM、不采集上下文），保持「直投通道无 AI 依赖」的原则。
