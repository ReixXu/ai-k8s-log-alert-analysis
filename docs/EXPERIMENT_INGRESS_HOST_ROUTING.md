# 实验笔记：Ingress 的 Host 路由机制（L7 负载均衡）

> 实验现象：同一 IP，不同访问方式，结果截然不同。

## 一、实验现象

| 访问方式 | 地址 | 结果 |
|---------|------|------|
| 域名访问 | `http://test.ops.local`（hosts 解析到 192.168.243.201）| ✅ 200，Nginx 欢迎页 |
| 裸 IP 访问 | `http://192.168.243.201` | ❌ 404 Not Found |

**关键点**：两种访问指向的是**同一个 IP**（Ingress-NGINX 的 LoadBalancer VIP `192.168.243.201`），唯一区别是请求携带的 **Host 头**。

## 二、原因分析：Ingress 基于 Host 路由

Ingress-NGINX 是**七层（L7/HTTP）负载均衡**，它根据 HTTP 请求中的 Host 头和 URL 路径决定转发目标：

```
浏览器请求
   │  Host: test.ops.local   ← 域名访问（图1）
   ▼
Ingress-NGINX ──匹配 Ingress 规则──►  test-ingress-svc ──► nginx Pod ──► 200 欢迎页
   │
   │  Host: 192.168.243.201  ← 裸 IP 访问（图2）
   ▼
Ingress-NGINX ──无任何规则匹配──► 返回 404（nginx 默认无匹配响应）
```

对应的 Ingress 规则：

```yaml
spec:
  ingressClassName: nginx
  rules:
    - host: test.ops.local        # 只匹配这个域名
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: test-ingress-svc
                port:
                  number: 80
```

- 图1：Host=`test.ops.local` **命中规则** → 转发后端 → 200
- 图2：Host=`192.168.243.201` **无规则匹配** → 404（Ingress 默认行为）

## 三、类比理解

把 Ingress-NGINX 想成**前台接待**：
- 「我找 test.ops.local 部门」→ 知道路线，带到办公室 ✅
- 「我要进这栋楼」（只给 IP）→ 不知道找谁 → 拒绝 ❌

Host 头就是"你要找哪个部门"的关键信息。

## 四、核心知识点

1. **Ingress 是 L7 负载均衡**：基于 HTTP 层（Host/Path）路由，区别于 Service 的 L4（IP:Port）转发。
2. **一个 Ingress Controller 可服务多个域名**：`test.ops.local`、`ai.ops.local`、`api.ops.local` 各配规则，共用一个 VIP。
3. **Host 不匹配默认 404**：可通过 `default-backend` 自定义兜底页。
4. **生产用域名而非裸 IP**：裸 IP 无法触发 L7 路由；这也是为什么线上环境都配 DNS。
5. **catch-all 规则**：Ingress 规则省略 `host` 字段则匹配任意 Host，但不建议生产使用（易误路由）。

## 五、扩展：按 Path 路由（进阶）

Ingress 还能基于路径分流，同一域名不同路径到不同服务：

```yaml
spec:
  rules:
    - host: api.ops.local
      http:
        paths:
          - path: /infer          # → 推理服务
            pathType: Prefix
            backend:
              service: { name: ai-svc, port: { number: 80 } }
          - path: /metrics        # → 监控服务
            pathType: Prefix
            backend:
              service: { name: prometheus, port: { number: 9090 } }
```

## 六、本实验在项目中的意义

- 证明 MetalLB（L2/四层入口）与 Ingress（L7/七层路由）的**分层协作**：MetalLB 给 Ingress 分配 VIP，Ingress 做 HTTP 路由。
- 后续本项目统一入口：`ai.ops.local` → ai-svc 推理 API，一条 Ingress 规则即可。
