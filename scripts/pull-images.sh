#!/usr/bin/env bash
# ============================================================
# pull-images.sh — 一次性拉取本项目所需镜像并推送到 Harbor
# 在 Harbor 机（192.168.243.120，有外网+docker）上以 root 执行。
# 用法: bash pull-images.sh
# 注意: 如果某镜像拉取失败(网络/版本不存在)，脚本会打印但继续，可单独重试。
# ============================================================
set -uo pipefail

HARBOR="reix.harbor.cn"
PROJECT="k8s-ai"            # Harbor 项目名（本 AI 云原生运维项目专用）
USER="${HARBOR_USER:-admin}"
PASS="${HARBOR_PASS:-}"    # 通过环境变量传入，勿硬编码密码

[ -z "$PASS" ] && { echo "请设置环境变量 HARBOR_PASS 提供 Harbor 密码"; exit 1; }

docker login ${HARBOR} -u ${USER} -p ${PASS} || { echo "登录失败"; exit 1; }

# 数组: "源镜像 目标tag"
IMAGES=(
  # ---- ① 业务镜像构建必需（基础镜像）----
  "docker.io/library/python:3.11-slim                          python-3.11-slim"
  # ---- ② Ingress-NGINX controller ----
  "registry.k8s.io/ingress-nginx/controller:v1.11.5             ingress-nginx-controller:v1.11.5"
  # ---- ③ kube-prometheus-stack 组件 ----
  "quay.io/prometheus-operator/prometheus-operator:v0.80.1     prometheus-operator:v0.80.1"
  "quay.io/prometheus-operator/prometheus-config-reloader:v0.80.1  prometheus-config-reloader:v0.80.1"
  "quay.io/prometheus-operator/admission-webhook:v0.80.1       admission-webhook:v0.80.1"
  "quay.io/prometheus/prometheus:v2.55.1                       prometheus:v2.55.1"
  "registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.14.0  kube-state-metrics:v2.14.0"
  "quay.io/prometheus/node-exporter:v1.8.2                     node-exporter:v1.8.2"
  "grafana/grafana:11.4.0                                      grafana:11.4.0"
  # ---- ④ Loki + Promtail（日志）----
  "grafana/loki:3.3.2                                          loki:3.3.2"
  "grafana/promtail:3.3.2                                      promtail:3.3.2"
)

fail=0
for pair in "${IMAGES[@]}"; do
  src="${pair%% *}"
  tag="${pair##* }"
  dst="${HARBOR}/${PROJECT}/${tag}"
  echo "=================================================="
  echo "[1/3] pull  $src"
  docker pull "$src" || { echo "❌ pull 失败: $src"; fail=1; continue; }
  echo "[2/3] tag   -> $dst"
  docker tag "$src" "$dst" || { echo "❌ tag 失败"; fail=1; continue; }
  echo "[3/3] push  $dst"
  docker push "$dst" || { echo "❌ push 失败: $dst"; fail=1; continue; }
  echo "✅ $dst"
done

echo "=================================================="
[ $fail -eq 0 ] && echo "🎉 全部镜像拉取并推送完成" || echo "⚠️ 部分镜像失败，请重试失败项（版本号可能需调整）"
