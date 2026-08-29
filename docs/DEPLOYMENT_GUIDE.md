# 项目部署指南（完整步骤）

> AI 驱动的云原生智能运维平台 —— 从零到完整闭环的部署手册。
> 环境：3 节点 K8s v1.36.3（Rocky Linux 10.2）+ Harbor 私有仓库 + 1 台 NFS 存储机。

---

## 〇、架构总览

```
客户端 → MetalLB(192.168.243.200-220) → Ingress-NGINX(.201)
  ├→ ai-svc (FastAPI 推理 API) → mock-vllm（业务层）
  ├→ Grafana (.202) ← Prometheus（指标）+ Loki（日志）（可观测层）
  └→ Alertmanager → AIOps 助手（DeepSeek LLM + RAG + 集群上下文）
                     ├→ 钉钉 / 企业微信 / 邮件（告警 + AI 分析通知）
                     └→ 恢复通知（✅ 已恢复）
```

## 一、环境清单

| 角色 | 主机 | IP | 说明 |
|------|------|-----|------|
| K8s 控制平面 | k8s-master | 192.168.243.121 | kubeadm 集群 v1.36.3 |
| K8s 工作节点 | k8s-node1 | 192.168.243.122 | |
| K8s 工作节点 | k8s-node2 | 192.168.243.123 | |
| Harbor + NFS | harbor | 192.168.243.120 | 镜像仓库 reix.harbor.cn + NFS 存储 |

**命名空间**：`app`（业务）、`monitoring`（可观测）、`aiops`（AIOps 助手）、`nfs-storageclass`（存储）、`ingress-nginx`、`metallb-system`、`argocd`（可选）

---

## 二、部署步骤（按阶段）

### 阶段 0：基础环境（存储 + 网络 + 命名空间）

#### 0.1 命名空间
```bash
kubectl create ns app
kubectl create ns monitoring
kubectl create ns aiops
```

#### 0.2 NFS 存储（Harbor 机 192.168.243.120）
```bash
# Harbor 机上
dnf install -y nfs-utils
systemctl enable --now nfs-server rpcbind
mkdir -p /nfsdata/ai-cloud-native-ops
chown -R nobody /nfsdata/ai-cloud-native-ops/
chmod -R 777 /nfsdata/ai-cloud-native-ops/
cat > /etc/exports <<'EOF'
/nfsdata/ai-cloud-native-ops *(rw,no_root_squash,no_all_squash,sync)
EOF
exportfs -arv && systemctl restart nfs-server
showmount -e 127.0.0.1   # 验证
```

#### 0.3 三台 K8s 节点装 NFS 客户端
```bash
# 每台节点执行
dnf install -y nfs-utils
systemctl enable --now rpcbind
showmount -e 192.168.243.120   # 验证互通
```

#### 0.4 部署 nfs-client-provisioner（动态供给）
```bash
# 先建 Harbor 镜像拉取凭证
kubectl create secret docker-registry harbor-secret -n nfs-storageclass \
  --docker-server=reix.harbor.cn --docker-username=admin --docker-password='<密码>'

# 应用清单（k8s/storage/nfs-provisioner.yaml）
kubectl apply -f k8s/storage/nfs-provisioner.yaml
kubectl get sc          # 应看到 nfs-client (default)
kubectl get pods -n nfs-storageclass   # Running
```

#### 0.5 部署 MetalLB
```bash
kubectl apply -f metallb-native.yaml   # 课堂代码 6/metallb-native.yaml
kubectl apply -f k8s/networking/metallb-config.yaml   # IP 池 192.168.243.200-220
kubectl get pods -n metallb-system     # controller + speaker×3 Running
```

#### 0.6 部署 Ingress-NGINX
```bash
kubectl apply -f ingress-nginx.yaml    # 镜像已改为 reix.harbor.cn/k8s/ingress-nginx/*
kubectl get svc -n ingress-nginx       # LoadBalancer 拿到 .201
```

### 阶段 1：业务服务（ai-svc + mock-vllm）

#### 1.1 构建并推送镜像（Harbor 机）
```bash
# 把 apps/ 源码传到 Harbor 机
scp -r apps root@192.168.243.120:/root/

# Harbor 机上
cd /root/apps
docker build -t reix.harbor.cn/k8s-ai/ai-svc:latest ./ai-svc
docker build -t reix.harbor.cn/k8s-ai/mock-vllm:latest ./mock-vllm
docker login reix.harbor.cn -u admin -p '<密码>'
docker push reix.harbor.cn/k8s-ai/ai-svc:latest
docker push reix.harbor.cn/k8s-ai/mock-vllm:latest
```

#### 1.2 部署到集群
```bash
# 业务命名空间建 Harbor 凭证 + SA 注入
kubectl create secret docker-registry harbor-secret -n app \
  --docker-server=reix.harbor.cn --docker-username=admin --docker-password='<密码>'
kubectl patch serviceaccount default -n app -p '{"imagePullSecrets": [{"name": "harbor-secret"}]}'

kubectl apply -f k8s/app/vllm-svc.yaml
kubectl apply -f k8s/app/ai-svc.yaml
kubectl apply -f k8s/app/ai-svc-lb.yaml    # LoadBalancer 直连 .200

# 验证
curl -s http://192.168.243.200/healthz
curl -s -X POST http://192.168.243.200/v1/infer \
  -H "Content-Type: application/json" -d '{"prompt":"测试"}' 
```

### 阶段 2：可观测（Prometheus + Grafana + Loki + Promtail）

#### 2.1 kube-prometheus-stack（Helm）
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade --install kube-prom prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  --set grafana.service.type=LoadBalancer \
  --set grafana.adminPassword='admin123' --timeout 10m
kubectl get pods -n monitoring    # 全部 Running
```

#### 2.2 采集业务指标（ServiceMonitor）
```bash
kubectl apply -f monitoring/ai-svc-servicemonitor.yaml
# 前提: ai-svc-metrics Service 的端口有 name: metrics（已在清单中）
```

#### 2.3 Loki（裸清单单体 + NFS）
```bash
kubectl apply -f k8s/monitoring/loki-standalone.yaml
kubectl get pods -n monitoring | grep loki   # Running
kubectl get pvc -n monitoring | grep loki    # Bound（NFS 动态供给）
```

#### 2.4 Promtail（日志采集）
```bash
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install promtail grafana/promtail --namespace monitoring \
  --set config.lokiAddress=http://loki.monitoring:3100/loki/api/v1/push --timeout 10m

# ⚠️ 关键：必须给 Promtail DaemonSet 挂载宿主 docker 数据目录（否则软链断裂，日志采集不到）
kubectl patch ds promtail -n monitoring --type=json -p='[
  {"op":"add","path":"/spec/template/spec/volumes/-","value":{"name":"dockerdata","hostPath":{"path":"/data/docker/containers"}}},
  {"op":"add","path":"/spec/template/spec/containers/0/volumeMounts/-","value":{"name":"dockerdata","mountPath":"/data/docker/containers","readOnly":true}}
]'

# ⚠️ 关键：chart 默认推送到 loki-gateway（不存在），需改成真实 Loki 地址
# 修改 secret promtail 里的 promtail.yaml: clients.url → http://loki.monitoring:3100/loki/api/v1/push

# 验证日志链路
curl -s --get 'http://10.13.139.181:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={namespace="app"}' --data-urlencode 'limit=5' | jq '.data.result'
```

### 阶段 3：AIOps 助手（告警规则 + 分析 + 通知）

#### 3.1 告警规则
```bash
kubectl apply -f monitoring/ai-svc-alerts.yaml
curl -s http://10.1.171.25:9090/api/v1/rules | jq '.data.groups[] | select(.name=="ai-svc.rules") | .rules[].name'
```

#### 3.2 Alertmanager 路由到 AIOps
```bash
# 启用 AlertmanagerConfig selector
kubectl patch alertmanager kube-prom-kube-prometheus-alertmanager -n monitoring --type=merge \
  -p '{"spec":{"alertmanagerConfigSelector":{"matchLabels":{"release":"kube-prom"}}}}'

# 直接改 Alertmanager secret（绕开 CRD 的 namespace 限制）
kubectl get secret alertmanager-kube-prom-kube-prometheus-alertmanager -n monitoring \
  -o jsonpath='{.data.alertmanager\.yaml}' | base64 -d > /tmp/am.yaml
# 编辑: route.routes 加 {receiver: aiops-webhook, matchers: [severity="critical"], continue: true}
# 编辑: receivers 加 {name: aiops-webhook, webhook_configs: [{url: http://aiops-assistant.aiops/api/alert, send_resolved: true}]}
kubectl create secret generic alertmanager-kube-prom-kube-prometheus-alertmanager -n monitoring \
  --from-file=alertmanager.yaml=/tmp/am.yaml --dry-run=client -o yaml | kubectl apply -f -
kubectl delete pod -n monitoring alertmanager-kube-prom-kube-prometheus-alertmanager-0
```

#### 3.3 AIOps 助手
```bash
# ① Secret（LLM Key + 通知渠道）
kubectl create secret generic aiops-secrets -n aiops --from-literal=llm_api_key='<DeepSeek Key>'
kubectl create secret generic aiops-notify -n aiops \
  --from-literal=dingtalk_webhook='<钉钉webhook>' \
  --from-literal=wecom_webhook='<企微webhook>' \
  --from-literal=smtp_host='smtp.yeah.net' \
  --from-literal=smtp_port='465' \
  --from-literal=smtp_user='<邮箱>' \
  --from-literal=smtp_pass='<授权码>' \
  --from-literal=mail_to='<收件人>'

# ② aiops 命名空间 Harbor 凭证
kubectl create secret docker-registry harbor-secret -n aiops \
  --docker-server=reix.harbor.cn --docker-username=admin --docker-password='<密码>'
kubectl patch serviceaccount default -n aiops -p '{"imagePullSecrets": [{"name": "harbor-secret"}]}'

# ③ 构建镜像（Harbor 机）
cd /root
docker build -t reix.harbor.cn/k8s-ai/aiops-assistant:latest ./assistant
docker push reix.harbor.cn/k8s-ai/aiops-assistant:latest

# ④ 部署
kubectl apply -f k8s/aiops/aiops-assistant.yaml
kubectl rollout status deployment/aiops-assistant -n aiops
curl -s http://<aiops-svc-ip>/healthz   # {"status":"ok"}
```

### 阶段 4：验收（故障注入闭环测试）

```bash
# ① 注入故障
kubectl scale deployment ai-svc -n app --replicas=0

# ② 等待告警触发（for: 2m）
sleep 150
curl -s 'http://10.1.171.25:9090/api/v1/alerts' | jq '.data.alerts[] | select(.labels.alertname=="AiSvcGone") | {state}'   # firing

# ③ 看 AIOps 收到 + 分析 + 通知
kubectl logs -n aiops deploy/aiops-assistant --tail=30 | grep -E "ANALYSIS|notify"

# ④ 恢复服务 → 恢复通知
kubectl scale deployment ai-svc -n app --replicas=2
sleep 120
kubectl logs -n aiops deploy/aiops-assistant --tail=20 | grep -E "resolved|notify-resolved"
# 钉钉/企微/邮箱应收到「✅ 告警已恢复」
```

---

## 三、验收清单

- [ ] `kubectl get nodes` 全部 Ready
- [ ] `kubectl get sc` 有 nfs-client (default)
- [ ] `kubectl get svc -A` 有 .200/.201/.202 三个 LoadBalancer
- [ ] `curl http://192.168.243.200/v1/infer` 推理成功
- [ ] Prometheus 查询 `ai_svc_requests_total` 有数据
- [ ] Loki 查询 `{namespace="app"}` 有日志
- [ ] `kubectl get pods -n aiops` Running，/healthz ok
- [ ] 故障注入 → 三渠道收到「告警 + AI 分析」+「✅ 已恢复」
