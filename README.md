# AI 智能分析 K8s 集群服务日志和告警
# AI-Powered Log & Alert Analysis for K8s Services

> 一个把「云原生运维」与「AI」融合的端到端企业级项目。
> 基于已有 3 节点 Kubernetes 集群 + Harbor 私有仓库，从零部署完整的
> **AI 推理业务 + 可观测平台 + AIOps 智能运维助手**。

---

## 📌 一、项目技术亮点

- **云原生**：多节点 K8s 集群、容器化、存储方案（NFS 动态供给）、Ingress/LoadBalancer、监控告警、CI/CD。
- **AI 基建**：在 K8s 上部署/运维模型推理服务（vLLM/模拟）、AI 业务 API。
- **AI 驱动运维**：用 LLM 做日志智能分析、告警根因定位、故障处置建议（RAG + 上下文采集，AIOps）。
- **工程化**：私有 Harbor 镜像仓库、可观测三件套（Prometheus/Grafana/Loki）、CI/CD。
- **可演示**：整条链路真实跑通，制造故障 → 告警 → AI 自动分析。

## 🎯 二、业务场景（一句话）

一个「智能运维服务」对外提供模型推理 API，同时用 AI 助手自动巡检、分析日志、定位告警根因。**运维对象本身就是 AI 服务**，且**运维手段也由 AI 驱动** —— 两端都靠 AI。

---

## 📊 三、可观测平台

项目内置完整的可观测体系（可观测性三支柱），既是人工查看的监控平台，也是 AIOps 助手的数据来源：

| 支柱 | 组件 | 访问方式 | 状态 |
|------|------|---------|------|
| **指标 Metrics** | Prometheus（kube-prometheus-stack） | ClusterIP:9090 | ✅ 采集节点/容器/Pod/业务指标 |
| **可视化** | Grafana | `http://192.168.243.202`（LoadBalancer） | ✅ 看板可访问 |
| **日志 Logs** | Loki + Promtail（DaemonSet×3） | ClusterIP:3100 | ✅ `{namespace="app"}` 日志可查 |
| **告警 Alerts** | Alertmanager + PrometheusRule | ClusterIP:9093 | ✅ 6 条规则 + 路由到 AIOps |

**关键数据流**：
```
业务 Pod 指标/日志
   │
   ▼
Prometheus（指标）← ServiceMonitor ← ai-svc /metrics
Loki（日志）← Promtail ← /var/log/pods/*
   │
   ▼
告警规则触发 → Alertmanager → AIOps 助手（AI 分析）
```

---

## ✅ 四、实施进度追踪（每完成一步同步更新）

> 当前进度：**可观测层进行中** —— kube-prometheus-stack 已部署，业务指标采集已打通，下一步部署 Loki 日志 + 告警规则。

| 阶段 | 步骤 | 状态 |
|------|------|------|
| **基础** | 环境确认：3 节点 K8s v1.36.3 已 Ready，Harbor 可登录 | ✅ 完成 |
| **基础** | 确定存储方案：采用 nfs-subdir-external-provisioner v4.0.2（NFS 动态供给，替代 local-path） | ✅ 完成 |
| **存储** | Harbor 机（192.168.243.120）部署 NFS 服务端 `/nfsdata/ai-cloud-native-ops` | ✅ 完成 |
| **存储** | 三台 k8s 节点安装 nfs-utils 客户端 | ✅ 完成 |
| **存储** | 部署 nfs-client-provisioner（Deployment+RBAC+StorageClass） | ✅ 完成 |
| **存储** | 验证动态供给：创建测试 PVC/Pod 确认挂载 | ✅ 完成 |
| **网络** | 部署 MetalLB（LoadBalancer） | ✅ 完成 |
| **网络** | 部署 Ingress-NGINX | ✅ 完成 |
| **基础** | 创建命名空间 app / monitoring / aiops | ✅ 完成 |
| **业务** | 构建并推送 ai-svc / mock-vllm 镜像到 Harbor | ✅ 完成 |
| **业务** | 部署业务服务 + Ingress，验证推理 API | ✅ 完成 |
| **可观测** | 部署 Prometheus / Grafana / Alertmanager / kube-state-metrics / node-exporter | ✅ 完成 |
| **可观测** | 业务指标采集打通（ServiceMonitor + ai-svc /metrics 修复） | ✅ 完成 |
| **可观测** | 部署 Loki（单体 + filesystem + NFS PVC） | ✅ 完成 |
| **可观测** | 部署 Promtail（日志采集 DaemonSet，双 job：kubernetes-pods + docker-containers） | ✅ 完成 |
| **可观测** | 配置告警规则 + Alertmanager → AIOps webhook | ✅ 完成 |
| **AIOps** | 部署 AIOps 助手（LLM + RAG + 上下文采集） | ✅ 完成 |
| **AIOps** | AI 日志智能分析验证通过（analyze-log：Loki 日志 → DeepSeek 分析） | ✅ 完成 |
| **演示** | 制造故障 → 告警 → AI 自动根因分析（AiSvcDown 告警 → AI 结合集群日志判断为瞬时抓取失败/误报） | ✅ 完成 |
| **演示** | **完整自动化闭环**：ai-svc 缩容 → AiSvcGone 告警（absent() 检测）→ Alertmanager 路由 → AIOps webhook 自动接收（200 OK） | ✅ 完成 |
| **通知** | **多渠道告警通知**：AI 分析结果 + 原始告警 → 钉钉 / 企业微信 / 邮件 三渠道推送（errcode:0 全部成功） | ✅ 完成 |
| **通知** | **故障恢复通知**：告警 resolved → 「✅ 告警已恢复」三渠道推送（事件生命周期完整闭环） | ✅ 完成 |
| **AIOps** | **AI 根因分析质量验证**：能读取集群事件（缩容记录）、精准定位根因（人工缩容导致）、给出处置步骤 | ✅ 完成 |
| **收尾** | 文档完善、架构图 | 🔄 进行中 |

**变更日志（按时间）**
- `2026-08-26`：环境确认（3 节点 Ready + Harbor 登录成功）
- `2026-08-26`：存储方案由 local-path 改为 NFS（取自《7.Kubernetes存储.pdf》的 nfs-subdir-external-provisioner 方案，更企业级，支持 RWX）
- `2026-08-26`：确认 Harbor 镜像 `reix.harbor.cn/k8s/nfs-subdir-external-provisioner:v4.0.2` 可拉取
- `2026-08-26`：完成 NFS 服务端部署（Harbor 机 192.168.243.120，共享目录 `/nfsdata/ai-cloud-native-ops`）
- `2026-08-26`：部署 nfs-client-provisioner 成功（Pod Running，StorageClass `nfs-client` 设为默认）
- `2026-08-26`：动态供给验收通过：测试 PVC 自动 Bound、PV 自动创建、Pod 写入 NFS 成功
- `2026-08-26`：落盘验证通过：Harbor 机 `/nfsdata/ai-cloud-native-ops/default/test-nfs-claim/test.txt` 内容正确，数据穿透 K8s→NFS→宿主机磁盘全链路打通
- `2026-08-27`：部署 MetalLB v0.16.1 成功（controller + speaker×3 Running），IP 池 `192.168.243.200-220`，L2 通告 ens160；LoadBalancer 验证通过：test-lb-svc 拿到 `192.168.243.200` 并成功访问 nginx 页
- `2026-08-27`：部署 Ingress-NGINX v1.15.1 成功（镜像走 Harbor），controller Running，LoadBalancer 拿到 `192.168.243.201`
- `2026-08-27`：Ingress 端到端验证通过：`curl -H "Host: test.ops.local" http://192.168.243.201/` 返回 nginx 页，MetalLB→Ingress→Pod 全链路打通
- `2026-08-27`：业务镜像构建并推送成功：`reix.harbor.cn/k8s-ai/ai-svc:latest`、`mock-vllm:latest`（Harbor k8s-ai 私有项目，已配 imagePullSecret）
- `2026-08-27`：业务服务部署成功：ai-svc×2 + vllm-svc Running，LoadBalancer 拿到 `192.168.243.200`，推理 API `/v1/infer` 验证通过（延迟 ~50ms）
- `2026-08-27`：kube-prometheus-stack 部署成功（Helm）：Prometheus/Grafana/Alertmanager/kube-state-metrics/node-exporter 全部 Running，Grafana LoadBalancer 拿到 `192.168.243.202`
- `2026-08-27`：业务指标采集打通：修复 ai-svc `/metrics` JSON 包装 bug（改 Response 纯文本），ServiceMonitor + release 标签 + Service label 三层配置正确后，`ai_svc_requests_total` 成功被 Prometheus 采集
- `2026-08-27`：Loki（裸清单单体 + NFS PVC）部署成功；Promtail 排障完成（根因：容器日志软链指向 `/data/docker/containers` 未挂载，加挂载 + 双 job 配置后日志采集打通，`{namespace="app"}` 查询成功）
- `2026-08-28`：告警规则部署（5+1 条 PrometheusRule），修复「缩容=0 时 up==0 不触发」盲区（新增 `absent()` 检测的 AiSvcGone 规则）；Alertmanager 路由到 AIOps webhook（绕过 CRD namespace 限制，直接改 secret 配置）
- `2026-08-28`：AIOps 助手部署成功（DeepSeek LLM + RAG + ContextCollector），修复 Alertmanager webhook status 字段位置 bug、kubectl 进镜像、模型名大小写等问题
- `2026-08-28`：**完整自动化闭环验证**：ai-svc 缩容 → AiSvcGone 告警 → Alertmanager → AIOps 自动接收（200 OK）
- `2026-08-29`：**多渠道通知打通**：AI 分析结果 + 告警 → 钉钉 / 企业微信 / 邮件三渠道真实送达（errcode:0，用户终端截图确认）
- `2026-08-29`：**故障恢复通知打通**：告警 resolved → 「✅ 告警已恢复」三渠道推送，事件生命周期完整闭环

---

## 🖥️ 五、当前环境

| 角色 | 主机 | IP | OS | 规格 | 用途 |
|------|------|-----|-----|------|------|
| 控制平面 | k8s-master | 192.168.243.121 | Rocky Linux 10.2 | 4C/4G/50G | 集群管理 |
| 工作节点 | k8s-node1 | 192.168.243.122 | Rocky Linux 10.2 | 4C/4G/50G | 业务/监控 |
| 工作节点 | k8s-node2 | 192.168.243.123 | Rocky Linux 10.2 | 4C/4G/50G | 业务/AIOps |
| Harbor+NFS | harbor | 192.168.243.120 | Rocky Linux 10.2 | — | 镜像仓库 + NFS 存储 |

**集群状态**：Kubernetes v1.36.3，容器运行时 docker 29.6.2，3 节点 Ready。

---

## 🏗️ 六、架构图

```
                        ┌──────────────────────────────┐
                        │       客户端 / Web UI          │
                        └──────────┬───────────────────┘
                                   │ (https/ingress)
               ┌───────────────────▼───────────────────┐
               │       Ingress-NGINX / MetalLB LB       │
               └───┬───────────────┬───────────────┬────┘
                   │               │               │
          ┌────────▼───┐   ┌───────▼─────┐   ┌─────▼────────┐
          │  ai-svc     │   │  aiops-     │   │  grafana /   │
          │ (FastAPI)   │   │  assistant  │   │  prometheus  │
          └────────┬───┘   └──────┬──────┘   └───┬──────────┘
                   │              │              │
        ┌──────────▼───┐   ┌──────▼──────┐  ┌────▼───────────┐
        │   mock-vllm  │   │  LLM API     │  │  Loki /        │
        │  模型推理服务 │   │  (+ RAG)     │  │  Alertmanager  │
        └─────────────┘   └──────────────┘  └────────────────┘
                                │
                        ┌───────▼────────┐
                        │  NFS 存储        │
                        │ 192.168.243.120 │
                        └────────────────┘
```

---

## 🛠️ 七、技术栈

| 领域 | 技术 |
|------|------|
| 集群 | Kubernetes v1.36.3、Docker（CRI）、Calico |
| 存储 | NFS + nfs-subdir-external-provisioner（动态供给，RWX）|
| 网络 | MetalLB（LoadBalancer）、Ingress-NGINX |
| 可观测性 | Prometheus（operator）、Grafana、Loki（单体 + filesystem + NFS PVC）、Promtail、Alertmanager |
| AI 服务 | mock-vllm（模拟推理）、FastAPI 业务服务 |
| AIOps | LLM API（DeepSeek/OpenAI）、RAG 知识库、上下文采集 |
| 镜像仓库 | Harbor（reix.harbor.cn，项目 `k8s-ai` 专用于本项目镜像）|

---

## 📂 八、仓库结构

```
ai-cloud-native-ops/
├── README.md        # 本文件：项目总览 + 实施进度追踪
├── docs/            # 文档：架构、roadmap、实施手册
├── scripts/         # 部署 / 运维脚本
├── k8s/             # K8s 清单（app / aiops / storage / argocd）
├── apps/            # 业务微服务源码（ai-svc / mock-vllm）
├── monitoring/      # Prometheus/Grafana/Loki/Alertmanager 配置
├── aiops/           # AI 运维助手代码（LLM + RAG + 上下文采集）
└── .github/         # CI/CD 流水线
```

---

## 🚀 九、文档索引

| 主题 | 文档 |
|------|------|
| **完整部署步骤（从环境到闭环）** | [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) |
| **配置管理（告警规则/通知媒介/LLM Key）** | [`docs/CONFIGURATION_GUIDE.md`](docs/CONFIGURATION_GUIDE.md) |
| **告警规则扩展指南** | [`docs/ALERT_RULES_GUIDE.md`](docs/ALERT_RULES_GUIDE.md) |
| **告警效果图（钉钉/企微/邮箱实测）** | [`docs/ALERT_SCREENSHOTS.md`](docs/ALERT_SCREENSHOTS.md) |
| 四阶段路线总览 | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| 架构与数据流 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| 可观测性三支柱 | [`docs/OBSERVABILITY_STACK.md`](docs/OBSERVABILITY_STACK.md) |
| Ingress Host 路由实验 | [`docs/EXPERIMENT_INGRESS_HOST_ROUTING.md`](docs/EXPERIMENT_INGRESS_HOST_ROUTING.md) |
| Promtail 排障记录 | [`docs/TROUBLESHOOTING_PROMTAIL.md`](docs/TROUBLESHOOTING_PROMTAIL.md) |

> 注：原计划的 `docs/INSTALL_UBUNTU_VM.md` 与 `docs/CLUSTER_SETUP.md` 为「从零搭建 VM 集群」的备选方案，
> 因当前环境已有现成集群，改为直接在此集群上部署，文档保留作参考。
