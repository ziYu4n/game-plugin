#!/bin/bash
set -u

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
  SOURCE_DIR="$(cd "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  case "$SOURCE" in
    /*) ;;
    *) SOURCE="$SOURCE_DIR/$SOURCE" ;;
  esac
done
ROOT="$(cd "$(dirname "$SOURCE")" && pwd)"
PID_FILE="$ROOT/logs/gui.pid"
URL_FILE="$ROOT/logs/gui.url"
WEB_LOG="$ROOT/logs/web-launch.log"
WEB_ERR="$ROOT/logs/web-launch-error.log"
LAUNCH_LABEL="local.game-plugin.web"

mkdir -p "$ROOT/logs"

open_existing() {
  [ -f "$PID_FILE" ] && [ -f "$URL_FILE" ] || return 1
  pid="$(tr -dc '0-9' < "$PID_FILE")"
  url="$(head -n 1 "$URL_FILE")"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null || return 1
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  case "$command_line" in
    *"$ROOT/gui.py"*) ;;
    *) return 1 ;;
  esac
  case "$url" in
    http://127.0.0.1:*|http://localhost:*) ;;
    *) return 1 ;;
  esac
  /usr/bin/open "$url"
  return 0
}

if open_existing; then
  exit 0
fi

rm -f "$PID_FILE" "$URL_FILE"
cd "$ROOT"
/bin/launchctl remove "$LAUNCH_LABEL" >/dev/null 2>&1 || true
if ! /bin/launchctl submit -l "$LAUNCH_LABEL" \
  -o "$WEB_LOG" -e "$WEB_ERR" -- \
  /usr/bin/python3 "$ROOT/gui.py" --serve; then
  echo "网页后台服务提交失败，请查看：$WEB_ERR"
  read -r -p "按回车关闭窗口"
  exit 1
fi

for _ in $(seq 1 50); do
  if [ -f "$URL_FILE" ]; then
    url="$(head -n 1 "$URL_FILE")"
    case "$url" in
      http://127.0.0.1:*|http://localhost:*)
        /usr/bin/open "$url"
        exit 0
        ;;
    esac
  fi
  sleep 0.1
done

echo "网页服务没有正常启动，请查看：$WEB_LOG"
read -r -p "按回车关闭窗口"
exit 1
