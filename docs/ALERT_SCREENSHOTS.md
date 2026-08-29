# 告警通知效果图（真实测试记录）

> 以下为故障注入闭环测试（ai-svc 缩容 → AiSvcGone 告警 → AI 分析 → 三渠道通知）的**真实截图内容转写**。
> 测试时间：2026-08-29 20:13（告警）~ 20:18（恢复）

---

## 图一：钉钉收到的告警 + 恢复通知

**第一条消息（20:13）— 告警通知**

> **告警**: AiSvcGone
> **摘要**: ai-svc 指标完全消失
> **AI 根因分析**:
> **最可能根因**
> ai-svc Deployment 被缩容至 0 副本（事件显示先缩到0，25m前扩到2，2m59s前又删除全部Pod），导致无Pod暴露 /metrics，Prometheus 抓取目标消失，指标完全消失。无证据表明节点或底层故障。
>
> **处置步骤**
> 1. 确认当前副本数及触发源：`kubectl -n app get deploy ai-svc -o yaml | grep replicas`、`kubectl -n app get hpa`
> 2. 手动恢复副本数：`kubectl -n app scale deploy ai-svc --replicas=2`
> 3. 检查Pod是否Running/Ready：`kubectl -n app get pods -l app=ai-svc`
> 4. 若存在HPA，检查其 min/max 及指标是否异常，避免再次缩容到0。
>
> **验证恢复**
> - Pod状态：2/2 Running，Deployment READY 2/2
> - 服务端点：`kubectl -n app get endpoints ai-svc` 有Pod IP
> - 指标采集：访问Pod /metrics 返回200，Prometheus target 恢复，告警指标重新出现。

**第二条消息（20:18）— 恢复通知**

> **告警**: AiSvcGone
> **状态**: 已恢复 (resolved)
> **摘要**: ai-svc 指标完全消失
> **恢复时间**: 见告警详情
> 故障已解除，无需处理。

---

## 图二：企业微信收到的告警 + 恢复通知

**第一条消息（告警机器人）**

> 【AiSvcGone】
> 告警: AiSvcGone
> 摘要: ai-svc 指标完全消失
> AI 根因分析:
> **最可能根因**
> ai-svc Deployment 被缩容至 0 副本（事件显示先缩到0，25m前扩到2，2m59s前又删除全部Pod），导致无Pod暴露 /metrics，Prometheus 抓取目标消失，指标完全消失。无证据表明节点或底层故障。
>
> **处置步骤**
> 1. 确认当前副本数及触发源：`kubectl -n app get deploy ai-svc -o yaml | grep replicas`、`kubectl -n app get hpa`
> 2. 手动恢复副本数：`kubectl -n app scale deploy ai-svc --replicas=2`
> 3. 检查Pod是否Running/Ready：`kubectl -n app get pods -l app=ai-svc`
> 4. 若存在HPA，检查其 min/max 及指标是否异常，避免再次缩容到0。
>
> **验证恢复**
> - Pod状态：2/2 Running，Deployment READY 2/2
> - 服务端点：`kubectl -n app get endpoints ai-svc` 有Pod IP
> - 指标采集：访问Pod /metrics 返回200，Prometheus target 恢复，告警指标重新出现。

**第二条消息（告警机器人）**

> 【AiSvcGone】
> 告警: AiSvcGone
> 状态: 已恢复 (resolved)
> 摘要: ai-svc 指标完全消失
> 恢复时间: 见告警详情
> 故障已解除，无需处理。

---

## 图三：QQ 邮箱收到的两封邮件

**邮件 1（10 分钟前）— 告警邮件**

> **主题**: [AIOps] 告警 AiSvcGone
> **发件人**: SMTP发件账号 → 收件人邮箱
> **正文**: 告警: AiSvcGone / 摘要: ai-svc 指标完全消失 / **AI 根因分析**: 最可能根因（ai-svc Deployment 被缩容至 0 副本...）处置步骤...验证恢复...

**邮件 2（5 分钟前）— 恢复邮件**

> **主题**: [AIOps] ✅ 告警已恢复 AiSvcGone
> **发件人**: SMTP发件账号 → 收件人邮箱
> **正文**: 告警: AiSvcGone / 状态: 已恢复 (resolved) / 摘要: ai-svc 指标完全消失 / 恢复时间: 见告警详情 / 故障已解除，无需处理。

---

## 本次测试验证的价值点

| 验证项 | 结果 |
|--------|------|
| 故障注入（缩容）→ Prometheus 告警 | ✅ AiSvcGone firing |
| Alertmanager 路由 → AIOps webhook | ✅ receivers: aiops-webhook |
| AI 根因分析（读取真实集群事件）| ✅ 精准定位「人工缩容导致」，非故障 |
| 处置建议（含 kubectl 命令）| ✅ 完整、可执行 |
| 三渠道通知（钉钉/企微/邮件）| ✅ errcode:0 + 邮件已发送 |
| 恢复通知（resolved）| ✅ 「✅ 告警已恢复」三渠道送达 |

> 📌 截图原图保存在个人设备中（手机翻看钉钉/企微/邮箱即可）。
