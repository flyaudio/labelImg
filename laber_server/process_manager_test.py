"""Tests for the Docker inference process manager."""

import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

try:
    from .process_manager import (
        RemoteInferenceProcessError,
        RemoteInferenceProcessManager,
    )
except ImportError:  # direct execution from this directory
    from process_manager import (
        RemoteInferenceProcessError,
        RemoteInferenceProcessManager,
    )


class RemoteInferenceProcessManagerTest(unittest.TestCase):
    def setUp(self):
        self.status = "stopped"
        self.run = Mock(side_effect=self._run_command)
        self.process = Mock()
        self.process.poll.return_value = None
        self.popen = Mock(return_value=self.process)
        self.manager = RemoteInferenceProcessManager(
            start_script="start.sh",
            stop_script="stop.sh",
            status_script="status.sh",
            popen_factory=self.popen,
            run_command=self.run,
            stop_timeout=1,
        )

    def _run_command(self, command, **kwargs):
        if command[-1] == "status.sh":
            return SimpleNamespace(
                returncode=0, stdout=self.status + "\n", stderr=""
            )
        if command[-1] == "stop.sh":
            self.status = "stopped"
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError("Unexpected command: {}".format(command))

    def test_start_launches_script_without_interactive_terminal(self):
        self.assertEqual(self.manager.start(), "starting")
        self.popen.assert_called_once_with(
            ["bash", "start.sh"],
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )

    def test_start_does_not_duplicate_running_service(self):
        self.status = "running"
        self.assertEqual(self.manager.start(), "running")
        self.popen.assert_not_called()

    def test_stop_verifies_service_is_stopped(self):
        self.manager._process = self.process
        self.status = "running"
        self.assertEqual(self.manager.stop(), "stopped")
        self.process.wait.assert_called_once_with(timeout=1)
        self.assertIsNone(self.manager._process)

    def test_status_reports_starting_when_wrapper_is_alive(self):
        self.manager._process = self.process
        self.assertEqual(self.manager.status(), "starting")

    def test_failed_status_check_is_reported(self):
        self.run.side_effect = OSError("docker missing")
        with self.assertRaisesRegex(RemoteInferenceProcessError, "docker missing"):
            self.manager.status()


if __name__ == "__main__":
    unittest.main()
