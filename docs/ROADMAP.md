# ROADMAP — 四阶段实施路线

> 目标：一个可演示、可深挖的「AI 智能分析 K8s 集群日志和告警」项目。
> 每阶段结束都有**可跑通的交付物**，随时能中断、能继续。

---

## 阶段 P0 — 虚拟机与环境基建（半天~1天）

**目标**：搭好 3 台可 SSH、可互通的 Ubuntu 22.04 VM，装好基础工具与容器运行时。

**任务清单**
- [ ] VMware Workstation 创建 VM：Master / Worker-1 / Worker-2
- [ ] 同一 NAT/桥接网段，固定 IP（示例 192.168.x.101/102/103）
- [ ] 配置 SSH 免密、hosts 解析
- [ ] 每台装：docker/containerd、kubectl、curl、git、jq、htop 等
- [ ] 禁用 swap、加载内核模块、设 sysctl（K8s 前置）
- [ ] 测试三机互通（ping / ssh）

**交付物**
- `scripts/init_node.sh`（一键初始化单节点）
- 三台机器可互通、可 SSH

**关键技术点**
- 容器运行时选型：containerd vs docker（如今推荐 containerd）
- K8s 前置条件：swap 关闭、br_netfilter、ip_forward、cgroups
- NAT vs 桥接网络的区别与应用场景

---

## 阶段 P1 — Kubernetes 集群搭建（1~2天）

**目标**：kubeadm 装出高可用的多节点集群（至少 1 控制平面 + 2 worker）。

**任务清单**
- [ ] 安装 kubeadm、kubelet、kubectl（固定版本）
- [ ] 初始化控制平面（`kubeadm init`）
- [ ] 安装 CNI（Calico）
- [ ] 节点 join（worker 加入）
- [ ] 安装 MetalLB（LoadBalancer）或直接用 NodePort
- [ ] 安装 Ingress-NGINX
- [ ] 安装存储（local-path / NFS / Longhorn）
- [ ] 规划命名空间：`app` / `monitoring` / `aiops`

**交付物**
- `kubectl get nodes` 全部 Ready
- 可用 Ingress 转发到业务服务
- `docs/CLUSTER_SETUP.md`（你的操作手册）

**关键技术点（必考）**
- kubeadm 初始化流程与控制平面组件（etcd/kube-apiserver/kube-controller-manager/kube-scheduler）
- CNI 原理、Pod 网络、Service 类型（ClusterIP/NodePort/LoadBalancer/ExternalName）
- kubeconfig、RBAC、证书

---

## 阶段 P2 — 业务应用 + 可观测性（2~3天）

**目标**：跑通一个「AI 推理业务服务」，并搭起监控告警全家桶。

### P2a — AI 业务服务部署
- [ ] 写一个 FastAPI 推理 API（`apps/ai-svc`）：接收文本 → 调 vLLM/模型 → 返回结果
- [ ] 构建 Docker 镜像
- [ ] 部署到集群 `app` 命名空间，Ingress 暴露
- [ ] 模拟高并发/抽风，制造可观测素材

### P2b — 可观测性三件套
- [ ] Prometheus：采集节点/容器/Pod 指标
- [ ] node-exporter、cAdvisor、kube-state-metrics
- [ ] Grafana：Dashboards + 数据源
- [ ] Loki + Promtail：日志采集（业务日志、应用日志）
- [ ] Alertmanager：告警路由 + 通知（Webhook/邮件）
- [ ] 配置告警规则：CPU/Pod 重启/错误率/延迟

**交付物**
- 推理 API 可访问（curl 通）
- Grafana 能看到实时指标 + 日志
- 触发告警 → 能收到通知

**关键点**
- Prometheus pull 模式、metrics 采集路径、alerting rules
- 三支柱：指标（Metrics）日志（Logs）追踪（Traces）——至少前两者
- SLO/SLI 概念（可用性、延迟、错误率、饱和度 USE 方法）

---

## 阶段 P3 — AIOps：AI 驱动智能运维（3~5天，核心亮点）

**目标**：做一个「AI 运维助手」，用大模型自动分析日志 / 定位告警根因 / 给出故障处置建议。

### AIOps 助手架构（可选演进路线）

**路线 A：日志智能分析（起点）**
- 收集 Loki 日志 → 交给 LLM 分析异常 → 返回根因+建议
- 实现：`aiops/log-analyzer`（FastAPI/LangChain 或直接 OpenAI SDK）
- 输入 LogQL / 时间窗；输出自然语言诊断报告

**路线 B：告警根因定位（进阶）**
- Alertmanager Webhook → 触发分析 → 拉取关联指标+日志 → LLM 推理根因+处置步骤
- 接入集群事件、Pod 状态、最近变更（GitOps 提交）

**路线 C：RAG 知识库**
- 把企业运维手册 / 常见故障 / 架构文档做向量化
- 用户/告警问题 → 检索相关知识点 → LLM 结合知识库回答

**路线 D：故障自愈与工具调用（可选进阶）**
- 让 LLM 有工具（kubectl / 重启 / 扩缩容）→ 自动或建议执行
- 强调「人在回路」安全边界（审批后执行）

### 技术栈建议
- 后端：Python FastAPI / LangChain
- LLM：OpenAI / DeepSeek API（你已可访问云端模型，直接用）
- RAG：向量库（Chroma/pgvector）+ embedding
- 触发：Cron 定时巡检、Alertmanager Webhook、Web UI 手动提问

**交付物**
- AIOps 服务部署到集群，Web / API 可问「分析下这个告警为什么发生」
- 演示：制造故障 → 告警 → AI 自动给出根因建议
- `docs/AIOPS_ARCH.md`

**关键点**
- LLM 幻觉的控制：RAG、限定上下文、结构化输出
- 安全：AI 有工具时的权限边界、审计、人在回路
- 成本与延迟：缓存、模型选择、别让 AI 过度分析

---

## 推荐时间线

| 周 | 目标 | 状态 |
|----|------|------|
| 第1周 | P0 + P1：环境 + 集群 | ▢ |
| 第2周 | P2：业务 + 可观测 | ▢ |
| 第3-4周 | P3：AIOps 助手 | ▢ |
| 第5周 | 打磨：文档、Grafana 截图、demo 脚本 | ▢ |

> 建议：即使时间紧，也要保证 P0→P2 完整跑通（这是硬核实力的证明）；
> P3 的 AIOps 是差异化亮点，至少做到「日志分析 + 告警根因」闭环。

---

## 常见问题
- **显存不够**：没有 GPU 也能做，用 CPU 版小模型（如 qwen2.5-1.5b 走 Ollama）模拟推理服务，AIOps 端仍用云端大模型。
- **配置要求**：3 台 VM 各 4C8G 比较稳；若本机内存紧张，可从 2 台（1 master + 1 并入）做起，再扩容。
