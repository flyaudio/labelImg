"""Start and stop the inference process in the existing Docker container."""

import subprocess
import threading
from pathlib import Path


class RemoteInferenceProcessError(RuntimeError):
    """A Docker or process lifecycle command failed."""


class RemoteInferenceProcessManager:
    """Manage only the fixed X-AnyLabeling inference service process."""

    def __init__(
        self,
        start_script=None,
        stop_script=None,
        status_script=None,
        popen_factory=None,
        run_command=None,
        stop_timeout=20,
    ):
        folder = Path(__file__).resolve().parent
        self.start_script = Path(start_script or folder / "start_x-anylabeling-server.sh")
        self.stop_script = Path(stop_script or folder / "stop_x-anylabeling-server.sh")
        self.status_script = Path(status_script or folder / "status_x-anylabeling-server.sh")
        self._popen = popen_factory or subprocess.Popen
        self._run = run_command or subprocess.run
        self._stop_timeout = stop_timeout
        self._process = None
        self._lock = threading.RLock()

    @staticmethod
    def _script_command(path):
        return ["bash", str(path)]

    def _container_service_status(self):
        try:
            result = self._run(
                self._script_command(self.status_script),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RemoteInferenceProcessError(
                "Unable to check the inference service: {}".format(exc)
            ) from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise RemoteInferenceProcessError(
                detail or "Unable to check the inference service"
            )
        status = (result.stdout or "").strip().lower()
        if status not in {"running", "stopped"}:
            raise RemoteInferenceProcessError(
                "Unexpected inference service status: {}".format(status)
            )
        return status

    def status(self):
        """Return running, starting, or stopped for the inference service."""
        with self._lock:
            status = self._container_service_status()
            if status == "running":
                return "running"
            if self._process is not None and self._process.poll() is None:
                return "starting"
            return "stopped"

    def start(self):
        """Launch the fixed start script without blocking the control API."""
        with self._lock:
            status = self._container_service_status()
            if status == "running":
                return "running"
            if self._process is not None and self._process.poll() is None:
                return "starting"
            try:
                self._process = self._popen(
                    self._script_command(self.start_script),
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    close_fds=True,
                )
            except OSError as exc:
                self._process = None
                raise RemoteInferenceProcessError(
                    "Unable to launch the inference service: {}".format(exc)
                ) from exc
            return "starting"

    def stop(self):
        """Stop the container's Uvicorn process and wait for it to exit."""
        with self._lock:
            try:
                result = self._run(
                    self._script_command(self.stop_script),
                    capture_output=True,
                    text=True,
                    timeout=self._stop_timeout + 10,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise RemoteInferenceProcessError(
                    "Unable to stop the inference service: {}".format(exc)
                ) from exc
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "").strip()
                raise RemoteInferenceProcessError(
                    detail or "Unable to stop the inference service"
                )

            process = self._process
            if process is not None and process.poll() is None:
                try:
                    process.wait(timeout=self._stop_timeout)
                except subprocess.TimeoutExpired:
                    # The container-side stop script has already sent TERM and
                    # KILL to the dedicated Uvicorn process group. Terminate
                    # the now-orphaned docker exec wrapper if it did not exit.
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
            self._process = None

            status = self._container_service_status()
            if status != "stopped":
                raise RemoteInferenceProcessError(
                    "The inference service is still running after stop"
                )
            return "stopped"
