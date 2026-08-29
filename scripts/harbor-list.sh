#!/usr/bin/env bash
# ============================================================
# harbor-list.sh — 查看 Harbor 仓库中的镜像（Harbor REST API v2.0）
# 用法:
#   ./harbor-list.sh                 # 列出所有项目
#   ./harbor-list.sh library         # 列出某项目下的所有镜像(repo)
#   ./harbor-list.sh library myapp   # 列出某镜像的所有 tag
#   ./harbor-list.sh -t              # 列出所有项目下所有镜像的 tags(全量)
# 配置: 通过环境变量覆盖（也可直接改下面的默认值）
# ============================================================
set -euo pipefail

# ---- 配置（改成你的实际值，或 export 覆盖）----
HARBOR_URL="${HARBOR_URL:-https://reix.harbor.cn}"
HARBOR_USER="${HARBOR_USER:-admin}"
HARBOR_PASS="${HARBOR_PASS:-}"    # 通过环境变量传入，勿硬编码密码
# ----------------------------------------------

# 密码为空时提示（避免匿名请求）
[ -z "$HARBOR_PASS" ] && { echo "请设置环境变量 HARBOR_PASS 提供 Harbor 密码"; exit 1; }

# URL 编码仓库名（仓库名里的 / 需编码为 %2F）
urlencode() {
  local s="$1"
  s="${s//\//%2F}"
  echo "$s"
}

api() {  # api <path>
  curl -sk -u "${HARBOR_USER}:${HARBOR_PASS}" "${HARBOR_URL}${1}"
}

case "${1:-}" in
  ""|-h|--help)
    echo "用法: $0 [项目] [镜像] | -t"
    echo "  $0             列出所有项目"
    echo "  $0 <项目>      列出该项目的镜像"
    echo "  $0 <项目> <镜像> 列出该镜像的 tag"
    echo "  $0 -t          列出所有镜像(全项目)"
    ;;
  -t)
    echo "=== 所有项目 ==="
    api "/api/v2.0/projects?page_size=100" | jq -r '.[].name'
    echo
    echo "=== 各项目下的镜像与 tags ==="
    for proj in $(api "/api/v2.0/projects?page_size=100" | jq -r '.[].name'); do
      echo "--- 项目: $proj ---"
      api "/api/v2.0/projects/${proj}/repositories?page_size=100" \
        | jq -r '.[].name' | while read -r repo; do
          echo "  $repo"
          api "/api/v2.0/projects/${proj}/repositories/$(urlencode "$repo")/artifacts?page_size=100" \
            | jq -r '  | .[].tags[]?.name' | sed 's/^/    tag: /'
        done
    done
    ;;
  *)
    if [ $# -eq 1 ]; then
      proj="$1"
      echo "=== 项目 $proj 下的镜像 ==="
      api "/api/v2.0/projects/${proj}/repositories?page_size=100" | jq -r '.[].name'
    else
      proj="$1"; repo="$2"
      echo "=== 镜像 $proj/$repo 的 tags ==="
      api "/api/v2.0/projects/${proj}/repositories/$(urlencode "$proj/$repo")/artifacts?page_size=100" \
        | jq -r '.[].tags[]?.name'
    fi
    ;;
esac
