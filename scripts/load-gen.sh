#!/usr/bin/env bash
# load-gen.sh — 给 ai-svc 持续制造请求，方便观察指标 / 触发告警 / 生成日志素材
# 用法:  bash load-gen.sh [url] [并发]
URL="${1:-http://localhost/v1/infer}"
CONC="${2:-20}"
echo "向 $URL 并发 $CONC 持续打请求 (Ctrl-C 停止)"
for i in $(seq 1 "$CONC"); do
  (
    while true; do
      curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" \
        -X POST "$URL" -H "Content-Type: application/json" \
        -d "{\"prompt\":\"帮我分析最近一次告警\",\"max_tokens\":32}" \
        >>/tmp/loadgen_$i.log 2>&1
      sleep 0.2
    done
  ) &
done
wait
