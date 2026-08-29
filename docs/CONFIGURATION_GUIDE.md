# 配置管理指南（部署前后如何调整）

> 本项目所有「日常维护」配置的修改方法：告警规则、告警媒介（钉钉/企微/邮箱）、LLM API Key。
> 与 `ALERT_RULES_GUIDE.md`（告警规则语法详解）配合使用。

---

## 一、告警规则调整

### 1.1 部署前（预置规则）

规则文件：`monitoring/ai-svc-alerts.yaml`（仓库内），部署前直接编辑该文件，然后：

```bash
kubectl apply -f monitoring/ai-svc-alerts.yaml
```

### 1.2 部署后（新增/修改/删除）

**推荐做法：改仓库文件 → apply（保持仓库与集群一致）**

```bash
# ① 编辑仓库中的规则文件
vi monitoring/ai-svc-alerts.yaml

# ② 应用
kubectl apply -f monitoring/ai-svc-alerts.yaml

# ③ 验证加载
curl -s http://10.1.171.25:9090/api/v1/rules | jq '.data.groups[] | select(.name=="ai-svc.rules") | .rules[].name'
```

**快速验证告警（不改文件）**：

```bash
# 查看当前告警状态
curl -s 'http://10.1.171.25:9090/api/v1/alerts' | jq '.data.alerts[] | {labels: .labels.alertname, state}'
```

### 1.3 规则修改示例

```yaml
# 修改触发阈值（比如 P99 从 1s 改 500ms）
- alert: AiSvcP99LatencyHigh
  expr: histogram_quantile(0.99, sum by (le) (rate(ai_svc_request_duration_seconds_bucket{endpoint="/v1/infer"}[5m]))) > 0.5
  for: 5m
  ...
```

> 完整语法、指标参考、`absent()` 坑：见 `ALERT_RULES_GUIDE.md`

### 1.4 删除规则

从 `monitoring/ai-svc-alerts.yaml` 删掉对应规则块 → `kubectl apply` 即可（PrometheusRule 是全量替换）。

---

## 二、告警媒介修改（钉钉 / 企业微信 / 邮箱）

### 2.1 媒介配置存在哪

所有通知媒介配置在 **Secret `aiops-notify`**（aiops 命名空间）——AIOps 助手通过环境变量读取。

### 2.2 修改某个媒介（改 Secret 后重启 Pod）

```bash
# ① 查看当前配置（不显示值）
kubectl get secret aiops-notify -n aiops

# ② 更新配置（示例：换钉钉 webhook）
kubectl create secret generic aiops-notify -n aiops \
  --from-literal=dingtalk_webhook='<新钉钉webhook>' \
  --from-literal=wecom_webhook='<企微webhook（不变也需带上）>' \
  --from-literal=smtp_host='smtp.yeah.net' \
  --from-literal=smtp_port='465' \
  --from-literal=smtp_user='<邮箱>' \
  --from-literal=smtp_pass='<授权码>' \
  --from-literal=mail_to='<收件人>' \
  --dry-run=client -o yaml | kubectl apply -f -

# ③ 重启让新配置生效（env 从 Secret 读取，重启后生效）
kubectl rollout restart deployment/aiops-assistant -n aiops
kubectl rollout status deployment/aiops-assistant -n aiops
```

### 2.3 只改其中一个媒介

用 `kubectl patch` 只更新某个 key（不需要重写整个 Secret）：

```bash
# 只改钉钉 webhook
NEW_DINGTALK=$(echo -n '<新钉钉webhook>' | base64 -w0)
kubectl patch secret aiops-notify -n aiops --type=merge \
  -p "{\"data\":{\"dingtalk_webhook\":\"$NEW_DINGTALK\"}}"
kubectl rollout restart deployment/aiops-assistant -n aiops
```

### 2.4 获取各媒介 Webhook 的方法

| 媒介 | 获取方式 | 注意 |
|------|---------|------|
| 钉钉 | 钉钉群 → 群设置 → 智能群助手 → 添加机器人 → 自定义 | 如开启「加签」需额外配 secret；可设安全关键字 |
| 企业微信 | 企微群 → 群机器人 → 添加 → 复制 Webhook | key 在 URL 里 |
| 邮箱 | SMTP 服务商控制台生成授权码 | 不是登录密码，是 SMTP 授权码 |

### 2.5 停用某个媒介

把对应 key 置空即可（notify.py 检测到空自动跳过）：

```bash
kubectl patch secret aiops-notify -n aiops --type=merge \
  -p '{"data":{"dingtalk_webhook":""}}'
kubectl rollout restart deployment/aiops-assistant -n aiops
```

### 2.6 通知内容模板修改

模板在 `aiops/assistant/app/notify.py`：
- `notify_all()`：告警通知（告警名 + 摘要 + AI 分析）
- `notify_resolved()`：恢复通知（✅ 已恢复）
修改后需**重建镜像**并更新 Deployment。

---

## 三、LLM API Key / 模型修改（AI 分析用的模型）

### 3.1 配置存在哪

LLM 配置在 **Secret `aiops-secrets`** + **Deployment 环境变量**：

| 配置 | 位置 | 示例值 |
|------|------|--------|
| API Key | Secret `aiops-secrets` / key `llm_api_key` | sk-xxxx |
| Base URL | Deployment env `LLM_BASE_URL` | https://api.deepseek.com |
| 模型名 | Deployment env `LLM_MODEL` | deepseek-v4-flash |

### 3.2 修改 API Key（最常见操作）

```bash
# ① 更新 Secret
kubectl create secret generic aiops-secrets -n aiops \
  --from-literal=llm_api_key='<新Key>' \
  --dry-run=client -o yaml | kubectl apply -f -

# ② 重启 Pod 让新 Key 生效（env 从 Secret 注入，Pod 内已缓存，需重启）
kubectl rollout restart deployment/aiops-assistant -n aiops
kubectl rollout status deployment/aiops-assistant -n aiops

# ③ 验证
curl -s -X POST http://<aiops-svc-ip>/api/ask \
  -H "Content-Type: application/json" -d '{"question":"测试"}' | jq .answer
```

### 3.3 切换模型（如换 deepseek-v4-pro 或 OpenAI）

```bash
# ① 改 Deployment 环境变量
kubectl set env deployment/aiops-assistant -n aiops LLM_MODEL=deepseek-v4-pro
kubectl set env deployment/aiops-assistant -n aiops LLM_BASE_URL=https://api.deepseek.com

# ② 等滚动更新完成
kubectl rollout status deployment/aiops-assistant -n aiops

# ③ 同步修改仓库清单（保持仓库一致）
# k8s/aiops/aiops-assistant.yaml 中 LLM_MODEL/LLM_BASE_URL
```

> ⚠️ **模型名大小写敏感**（踩过的坑）：DeepSeek 只认 `deepseek-v4-flash`/`deepseek-v4-pro`/`deepseek-v4-flash-vision-exp`（小写），`deepseek-v4-Flash` 会报 400。

### 3.4 切换 LLM 服务商（如换 OpenAI）

```bash
kubectl set env deployment/aiops-assistant -n aiops LLM_BASE_URL=https://api.openai.com LLM_MODEL=gpt-4o
kubectl rollout status deployment/aiops-assistant -n aiops
# 同步更新 aiops-secrets 的 llm_api_key 为 OpenAI Key
```

---

## 四、其他常用配置

### 4.1 修改 AI 分析的上下文范围

`aiops/assistant/app/context.py`：
- `fetch_logs()`：`limit=50`（日志条数）、`since`（时间窗口）
- `collect_for_alert()`：快照内容（CPU/事件/Pod/部署/日志）
改后需重建镜像。

### 4.2 修改 RAG 知识库

`aiops/assistant/knowledge/*.md`：直接编辑文档内容（新增故障排查知识），重建镜像生效。

### 4.3 修改 Alertmanager 路由（告警分级/分流）

Secret `alertmanager-kube-prom-kube-prometheus-alertmanager` 的 `alertmanager.yaml`：
- `routes`：按 severity/service 分流到不同 receiver
- `receivers`：定义各接收端（webhook/钉钉/邮件）
改后重启 Alertmanager Pod。

### 4.4 Grafana / Prometheus 密码

```bash
# Grafana（helm 安装时设的 adminPassword）
kubectl get secret kube-prom-grafana -n monitoring -o jsonpath='{.data.admin-password}' | base64 -d
```

---

## 五、故障排查速查

| 现象 | 排查 |
|------|------|
| 告警不触发 | `curl .../api/v1/rules` 看规则是否加载；查 Prometheus 日志 |
| 告警触发但没收到通知 | Alertmanager `api/v2/alerts` 看 receivers 是否为 aiops-webhook |
| 通知失败 | AIOps 日志 `[notify]` 行看各渠道 errcode |
| AI 分析为空 | AIOps 日志 diagnosis；确认 LLM Key/模型名/上下文长度 |
| 日志采集不到 | Promtail `files_active` 指标；确认 `/data/docker/containers` 挂载 |
