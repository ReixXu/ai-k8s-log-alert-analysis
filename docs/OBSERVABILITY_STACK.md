# 可观测性栈：指标（Metrics）+ 日志（Logs）

> 本项目的可观测性设计，以及 Prometheus / Loki 的分工与协作。

## 一、可观测性三支柱（Observability Three Pillars）

| 支柱 | 回答的问题 | 本项目实现 |
|------|-----------|-----------|
| **指标 Metrics** | 「发生了什么异常（量化）」| Prometheus + node-exporter + kube-state-metrics |
| **日志 Logs** | 「为什么（细节）」| Loki + Promtail |
| **追踪 Traces** | 「一次请求的完整路径」| （本项目暂未实现，可选扩展 Jaeger/Tempo）|

> 说明：三支柱解决不同维度问题，成熟系统通常三样都上；本项目至少覆盖前两者。

## 二、架构图

```
┌─────────────────────────────────────┐
│           Grafana（统一展示层）        │  ← LoadBalancer 192.168.243.202
├──────────────┬──────────────────────┤
│  Prometheus  │       Loki           │
│  （指标）     │       （日志）         │
│  时序数据     │      文本数据          │
└──────────────┴──────────────────────┘
       ↑                  ↑
   node-exporter      Promtail（DaemonSet）
   kube-state-metrics  /var/log/pods/*
   ai-svc /metrics
```

## 三、Prometheus（指标）vs Loki（日志）—— 关键区别

| 维度 | Prometheus | Loki |
|------|-----------|------|
| 数据类型 | 时间序列（数值） | 日志流（文本） |
| 数据模型 | `metric名{标签}` + 值 | `{标签}` + 日志行 |
| 查询语言 | PromQL | LogQL |
| 索引策略 | 索引所有标签 | **只索引标签，不索引正文** |
| 存储 | TSDB（时序库） | chunks + index（对象/文件） |
| 典型用途 | CPU/延迟/错误率 | 具体报错内容 |

### Loki 的核心设计

- Loki **只索引标签，不索引日志全文**（对比 ELK 的 Elasticsearch 全文索引）
- 日志正文压缩后按块存储，查询时才解压匹配
- 因此 **Loki 极省内存和存储**，适合 K8s 日志量大、查询少的场景
- 与 Prometheus 共用**标签体系**，Grafana 里指标+日志联动

## 四、数据流

```
业务 Pod（ai-svc）
   │ stdout/stderr 结构化日志
   ▼
/var/log/pods/*/*.log （节点磁盘）
   ▼
Promtail（DaemonSet，读日志文件 + 标签重写）
   ▼ push API
Loki（存储 chunks/index，落 NFS PVC）
   ▼ LogQL 查询
Grafana / AIOps 助手
```

## 五、本项目的存储决策

- **Loki 用 filesystem + NFS PVC**（`loki-pvc` → `nfs-client` StorageClass → Harbor 机 `/nfsdata/ai-cloud-native-ops`）
- **为什么不用对象存储（MinIO）**：
  - 学习/中小规模，filesystem 足够
  - 单体模式无 HA 需求
  - 4G 内存节点再跑 MinIO 会紧张
- **生产演进方向**：规模扩大后切到对象存储（S3/MinIO），Loki 支持 SimpleScalable/Distributed 模式

## 六、组件版本与兼容性

| 组件 | 版本 | 兼容性 |
|------|------|--------|
| Prometheus（kube-prometheus-stack） | operator 88.5.4 | 独立体系，与 Loki 无冲突 |
| Loki | 3.3.2 | 与 Promtail 同版本 |
| Promtail | 3.3.2 | push API 稳定，同版本最稳妥 |

> 要点：Prometheus 和 Loki 是**两套独立体系**（指标 vs 日志），数据格式不冲突，唯一交集是 Grafana 统一展示。

## 七、在 AIOps 中的角色（P3 铺垫）

AIOps 助手做根因分析时，需要**同时消费两类数据**：
- `ContextCollector.query_metric()` → Prometheus 指标（量化异常）
- `ContextCollector.fetch_logs()` → Loki 日志（定位细节）

两者结合 + LLM 推理 = 完整的智能根因分析。
