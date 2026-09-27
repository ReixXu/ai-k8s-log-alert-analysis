# 告警通知效果图（真实测试记录）

> 以下为故障注入闭环测试（ai-svc 缩容 → AiSvcGone 告警 → AI 分析 → 三渠道通知）的**真实截图内容转写**。
> 测试时间：2026-08-29 20:13（告警）~ 20:18（恢复）

---

## 图一：钉钉收到的告警 + 恢复通知
<img width="692" height="1145" alt="659a40c7464e7febbf7710470ab3d67d" src="https://github.com/user-attachments/assets/5049a732-780f-4931-9eeb-9f9c10b30632" />

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
<img width="1080" height="3796" alt="7ce01755aef34cb0d10ba688f073688b" src="https://github.com/user-attachments/assets/6f33e550-89c5-4829-b666-bc7454783927" />

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
<img width="1080" height="672" alt="8bde725a0d16d497e27bf65c1e0cc14f" src="https://github.com/user-attachments/assets/5fe14605-6e33-4089-9f46-4d5c390c0708" />

**邮件 1（10 分钟前）— 告警邮件**

> **主题**: [AIOps] 告警 AiSvcGone
> **发件人**: SMTP发件账号 → 收件人邮箱
> **正文**: 告警: AiSvcGone / 摘要: ai-svc 指标完全消失 / **AI 根因分析**: 最可能根因（ai-svc Deployment 被缩容至 0 副本...）处置步骤...验证恢复...

**邮件 2（5 分钟前）— 恢复邮件**

> **主题**: [AIOps] ✅ 告警已恢复 AiSvcGone
> **发件人**: SMTP发件账号 → 收件人邮箱
> **正文**: 告警: AiSvcGone / 状态: 已恢复 (resolved) / 摘要: ai-svc 指标完全消失 / 恢复时间: 见告警详情 / 故障已解除，无需处理。

---

## 案例二：集群级告警（etcd）的 AI 分析

除业务服务告警外，本系统同样支持**集群级/控制平面告警**的自动分析。

### 2.1 问题现象（修复前）

收到邮件：

> **告警**: etcdInsufficientMembers
> **摘要**: etcd cluster has insufficient number of members.
> **AI 根因分析**: [LLM返回空内容] 模型未生成有效分析，请稍后重试或检查 prompt 长度。

虽然「链路是通的」（告警成功路由到 AIOps 且三渠道送达），但 AI 分析为空。

### 2.2 根因定位（两个叠加问题）

**问题一：上下文与告警不匹配**
原 `context.py` 只按 `namespace` 采集上下文，而 etcd 告警没有 namespace 标签，代码兜底为 `app`——于是给 AI 喂的是 app 命名空间 ai-svc/vllm 的 Pod、事件与日志，与 etcd 完全无关。

**问题二：推理模型的 token 消耗被低估**
`deepseek-v4-flash` 属推理类模型，思考过程（`reasoning_content`）与最终答案（`content`）**都计入 `completion_tokens`**。原 `max_tokens=1500` 在复杂告警分析场景下被思考过程耗尽，导致 `content` 为空。

在容器内实测确认：

```
finish_reason: stop
content: 'etcd 成员不足通常是由于部分节点宕机、网络分区或 peer 通信故障...'
reasoning_content: '我们需要回答用户中文请求：...（216 tokens 思考过程）'
usage: completion_tokens=260, reasoning_tokens=216   ← 思考占 83%
```

### 2.3 解决方案

| 改进 | 文件 | 内容 |
|------|------|------|
| 上下文按告警类型分流 | `app/context.py` | 节点类 → 查节点状态与全集群异常 Pod；控制平面类（etcd/scheduler/apiserver/proxy/TargetDown）→ 查 kube-system 组件、全集群事件、Endpoints；业务类 → 按该 namespace 查全套 |
| 告警范围识别 | `app/main.py` | 无 namespace 标签时标记为 `cluster-wide`，prompt 明确告知作用范围，并要求 AI 说明判断在基础设施层/编排层/应用层 |
| token 配额与兼容 | `app/llm.py` | max_tokens 提升至 4000（可用 `LLM_MAX_TOKENS` 调整）；`content` 为空时回退使用 `reasoning_content`；每次调用打印 finish_reason/思考长度/usage 便于诊断 |

### 2.4 修复后的 AI 分析（真实输出）

> 1) **根因**：最可能是**容器编排/监控配置层误报**。快照仅见 `etcd-k8s-master` 一个 etcd 成员且 Running，节点 CPU/内存正常；`etcdInsufficientMembers` 通常按 HA 阈值（如成员数<3 或<多数）触发，单 master 单 etcd 集群必然告警。若原设计为多 etcd，才考虑成员丢失/quorum 故障。
>
> 2) **处置**：
> ```bash
> kubectl -n kube-system get pod -l component=etcd -o wide
> kubectl -n kube-system exec etcd-k8s-master -- sh -c 'export ETCDCTL_API=3; C="--cacert=/etc/kubernetes/pki/etcd/ca.crt --cert=/etc/kubernetes/pki/etcd/server.crt --key=/etc/kubernetes/pki/etcd/server.key"; etcdctl $C member list -w table; etcdctl $C endpoint health --cluster'
> ```
> 若 member=1 且 healthy：将 Prometheus `etcdInsufficientMembers` 阈值改为 1 或静默；需 HA 则扩容至 3 control-plane。若异常：查 `kubectl -n kube-system logs etcd-k8s-master --tail=200`，修网络/证书/磁盘后恢复成员。
>
> 3) **验证**：`etcdctl endpoint health` 全 healthy，成员数符合设计，Prometheus 告警 inactive，`kubectl get nodes` 正常，apiserver 无持续重启。

**分析亮点**：
- 正确识别层级（编排/监控配置层误报），而非笼统归因
- 从集群真实拓扑（仅 1 个 etcd 成员）推断出「单节点集群触发 HA 阈值告警」这一根因
- 给出带证书参数的 etcdctl 专业命令，并分情况给出处置路径
- 提供架构建议（如需 HA 应扩容至 3 control-plane）

### 2.5 该案例验证的能力

| 验证项 | 结果 |
|--------|------|
| 集群级告警（无 namespace）自动触发 AI 分析 | ✅ |
| 按告警类型采集正确上下文（kube-system 而非 app）| ✅ |
| AI 给出层级判断（基础设施/编排/应用）| ✅ |
| 结合集群真实拓扑做领域推理（单 etcd → 误报）| ✅ |
| 输出专业可执行的排查命令 | ✅ |

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
| 集群级告警分析（etcd 案例）| ✅ 正确识别层级与根因 |
| 任意命名空间覆盖能力 | ✅ 上下文按告警的 namespace 标签动态采集 |

> 📌 截图原图保存在个人设备中（手机翻看钉钉/企微/邮箱即可）。
