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
set -Eeuo pipefail
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

is_alive() {
    local pid="$1"
    local state
    state="$(ps -p "$pid" -o stat= 2>/dev/null || true)"
    state="${state//[[:space:]]/}"
    [[ -n "$state" && "$state" != Z* ]]
}

server_pid=""
managed_group=false
if [[ -s "$pid_file" ]]; then
    candidate_pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ "$candidate_pid" =~ ^[0-9]+$ ]] && is_alive "$candidate_pid"; then
        candidate_args="$(ps -p "$candidate_pid" -o args= 2>/dev/null || true)"
        if [[ "$candidate_args" == *"uvicorn app.main:app"* ]]; then
            server_pid="$candidate_pid"
            candidate_pgid="$(ps -p "$candidate_pid" -o pgid= 2>/dev/null || true)"
            candidate_pgid="${candidate_pgid//[[:space:]]/}"
            if [[ "$candidate_pgid" == "$candidate_pid" ]]; then
                managed_group=true
            fi
        fi
    fi
    if [[ "$managed_group" != true ]]; then
        rm -f "$pid_file"
    fi
fi

if [[ -z "$server_pid" ]]; then
    # A manually started Uvicorn process has no dedicated process group/PID
    # file. Signal only that exact Python/Uvicorn PID.
    server_pid="$(find_server_pid)"
    if [[ -z "$server_pid" ]]; then
        echo "stopped"
        exit 0
    fi
fi

server_args="$(ps -p "$server_pid" -o args= 2>/dev/null || true)"
if [[ "$server_args" != *"uvicorn app.main:app"* ]]; then
    rm -f "$pid_file"
    echo "stopped"
    exit 0
fi

if [[ "$managed_group" == true ]]; then
    kill -TERM -- "-$server_pid" 2>/dev/null || true
else
    kill -TERM "$server_pid" 2>/dev/null || true
fi
for attempt in {1..20}; do
    if ! is_alive "$server_pid"; then
        rm -f "$pid_file"
        echo "stopped"
        exit 0
    fi
    sleep 0.5
done

if [[ "$managed_group" == true ]]; then
    kill -KILL -- "-$server_pid" 2>/dev/null || true
else
    kill -KILL "$server_pid" 2>/dev/null || true
fi
for attempt in {1..10}; do
    if ! is_alive "$server_pid"; then
        rm -f "$pid_file"
        echo "stopped"
        exit 0
    fi
    sleep 0.5
done
echo "The inference process did not exit after SIGKILL" >&2
exit 1
'
