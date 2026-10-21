#!/usr/bin/env bash
set -Eeuo pipefail

CONTAINER_NAME="${ANYLABEL_CONTAINER:-anylabel}"

# Only grant the container's local root user X access when this host has an
# active X session. The API server normally does not need a display.
if [[ -n "${DISPLAY:-}" ]] && command -v xhost >/dev/null 2>&1; then
    xhost +SI:localuser:root >/dev/null 2>&1 || true
fi

container_running="$(docker inspect --format '{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || true)"
if [[ "$container_running" != "true" ]]; then
    docker start "$CONTAINER_NAME" >/dev/null
fi

# Keep docker exec attached to this wrapper process so label_server can track
# it, while running Uvicorn in its own container-side process group. No -it is
# used, so this also works when label_server runs under systemd without a TTY.
exec docker exec "$CONTAINER_NAME" bash -lc '
set -Eeuo pipefail
cd /home/znzz/ma/X-AnyLabeling-Server
pid_file=/tmp/x-anylabeling-server.pid

find_server_pid() {
    while read -r process_pid process_state process_name process_args; do
        if [[ "$process_state" != Z* \
            && "$process_name" =~ ^(python[0-9.]*|uvicorn)$ \
            && "$process_args" == *"uvicorn app.main:app --host 0.0.0.0 --port 8000"* ]]; then
            printf "%s\n" "$process_pid"
            break
        fi
    done < <(ps -eo pid=,stat=,comm=,args=)
}

if [[ -s "$pid_file" ]]; then
    old_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ "$old_pid" =~ ^[0-9]+$ ]] && kill -0 "$old_pid" 2>/dev/null; then
        old_state="$(ps -p "$old_pid" -o stat= 2>/dev/null || true)"
        old_state="${old_state//[[:space:]]/}"
        old_args="$(ps -p "$old_pid" -o args= 2>/dev/null || true)"
        if [[ "$old_state" != Z* && "$old_args" == *"uvicorn app.main:app"* ]]; then
            echo "X-AnyLabeling-Server is already running (pid $old_pid)"
            exit 0
        fi
    fi
    rm -f "$pid_file"
fi

# Avoid launching a second copy if Uvicorn was started manually before this
# control service was installed.
existing_pid="$(find_server_pid)"
if [[ -n "$existing_pid" ]]; then
    echo "X-AnyLabeling-Server is already running (pid $existing_pid)"
    exit 0
fi

setsid uvicorn app.main:app --host 0.0.0.0 --port 8000 &
server_pid=$!
printf "%s\n" "$server_pid" > "$pid_file"

cleanup() {
    exit_code=$?
    trap - EXIT TERM INT
    if kill -0 "$server_pid" 2>/dev/null; then
        kill -TERM -- "-$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
    fi
    rm -f "$pid_file"
    exit "$exit_code"
}
trap cleanup EXIT
trap "exit 143" TERM
trap "exit 130" INT

wait "$server_pid"
'
