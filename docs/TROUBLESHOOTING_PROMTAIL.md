# 排障记录：Promtail 日志采集链路打通（含软链断裂根因）

> 从「Promtail 未就绪 / Loki 无日志」到「完整标签日志入库」的完整排障过程。
> 本项目最典型、最有参考价值的排障案例。

## 一、现象

- Promtail Pod `0/1 Running`（readiness probe 500）
- Loki 查询 `{namespace="app"}` 结果为空
- Promtail 日志大量 `failed to tail file, stat failed ... no such file or directory`

## 二、排障过程（分层定位法）

### 第 1 层：确认 Loki 本身正常
- 手动 push 测试：`curl -X POST .../loki/api/v1/push` → 成功
- 手动查询 `{job="manual-test"}` → 能查到
- **结论**：Loki 存储/查询 OK，问题在采集端

### 第 2 层：确认 Promtail 推送链路正常
- 静态采集测试（`static_configs` + `/var/log/messages`）→ 成功入库
- **结论**：Promtail → Loki 推送 OK

### 第 3 层：定位到「服务发现/路径」问题
- `promtail_targets_active_total 16`（服务发现正常）
- `promtail_files_active_total 0`（**没有任何文件在 tail**）
- `Adding target key="/var/log/pods///*.log"`（`__path__` 生成错误）

### 第 4 层（最终根因）：软链断裂
- 节点上 `ls -la /var/log/pods/app_ai-svc-*/ai-svc/` 发现：
  ```
  lrwxrwxrwx 1.log -> /data/docker/containers/<容器ID>/<容器ID>-json.log
  ```
- **日志文件是软链**，真实文件在 `/data/docker/containers/`
- Promtail 容器**没挂载 `/data/docker/containers`** → 软链目标不可见 → stat failed

## 三、修复

1. **给 Promtail DaemonSet 挂载宿主机 docker 数据目录**：
   ```bash
   kubectl patch ds promtail -n monitoring --type=json -p='[
     {"op":"add","path":"/spec/template/spec/volumes/-","value":{"name":"dockerdata","hostPath":{"path":"/data/docker/containers"}}},
     {"op":"add","path":"/spec/template/spec/containers/0/volumeMounts/-","value":{"name":"dockerdata","mountPath":"/data/docker/containers","readOnly":true}}
   ]'
   ```
2. **双 job 配置**（`kubernetes-pods` 带完整标签 + `docker-containers` 兜底）

## 四、修复后验证

```
promtail_files_active_total 67
promtail_sent_bytes_total 408507
```

查询 `{namespace="app"}` 返回：
```json
{
  "stream": {
    "app": "ai-svc",
    "container": "ai-svc",
    "namespace": "app",
    "pod": "ai-svc-6d57868c6b-tzzfz",
    "filename": "/var/log/pods/app_ai-svc-.../ai-svc/3.log"
  },
  "values": [["...", "{\"log\":\"INFO: ... GET /healthz HTTP/1.1 200 OK...}"]]
}
```

## 五、核心知识点

1. **K8s 容器日志软链机制**：`/var/log/pods/<ns>_<pod>_<uid>/<container>/` 下是软链 → 真实 docker 日志目录。采集器（Promtail/fluentd）必须能看到真实路径，否则 stat 失败。
2. **Promtail readiness 机制**：`/ready` 在「没有活跃文件 target」时返回 500 → Pod 未就绪。files_active 是核心健康指标。
3. **分层排障法**：先验证后端（Loki 收/查）→ 再验证中间（Promtail 推送）→ 最后定位采集端（target/路径/挂载）。
4. **双 job 设计**：带标签的 kubernetes-pods + 无标签兜底 docker-containers，兼顾「可查询性」和「可靠性」。
5. **docker vs containerd 日志路径差异**：docker 数据目录可自定义（本环境 `/data/docker/containers`），采集器挂载需与实际一致。

## 六、踩过的坑（避免重蹈）

| 坑 | 教训 |
|----|------|
| `file_targets` 语法 | 那是 Grafana Alloy 的，Promtail 3.x 不认 → 配置解析失败 CrashLoop |
| 多 source_labels 拼接 `__path__` | Promtail relabel 的 `$n` 行为与预期不符，生成 `///*.log` |
| 只关注 stat failed 噪音 | 真正的根因（挂载缺失）被大量噪音掩盖，应该早看 `/data/docker` 是否存在 |
