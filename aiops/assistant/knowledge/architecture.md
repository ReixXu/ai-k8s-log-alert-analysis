# 架构与部署知识（示例知识库）

## ai-svc 推理服务
- ai-svc 是 FastAPI 服务，POST /v1/infer 接受 prompt，返回推理结果。
- 通过内部 Service `ai-svc.app:80` 访问，实际容器端口 8000。
- 暴露 Prometheus 指标（/metrics），含请求计数器与 P99 延迟 histogram。

## 命名空间规划
- app：业务服务
- monitoring：Prometheus/Grafana/Loki/Alertmanager
- aiops：AIOps 智能运维助手

## 崩溃恢复约定
- 业务服务应配置 readiness/liveness 探针，确保流量只在就绪时进入。
- 有状态数据应放 PVC，而非本地临时盘。
