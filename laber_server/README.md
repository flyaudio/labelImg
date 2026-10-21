# label_server control service

`label_server` is a small Python standard-library HTTP service. It stays on the
Ubuntu host and uses no model, CUDA, or GPU packages. It controls the existing
`anylabel` Docker container's X-AnyLabeling inference process on port `8000`.

## Files

- `label_server.py`: authenticated control API, default port `8001`.
- `process_manager.py`: process lifecycle and status checks.
- `start_x-anylabeling-server.sh`: starts the existing container if needed and
  launches Uvicorn inside it.
- `stop_x-anylabeling-server.sh`: sends SIGTERM to the dedicated Uvicorn
  process group, waits, then uses SIGKILL only if it did not exit.
- `status_x-anylabeling-server.sh`: checks the PID recorded inside the
  container and detects the exact Uvicorn command if it was started manually
  before this controller was installed.
- `label_server.service`: example systemd unit for an always-on controller.

The scripts use the existing paths and names from the deployment:
container `anylabel`, project `/home/znzz/ma/X-AnyLabeling-Server`, and Uvicorn
port `8000`. They use non-interactive `docker exec`; the API remains attached
to a tracked wrapper process and does not require a terminal.

## Install on Ubuntu 22.04

Copy this whole folder to `/opt/laber_server`, then create a strong control
token in `/etc/laber_server.env`:

```sh
sudo install -d -m 0750 /opt/laber_server
sudo cp -a laber_server/. /opt/laber_server/
sudo sh -c 'umask 077; printf "%s\n" "LABEL_SERVER_TOKEN=replace-with-a-long-random-secret" > /etc/laber_server.env'
sudo chmod 0600 /etc/laber_server.env
```

Install and enable the systemd unit:

```sh
sudo cp /opt/laber_server/label_server.service /etc/systemd/system/label_server.service
sudo systemctl daemon-reload
sudo systemctl enable --now label_server.service
sudo systemctl status label_server.service
```

The unit runs as root so it can access the Docker daemon. Docker access grants
root-equivalent control of the host; keep the management port private and allow
it only from trusted client machines using the host firewall. Do not expose
port `8001` to the public internet. The token protects the HTTP actions, and
firewall restrictions limit who can reach the Docker controller at all.

The unauthenticated health endpoint is `GET http://SERVER:8001/health`. The
authenticated API uses the `Token` header:

- `GET /status`
- `POST /start` with `{}` JSON
- `POST /stop` with `{}` JSON

The control API never accepts a shell command or an arbitrary script path.
Starting and stopping the inference process does not stop the Docker container,
so the low-resource `label_server` remains available for the next request.

## Validate on the remote host

The server-side environment is not accessible from the labelImg client. After
installing, validate the unit, API token, Docker permissions, and model API
from Ubuntu. The client settings default to inference `http://192.168.31.5:8000`
and control `http://192.168.31.5:8001`.
