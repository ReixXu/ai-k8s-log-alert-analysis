# CLUSTER_SETUP — Kubernetes 集群搭建手册（P1）

> 前提：三台 VM 已完成 `init_node.sh` 初始化并互通。
> 本手册记录 kubeadm 搭建的完整命令与要点，供实操参考。

---

## 1. 初始化控制平面（在 Master 上）

```bash
# 需 root。--pod-network-cidr 用 Calico 默认网段 /16
sudo kubeadm init \
  --kubernetes-version=v1.30.x \
  --pod-network-cidr=10.244.0.0/16 \
  --apiserver-advertise-address=192.168.31.101

# 初始化成功后会有 join 命令输出，**务必复制保存**，
# 例如（每次不同，以下为示例）：
#   kubeadm join 192.168.31.101:6443 --token xxxx --discovery-token-ca-cert-hash sha256:xxxx
```

## 2. 配置 kubectl（普通用户）

```bash
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
kubectl version
kubectl get nodes    # 此时 master 应该是 NotReady（还没装网络插件）
```

## 3. 在 Master 安装 Calico（CNI）

```bash
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.29/manifests/calico.yaml
kubectl get pods -n kube-system   # 等 calico 相关 pod Running
kubectl taint nodes --all node-role.kubernetes.io/control-plane-  # 可选：允许 master 也调度业务
```

## 4. Worker 节点加入

在 worker1 / worker2 上执行第 1 步保存的 join 命令。

```bash
sudo kubeadm join 192.168.31.101:6443 --token ... --discovery-token-ca-cert-hash sha256:...
# 若 token 过期: 在 master 上 kubectl create token / kubeadm token create --print-join-command
```

在 Master 验证：

```bash
kubectl get nodes -o wide   # 全部 Ready
```

## 5. MetalLB（LoadBalancer 类型 Service）

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14/metallb-native.yaml
# 配置一个 IP 池（给 LoadBalancer 分配的 IP 段）
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.31.200-192.168.31.220
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: l2
  namespace: metallb-system
EOF
```

## 6. Ingress-NGINX

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.11/manifests/controller-svc-nodeport.yaml
kubectl get pods -n ingress-nginx
```

## 7. 存储：local-path（简单）或 Longhorn（企业级）

```bash
# local-path（建议先跑通）
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.26/deploy/local-path-storage.yaml
kubectl get sc   # 应看到 local-path
```

## 8. 命名空间规划

```bash
kubectl create ns app
kubectl create ns monitoring
kubectl create ns aiops
```

---

## 验收标准
- [ ] `kubectl get nodes` 全部 Ready
- [ ] `kubectl get pods -n kube-system` 各组件 Running
- [ ] `kubectl get sc` 有存储类
- [ ] 创建一个 Nginx 测试 Deployment + NodePort/LoadBalancer，浏览器能打开

## 相关知识（集群原理）
- 控制平面 4 组件 + etcd 的作用
- Pod 网络 / CNI / Service 三种类型 / 网络策略
- kubeadm init 的完整流程（ca → 静态 pod → 生成 join）
- kubeconfig、证书体系、RBAC
- 静态 Pod 与 Pod 创建流程（workqueue 机制）
