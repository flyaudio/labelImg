import sys
import yaml
import unittest
from pathlib import Path
import PyQt6.QtWidgets as QtWidgets
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
	QMainWindow
)
import setup
import anylabeling.resources.resources
from anylabeling.services.auto_labeling.remote_server import RemoteServer


class TestRemoteServer(unittest.TestCase):
	def setUp(self):
		# self.app = QApplication(sys.argv)
		ymlFileName = Path(setup.getRootDir()) / "anylabeling/configs/auto_labeling/remote_server.yaml"
		assert Path(ymlFileName).is_file(), ymlFileName
		try:
			# with open(ymlFileName, "r", encoding="utf-8") as f:
			# 	model_config = yaml.safe_load(f)
			# 	print("model_config=", model_config)
			model_config = {}
			on_message = print
			# print(f"Loading model: {model_config['type']}")
			# model_config["model"] = RemoteServer(model_config, on_message=on_message)
			model_config["model"] = RemoteServer(str(ymlFileName), on_message=on_message)
			# self.auto_segmentation_model_unselected.emit()
			# print(f"Model loaded successfully: {model_config['type']}")
		except Exception as e:
			template = "err in loading model: {error_message}"
			# translated_template = self.tr(template)
			# error_text = translated_template.format(error_message=str(e))
			# self.new_model_status.emit(error_text)
			# print(f"Error in loading model: {model_config['type']} with error: {str(e)}")

	def test_1(self):
		pass


if __name__ == '__main__':
	unittest.main()
'''
uvicorn app.main:app --host 0.0.0.0 --port 8000
'''