import os
import copy
import time
import yaml
import importlib.resources as pkg_resources
from threading import Lock, Event

from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
import setup
import log
import configs as CONFIGS
import auto_labeling.qt as qt

from auto_labeling.qt import GenericWorker
from auto_labeling.config import get_config, save_config
from auto_labeling.types import (
    AutoLabelingResult,
#     DownloadCancelledError,
)
# from anylabeling.services.auto_labeling.utils import TimeoutContext
from auto_labeling.config import (
    _CUSTOM_MODELS,
    _CACHED_AUTO_LABELING_MODELS,
    _AUTO_LABELING_MARKS_MODELS,
    _AUTO_LABELING_API_TOKEN_MODELS,
    _AUTO_LABELING_RESET_TRACKER_MODELS,
    _AUTO_LABELING_CONF_MODELS,
    _AUTO_LABELING_IOU_MODELS,
    _AUTO_LABELING_MASK_FINENESS_MODELS,
    _AUTO_LABELING_CROPPING_MODE_MODELS,
    _AUTO_LABELING_PRESERVE_EXISTING_ANNOTATIONS_STATE_MODELS,
    _AUTO_LABELING_PROMPT_MODELS,
    _ON_NEXT_FILES_CHANGED_MODELS,
)


class ModelManager(QObject):
    MAX_NUM_CUSTOM_MODELS = 5
    model_configs_changed = pyqtSignal(list)
    new_model_status = pyqtSignal(str)
    model_loaded = pyqtSignal(dict)
    new_auto_labeling_result = pyqtSignal(AutoLabelingResult)
    auto_segmentation_model_selected = pyqtSignal()
    auto_segmentation_model_unselected = pyqtSignal()
    prediction_started = pyqtSignal()
    prediction_finished = pyqtSignal()
    request_next_files_requested = pyqtSignal()
    output_modes_changed = pyqtSignal(dict, str)
    download_progress = pyqtSignal(int, int)
    download_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.model_configs = []

        self.loaded_model_config = None
        self.loaded_model_config_lock = Lock()

        self.model_download_worker = None
        self.model_download_thread = None
        self.model_execution_thread = None
        self.model_execution_thread_lock = Lock()
        self.model_execution_worker = None
        self._cancel_event = Event()

        self.load_model_configs()

    def load_model_configs(self):
        # Load list of default models
        with pkg_resources.open_text(CONFIGS, "models.yaml") as f:
            model_list = yaml.safe_load(f)
            log.info("default model list:", model_list)

        # Load list of custom models
        custom_models = get_config().get("custom_models", [])
        log.info("custom model list:", custom_models)
        for custom_model in custom_models:
            custom_model["is_custom_model"] = True

        # Remove invalid/not found custom models
        custom_models = [
            custom_model
            for custom_model in custom_models
            if os.path.isfile(custom_model.get("config_file", ""))
        ]
        config = get_config()
        config["custom_models"] = custom_models
        # save_config(config)

        model_list += custom_models

        # Load model configs
        model_configs = []
        for model in model_list:
            model_config = {}
            config_file = model["config_file"]
            if config_file.startswith(":/"):  # Config file is in resources
                config_file_name = config_file[2:]
                log.warn("11=", config_file_name)
                resource_path = pkg_resources.files(CONFIGS) / "auto_labeling" / config_file_name
                config_content = resource_path.read_text(encoding="utf-8")
                model_config = yaml.safe_load(config_content)
                model_config["config_file"] = str(config_file)
            else:  # Config file is in local file system
                with open(config_file, "r", encoding="utf-8") as f:
                    model_config = yaml.safe_load(f)
                    model_config["config_file"] = os.path.normpath(
                        os.path.abspath(config_file)
                    )
            is_custom = model.get("is_custom_model", False)
            model_config["is_custom_model"] = is_custom
            if is_custom and not model_config["name"].startswith("_custom_"):
                model_config["name"] = f"_custom_{model_config['name']}"

            model_configs.append(model_config)

        # Sort by last used
        for i, model_config in enumerate(model_configs):
            # Keep order for integrated models
            if not model_config.get("is_custom_model", False):
                model_config["last_used"] = -i
            else:
                model_config["last_used"] = model_config.get(
                    "last_used", time.time()
                )
        model_configs.sort(key=lambda x: x.get("last_used", 0), reverse=True)

        self.model_configs = model_configs
        self.model_configs_changed.emit(model_configs)

    def update_model_config(self, config_file, key, value):
        """Update a specific key in a model's configuration."""
        for config in self.model_configs:
            if config.get("config_file") == config_file:
                config[key] = value
                if (
                    self.loaded_model_config
                    and self.loaded_model_config.get("config_file")
                    == config_file
                ):
                    self.loaded_model_config[key] = value
                break

        if config_file and config_file.startswith(":/"):
            user_config = get_config()
            if "remote_server_settings" not in user_config:
                user_config["remote_server_settings"] = {}
            user_config["remote_server_settings"][key] = value
            save_config(user_config)

    def get_model_configs(self):
        """Return model infos"""
        return self.model_configs

    def set_output_mode(self, mode):
        """Set output mode"""
        if self.loaded_model_config and self.loaded_model_config["model"]:
            self.loaded_model_config["model"].set_output_mode(mode)

    def cancel_download(self):
        """Cancel the current model download."""
        self._cancel_event.set()

    @pyqtSlot()
    def on_model_download_finished(self):
        """Handle model download thread finished"""
        self.download_finished.emit()
        if self._cancel_event.is_set():
            self._cancel_event.clear()
            self.new_model_status.emit(self.tr("Download cancelled."))
            self.model_loaded.emit({})
            return
        if self.loaded_model_config and self.loaded_model_config["model"]:
            self.new_model_status.emit(
                self.tr("Model loaded. Ready for labeling.")
            )
            self.model_loaded.emit(self.loaded_model_config)
            self.output_modes_changed.emit(
                self.loaded_model_config["model"].Meta.output_modes,
                self.loaded_model_config["model"].Meta.default_output_mode,
            )
        else:
            self.model_loaded.emit({})

    def load_custom_model(self, config_file):
        """Run custom model loading in a thread"""
        raise NotImplementedError("load_custom_model")
        # config_file = os.path.normpath(os.path.abspath(config_file))
        # if (
        #     self.model_download_thread is not None
        #     and self.is_model_download_running()
        # ):
        #     log.info("Another model is being loaded. Please wait for it to finish.")
        #     return False
        #
        # # Check config file path
        # if not config_file or not os.path.isfile(config_file):
        #     log.error(
        #         "An error occurred while loading the custom model: "
        #         "The model path is invalid."
        #     )
        #     self.new_model_status.emit(self.tr("Error in loading custom model: Invalid path."))
        #     return False
        #
        # # Check config file content
        # model_config = {}
        # try:
        #     with open(config_file, "r", encoding="utf-8") as f:
        #         model_config = yaml.safe_load(f)
        #         model_config["config_file"] = os.path.abspath(config_file)
        # except Exception as e:
        #     log.error(
        #         "An error occurred while loading the custom model: "
        #         "The config file is invalid."
        #     )
        #     self.new_model_status.emit(
        #         self.tr("Error in loading custom model: Invalid config file.")
        #     )
        #     return False
        #
        # if (
        #     "type" not in model_config
        #     or "display_name" not in model_config
        #     or "name" not in model_config
        #     or model_config["type"] not in _CUSTOM_MODELS
        # ):
        #     if "type" not in model_config:
        #         log.error(
        #             "An error occurred while loading the custom model: "
        #             "The 'type' field is missing in the model configuration file."
        #         )
        #     elif "display_name" not in model_config:
        #         log.error(
        #             "An error occurred while loading the custom model: "
        #             "The 'display_name' field is missing in the model configuration file."
        #         )
        #     elif "name" not in model_config:
        #         log.error(
        #             "An error occurred while loading the custom model: "
        #             "The 'name' field is missing in the model configuration file."
        #         )
        #     else:
        #         log.error(
        #             "An error occurred while loading the custom model: "
        #             "The model type {model_config['type']} is not supported."
        #         )
        #     self.new_model_status.emit(
        #         self.tr(
        #             "Error in loading custom model: Invalid config file format."
        #         )
        #     )
        #     self.model_loaded.emit({})
        #     return False
        #
        # # Add or replace custom model
        # custom_models = get_config().get("custom_models", [])
        # matched_index = None
        # for i, model in enumerate(custom_models):
        #     if os.path.normpath(model["config_file"]) == os.path.normpath(
        #         config_file
        #     ):
        #         matched_index = i
        #         break
        # if matched_index is not None:
        #     model_config["last_used"] = time.time()
        #     custom_models[matched_index] = model_config
        # else:
        #     if len(custom_models) >= self.MAX_NUM_CUSTOM_MODELS:
        #         custom_models.sort(
        #             key=lambda x: x.get("last_used", 0), reverse=True
        #         )
        #         custom_models.pop()
        #     custom_models = [model_config] + custom_models
        #
        # # Save config
        # config = get_config()
        # config["custom_models"] = custom_models
        # save_config(config)
        #
        # # Reload model configs
        # self.load_model_configs()
        #
        # # Load model
        # self.load_model(model_config["config_file"])
        #
        # return True

    def load_model(self, config_file):
        """Run model loading in a thread"""
        # if self.is_model_download_running():
        #     log.info("Another model is being loaded. Please wait for it to finish.")
        #     return
        # if not config_file:
        #     if self.model_download_worker is not None:
        #         try:
        #             self.model_download_worker.finished.disconnect(
        #                 self.on_model_download_finished
        #             )
        #         except TypeError:
        #             pass
        #     self.unload_model()
        #     self.new_model_status.emit(self.tr("No model selected."))
        #     return

        # Check and get model id
        model_id = None
        for i, model_config in enumerate(self.model_configs):
            if model_config["config_file"] == config_file:
                model_id = i
                break
        if model_id is None:
            log.error(
                "An error occurred while loading the model: "
                "The model name is invalid.")
            self.new_model_status.emit(self.tr("Error in loading model: Invalid model name."))
            return

        self._cancel_event.clear()
        self.model_download_thread = QThread()
        template = "Loading model: {model_name}. Please wait..."
        translated_template = self.tr(template)
        message = translated_template.format(
            model_name=self.model_configs[model_id]["display_name"]
        )
        self.new_model_status.emit(message)

        self.model_download_worker = GenericWorker(self._load_model, model_id)
        self.model_download_worker.finished.connect(
            self.on_model_download_finished
        )
        self.model_download_worker.finished.connect(
            self.model_download_thread.quit
        )
        self.model_download_thread.finished.connect(
            self.on_model_download_thread_finished
        )
        self.model_download_thread.finished.connect(
            self.model_download_thread.deleteLater
        )
        self.model_download_worker.moveToThread(self.model_download_thread)
        self.model_download_thread.started.connect(
            self.model_download_worker.run
        )
        self.model_download_thread.start()

    def is_model_download_running(self):
        """Return whether the model download thread is still running."""
        try:
            return (
                self.model_download_thread is not None
                and self.model_download_thread.isRunning()
            )
        except RuntimeError:
            self.model_download_thread = None
            self.model_download_worker = None
            return False

    @pyqtSlot()
    def on_model_download_thread_finished(self):
        """Clear finished model download thread references."""
        self.model_download_thread = None
        self.model_download_worker = None

    def _load_model(self, model_id):  # noqa: C901
        """Load and return model info"""
        with self.loaded_model_config_lock:
            old_config = self.loaded_model_config
            if old_config is not None:
                self.loaded_model_config = None
        if old_config is not None:
            old_config["model"].unload()
            self.auto_segmentation_model_unselected.emit()

        model_config = copy.deepcopy(self.model_configs[model_id])
        model_config["_cancel_event"] = self._cancel_event
        model_config["_on_progress"] = (
            lambda downloaded, total: self.download_progress.emit(downloaded, total)
        )
        if model_config["type"] == "remote_server":
            from .remote_server import RemoteServer

            try:
                log.info(f"Loading model: {model_config['type']}")
                model_config["model"] = RemoteServer(
                    model_config, on_message=self.new_model_status.emit
                )
                self.auto_segmentation_model_unselected.emit()
                log.info(
                    f"load succ: {model_config['type']}"
                )
            except Exception as e:
                template = "Error in loading model: {error_message}"
                translated_template = self.tr(template)
                error_text = translated_template.format(error_message=str(e))
                self.new_model_status.emit(error_text)
                log.error(
                    f"Err in loading model: {model_config['type']} with error: {str(e)}"
                )
                return
        else:
            raise Exception(f"Unknown model type: {model_config['type']}")

        with self.loaded_model_config_lock:
            self.loaded_model_config = model_config
        return model_config

    def set_cache_auto_label(self, text, gid):
        """Set cache auto label
        沿用上次的标签，不用重复输入"""
        if (
            self.loaded_model_config is not None
            and self.loaded_model_config["type"]
            in _CACHED_AUTO_LABELING_MODELS
        ):
            self.loaded_model_config["model"].set_cache_auto_label(text, gid)

    def set_auto_labeling_marks(self, marks):
        """Set auto labeling marks
        (For example, for segment_anything model, it is the marks for)
        """
        if (
            self.loaded_model_config is None
            or self.loaded_model_config["type"]
            not in _AUTO_LABELING_MARKS_MODELS
        ):
            return
        self.loaded_model_config["model"].set_auto_labeling_marks(marks)

    def set_auto_labeling_api_token(self, token):
        """Set the API token for the model"""
        if (
            self.loaded_model_config is None
            or self.loaded_model_config["type"]
            not in _AUTO_LABELING_API_TOKEN_MODELS
        ):
            return
        self.loaded_model_config["model"].set_auto_labeling_api_token(token)

    def set_auto_labeling_reset_tracker(self):
        """Resets the tracker to its initial state,
        clearing all tracked objects and internal states.
        """
        if (
            self.loaded_model_config is None
            or self.loaded_model_config["type"]
            not in _AUTO_LABELING_RESET_TRACKER_MODELS
        ):
            return
        self.loaded_model_config["model"].set_auto_labeling_reset_tracker()

    def set_auto_labeling_conf(self, value):
        """Set auto labeling confidences"""
        if (
            self.loaded_model_config is None
            or self.loaded_model_config["type"] not in _AUTO_LABELING_CONF_MODELS
        ):
            return
        self.loaded_model_config["model"].set_auto_labeling_conf(value)

    def set_auto_labeling_iou(self, value):
        """Set auto labeling iou"""
        if (
            self.loaded_model_config is None
            or self.loaded_model_config["type"]
            not in _AUTO_LABELING_IOU_MODELS
        ):
            return
        self.loaded_model_config["model"].set_auto_labeling_iou(value)

    def set_auto_labeling_preserve_existing_annotations_state(self, state):
        if (
            self.loaded_model_config is not None
            and self.loaded_model_config["type"]
            in _AUTO_LABELING_PRESERVE_EXISTING_ANNOTATIONS_STATE_MODELS
        ):
            self.loaded_model_config[
                "model"
            ].set_auto_labeling_preserve_existing_annotations_state(state)

    def set_auto_labeling_prompt(self):
        if (
            self.loaded_model_config is not None
            and self.loaded_model_config["type"]
            in _AUTO_LABELING_PROMPT_MODELS
        ):
            self.loaded_model_config["model"].set_auto_labeling_prompt()

    def set_auto_labeling_filter_classes(self, class_names):
        """Set the active class filter by name on the loaded model."""
        if self.loaded_model_config is None:
            return
        model = self.loaded_model_config.get("model")
        if model and hasattr(model, "set_auto_labeling_filter_classes"):
            model.set_auto_labeling_filter_classes(class_names) #透传

    def unload_model(self):
        """Unload model"""
        if self.loaded_model_config is not None:
            self.loaded_model_config["model"].unload()
            self.loaded_model_config = None

    def predict_shapes(
        self,
        image,
        filename=None,
        text_prompt=None,
        run_tracker=False,
        batch=False,
        existing_shapes=None,
    ):
        """Predict shapes.
        NOTE: This function blocks. The model can take a long time to
        predict. So it is recommended to use predict_shapes_threading instead.
        """
        with self.loaded_model_config_lock:
            model_config = self.loaded_model_config
        if model_config is None:
            msg = "Model is not loaded. Choose a mode to continue"
            log.warn(msg)
            self.new_model_status.emit(self.tr(msg))
            self.prediction_finished.emit()
            return

        try:
            if text_prompt is not None:
                auto_labeling_result = model_config["model"].predict_shapes(
                    image, filename, text_prompt=text_prompt
                )
            elif run_tracker is True:
                auto_labeling_result = model_config["model"].predict_shapes(
                    image, filename, run_tracker=run_tracker
                )
            elif existing_shapes is not None:
                auto_labeling_result = model_config["model"].predict_shapes(
                    image, filename, existing_shapes=existing_shapes
                )
            else:
                auto_labeling_result = model_config["model"].predict_shapes(image, filename)

            if isinstance(auto_labeling_result, AutoLabelingResult):
                auto_labeling_result.image_path = filename

            if batch:
                return auto_labeling_result
            else:
                self.new_auto_labeling_result.emit(auto_labeling_result)
                msg = "AI inferencing Finished. Check the result"
                log.info(msg)
                self.new_model_status.emit(self.tr(msg))

        except Exception as e:  # noqa
            log.error(f"Error in predict_shapes: {e}")
            template = "Error in model prediction: {error_message}"
            translated_template = self.tr(template)
            error_text = translated_template.format(error_message=str(e))
            self.new_model_status.emit(error_text)

        self.prediction_finished.emit()

    @pyqtSlot()
    def predict_shapes_threading(
        self,
        image,
        filename=None,
        text_prompt=None,
        run_tracker=False,
        existing_shapes=None,
    ):
        """Predict shapes.
        This function starts a thread to run the prediction.
        """
        with self.loaded_model_config_lock:
            _config_snapshot = self.loaded_model_config
        if _config_snapshot is None:
            self.new_model_status.emit(self.tr("Model is not loaded. Choose a mode to continue."))
            return
        self.new_model_status.emit(self.tr("Inferencing. Please wait..."))
        self.prediction_started.emit()

        with self.model_execution_thread_lock:
            try:
                execution_running = (
                    self.model_execution_thread is not None
                    and self.model_execution_thread.isRunning()
                )
            except RuntimeError:
                self.model_execution_thread = None
                self.model_execution_worker = None
                execution_running = False

            if execution_running:
                msg = "Another model is being executed"
                log.warn(msg)
                self.new_model_status.emit(self.tr(msg))
                self.prediction_finished.emit()
                return

            self.model_execution_thread = QThread()
            if text_prompt is not None:
                self.model_execution_worker = GenericWorker(
                    self.predict_shapes,
                    image,
                    filename,
                    text_prompt=text_prompt,
                )
            elif run_tracker is True:
                self.model_execution_worker = GenericWorker(
                    self.predict_shapes,
                    image,
                    filename,
                    run_tracker=run_tracker,
                )
            elif existing_shapes is not None:
                self.model_execution_worker = GenericWorker(
                    self.predict_shapes,
                    image,
                    filename,
                    existing_shapes=existing_shapes,
                )
            else:
                self.model_execution_worker = GenericWorker(
                    self.predict_shapes, image, filename
                )
            self.model_execution_worker.finished.connect( # Worker 任务完成 → 让线程退出事件循环
                self.model_execution_thread.quit
            )
            self.model_execution_thread.finished.connect(
                self.on_model_execution_finished
            )
            self.model_execution_thread.finished.connect( #线程结束 → 延迟销毁线程对象，自动释放内存
                self.model_execution_thread.deleteLater
            )
            self.model_execution_worker.moveToThread( #Worker 对象移动到子线程中
                self.model_execution_thread
            )
            self.model_execution_thread.started.connect( # 线程启动后，自动执行 Worker 的 run 方法
                self.model_execution_worker.run
            )
            self.model_execution_thread.start()

    @pyqtSlot()
    def on_model_execution_finished(self):
        """Clear finished model execution thread references."""
        with self.model_execution_thread_lock:
            self.model_execution_thread = None
            self.model_execution_worker = None

    def on_next_files_changed(self, next_files):
        """Run prediction on next files in advance to save inference time later"""
        if self.loaded_model_config is None:
            return

        # Currently only segment_anything-like model supports this feature
        if (
            self.loaded_model_config["type"]
            not in _ON_NEXT_FILES_CHANGED_MODELS
        ):
            return

        self.loaded_model_config["model"].on_next_files_changed(next_files)

    # Specific model setters
    def set_upn_mode(self, mode):
        """Set UPN mode"""
        if self.loaded_model_config is None:
            return

        if self.loaded_model_config["type"] == "upn":
            self.loaded_model_config["model"].set_upn_mode(mode)

    def set_groundingdino_mode(self, mode):
        """Set GroundingDino (API) mode"""
        if self.loaded_model_config is None:
            return

        if self.loaded_model_config["type"] == "grounding_dino_api":
            self.loaded_model_config["model"].set_groundingdino_mode(mode)

    def set_florence2_mode(self, mode):
        """Set Florence2 mode"""
        if self.loaded_model_config is None:
            return

        if self.loaded_model_config["type"] == "florence2":
            self.loaded_model_config["model"].set_florence2_mode(mode)

    def set_remote_server_model(self, model_id):
        """Set remote server model ID"""
        if self.loaded_model_config is None:
            return

        if self.loaded_model_config["type"] == "remote_server":
            self.loaded_model_config["model"].set_model_id(model_id)

    def get_remote_server_available_models(self):
        """Get available models from remote server"""
        if self.loaded_model_config is None:
            return {}

        if self.loaded_model_config["type"] == "remote_server":
            return self.loaded_model_config["model"].get_available_models()
        return {}

    def get_remote_server_current_model_id(self):
        """Get current remote server model ID"""
        if self.loaded_model_config is None:
            return None

        if self.loaded_model_config["type"] == "remote_server":
            return self.loaded_model_config["model"].current_model_id
        return None

    def set_task(self, task_id):
        """Set task ID for the current model"""
        if self.loaded_model_config is None:
            return

        if self.loaded_model_config["type"] == "remote_server":
            self.loaded_model_config["model"].set_task(task_id)

    def set_mask_fineness(self, epsilon):
        """Set mask fineness (epsilon value for Douglas-Peucker algorithm)"""
        if (
            self.loaded_model_config is None
            or self.loaded_model_config["type"]
            not in _AUTO_LABELING_MASK_FINENESS_MODELS
        ):
            return
        self.loaded_model_config["model"].set_mask_fineness(epsilon)

    def set_cropping_mode(self, enabled: bool):
        """Set cropping mode for small object detection"""
        if (
            self.loaded_model_config is None
            or self.loaded_model_config["type"]
            not in _AUTO_LABELING_CROPPING_MODE_MODELS
        ):
            return
        self.loaded_model_config["model"].set_cropping_mode(enabled)


def test_get_config():
    cfg = get_config()
    for k, v in cfg.items():
        print(f"{k}->{v}")

def test_ModelManager():
    mm = ModelManager()
    mm.predict_shapes_threading(None)

if __name__ == "__main__":
    # test_get_config()
    test_ModelManager()