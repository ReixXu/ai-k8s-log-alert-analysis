# 一键部署所有清单的脚本（方便手动 GitOps，不依赖 ArgoCD）
# 用法:  bash scripts/deploy-all.sh
set -e
echo "== 部署 app =="
kubectl apply -f k8s/app/
echo "== 部署 aiops =="
kubectl apply -f k8s/aiops/ 2>/dev/null || true
echo "部署完成。"
kubectl get pods -A | grep -E "app|aiops" || true
