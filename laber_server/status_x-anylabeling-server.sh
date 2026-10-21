#!/usr/bin/env bash
set -Eeuo pipefail

CONTAINER_NAME="${ANYLABEL_CONTAINER:-anylabel}"
container_running="$(docker inspect --format '{{.State.Running}}' "$CONTAINER_NAME" 2>&1)" || {
    echo "Unable to inspect Docker container $CONTAINER_NAME: $container_running" >&2
    exit 1
}
if [[ "$container_running" != "true" ]]; then
    echo "stopped"
    exit 0
fi

docker exec "$CONTAINER_NAME" bash -lc '
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

pid_file=/tmp/x-anylabeling-server.pid
if [[ -s "$pid_file" ]]; then
    server_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ "$server_pid" =~ ^[0-9]+$ ]] && kill -0 "$server_pid" 2>/dev/null; then
        server_state="$(ps -p "$server_pid" -o stat= 2>/dev/null || true)"
        server_state="${server_state//[[:space:]]/}"
        server_args="$(ps -p "$server_pid" -o args= 2>/dev/null || true)"
        if [[ "$server_state" != Z* && "$server_args" == *"uvicorn app.main:app"* ]]; then
            echo "running"
            exit 0
        fi
    fi
fi
server_pid="$(find_server_pid)"
if [[ -n "$server_pid" ]]; then
    echo "running"
    exit 0
fi
echo "stopped"
'
