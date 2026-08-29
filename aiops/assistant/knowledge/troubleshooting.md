# 常见故障排查手册（示例知识库，供 RAG 检索）

## 节点 NotReady
- 检查 kubelet 状态：`systemctl status kubelet`，日志 `/var/log/kubelet.log`
- 查看证书是否过期：`openssl x509 -in /etc/kubernetes/kubelet-client-current.pem -text | grep -A1 Not`
- 若 CNI 网络插件未就绪会导致 NotReady。

## Pod 一直 Pending
- 一般 pending 是因为调度不成功：
  - 资源不足：`kubectl describe pod <name> | grep -A5 Events` 看调度事件
  - 有污点 taint：`kubectl get nodes -o wide` 看 Taints
  - 存储卷不可用（PVC pending）
- 解决方案：扩容节点、去掉 NoSchedule taint、或删除不可用的 PVC。

## Pod CrashLoopBackOff / 频繁重启
- `kubectl logs <pod> --previous` 看上次崩溃日志
- 常见原因：启动参数错、连不上依赖(数据库/配置中心)、OOMKilled
- 检查 limits：`kubectl describe pod` 的 container status 里 ExitCode 和 reason。

## 服务超时 / 延迟升高
- 用 Prometheus 看 `rate(ai_svc_request_duration_seconds_bucket[5m])` 的 P99
- 排查是否 CPU 打满、依赖的模型服务变慢、连接池打满
- 扩容副本或调大并发参数。

## 磁盘空间满
- `df -h` 定位，`du -sh * | sort -h` 找大目录
- 清理 Docker：`docker system prune`，或配置日志轮转
- containerd 镜像/日志占用：定期清理 /var/lib/containerd。
