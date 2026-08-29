FROM python:3.11-slim

# 安装 kubectl（供 ContextCollector 查询集群状态，与 K8s 版本匹配）
RUN apt-get update && apt-get install -y curl ca-certificates && \
    curl -fsSL -o /usr/local/bin/kubectl \
      "https://dl.k8s.io/release/v1.36.3/bin/linux/amd64/kubectl" && \
    chmod +x /usr/local/bin/kubectl && \
    apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
