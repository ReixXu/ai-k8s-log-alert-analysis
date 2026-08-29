#!/usr/bin/env bash
# =====================================================================
# init_node.sh — 云原生集群节点一键初始化 (Ubuntu 22.04 / 24.04)
# 需 root 或 sudo。适用于 Master 与 Worker 每台节点。
# 用法:  sudo bash init_node.sh
# =====================================================================
set -euo pipefail

# --- 可配置区 ---
K8S_VERSION="1.30"            # 大版本，用于 kubectl/kubeadm/kubelet
ROLE="${1:-worker}"           # master | worker（仅影响是否打印 join 提示信息）
# ---------------

log()  { echo -e "\033[1;34m[+] $*\033[0m"; }
warn() { echo -e "\033[1;33m[!] $*\033[0m"; }

[[ $EUID -ne 0 ]] && { echo "请用 root 或 sudo 运行"; exit 1; }

log "== 1/6 设置主机名映射 (hosts) =="
cat >> /etc/hosts <<'EOF'
# K8s cluster
192.168.31.101  master.local master
192.168.31.102  worker1.local worker1
192.168.31.103  worker2.local worker2
EOF

log "== 2/6 关闭 swap & 加载内核模块 =="
swapoff -a
sed -i '/ swap / s/^/#/g' /etc/fstab || true

cat > /etc/modules-load.d/k8s.conf <<'EOF'
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter

cat > /etc/sysctl.d/k8s.conf <<'EOF'
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sysctl --system

log "== 3/6 安装基础工具 =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y curl git jq htop vim net-tools ca-certificates gnupg lsb-release

log "== 4/6 安装 containerd (容器运行时) =="
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -y
apt-get install -y containerd.io
# 使用 containerd 默认配置并启用 systemd cgroup
containerd config default | \
  sed 's/SystemdCgroup = false/SystemdCgroup = true/' \
  > /etc/containerd/config.toml
systemctl enable --now containerd

log "== 5/6 安装 kubeadm / kubelet / kubectl =="
curl -fsSL https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/deb/Release.key \
  | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo \
  "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] \
  https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/deb/ /" \
  > /etc/apt/sources.list.d/kubernetes.list
apt-get update -y
apt-get install -y kubelet kubeadm kubectl
apt-mark hold kubelet kubeadm kubectl

log "== 6/6 完成 =="
echo -e "\n节点基础环境初始化完成。"
echo "  集群版本: v${K8S_VERSION}"
echo "  建议: 重启后再进入 P1 集群初始化。"
echo "  角色  : $ROLE"
if [[ "$ROLE" == "master" ]]; then
  warn "Master 节点下一步在 Master 上执行: kubeadm init ..."
fi
