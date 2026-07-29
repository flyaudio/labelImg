import os
import os.path as osp
import shutil
import copy
import yaml
import importlib.resources as pkg_resources

import setup
import configs as CONFIGS
import log

current_config_file = os.path.join(setup.getRootDir(), "configs/xanylabeling_config.yaml")
_work_directory = None
_LEGACY_KEY_MAP = {
    "epsilon": "canvas.epsilon",
    "show_cross_line": "canvas.crosshair.show",
}
_LEGACY_DROP_KEYS = {"ui"}


def set_work_directory(directory: str) -> None:
    """
    Sets the working directory for X-AnyLabeling.

    Args:
        directory (str): The path to the working directory.
    """
    global _work_directory
    _work_directory = osp.abspath(osp.expanduser(directory))


def get_work_directory() -> str:
    """
    Gets the working directory for X-AnyLabeling.

    Returns:
        str: The absolute path to the working directory.
    """
    if _work_directory is None:
        return osp.expanduser("~")
    return _work_directory


def get_models_config_path():
    return os.path.join(
        get_work_directory(), "xanylabeling_data", "models.json"
    )


def update_dict(target_dict, new_dict, validate_item=None):
    for key, value in new_dict.items():
        if validate_item:
            validate_item(key, value)
        if key not in target_dict:
            log.warn(f"Skipping unexpected key in config: {key}")
            continue
        if isinstance(target_dict[key], dict) and isinstance(value, dict):
            update_dict(target_dict[key], value, validate_item=validate_item)
        else:
            target_dict[key] = value


def _set_nested_value(target_dict, key_path, value):
    parts = key_path.split(".")
    current = target_dict
    for part in parts[:-1]:
        node = current.get(part)
        if not isinstance(node, dict):
            node = {}
            current[part] = node
        current = node
    current[parts[-1]] = value


def _has_nested_key(target_dict, key_path):
    current = target_dict
    for part in key_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _normalize_shortcut_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, (list, tuple)):
        values = [item for item in value if item not in (None, "")]
        if not values:
            return None
        value = values[0]
    text = str(value).strip()
    return text or None


def _normalize_multi_shortcut_value(value):
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        raw_values = [item for item in value if item not in (None, "")]
    else:
        raw_values = [value]
    normalized = []
    for item in raw_values:
        text = str(item).strip()
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def normalize_user_config(config):
    if not isinstance(config, dict):
        return config
    normalized = copy.deepcopy(config)
    for key, target_path in _LEGACY_KEY_MAP.items():
        if key in normalized:
            value = normalized.pop(key)
            if not _has_nested_key(normalized, target_path):
                _set_nested_value(normalized, target_path, value)
    for key in _LEGACY_DROP_KEYS:
        normalized.pop(key, None)
    shortcuts = normalized.get("shortcuts")
    if isinstance(shortcuts, dict):
        for key, value in list(shortcuts.items()):
            if key == "zoom_in":
                shortcuts[key] = _normalize_multi_shortcut_value(value)
            else:
                shortcuts[key] = _normalize_shortcut_value(value)
    return normalized


def save_config(config):
    user_config_file = osp.join(get_work_directory(), ".xanylabelingrc")
    try:
        os.makedirs(osp.dirname(user_config_file), exist_ok=True)
        with open(user_config_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f, allow_unicode=True)
    except Exception:  # noqa
        log.warn(f"Failed to save config: {user_config_file}")


def get_default_config():
    work_dir = get_work_directory()
    old_cfg_file = osp.join(work_dir, ".anylabelingrc")
    new_cfg_file = osp.join(work_dir, ".xanylabelingrc")
    if osp.exists(old_cfg_file) and not osp.exists(new_cfg_file):
        shutil.copyfile(old_cfg_file, new_cfg_file)

    config_file = "xanylabeling_config.yaml"
    with pkg_resources.open_text(CONFIGS, config_file) as f:
        config = yaml.safe_load(f)

    if not osp.exists(osp.join(work_dir, ".xanylabelingrc")):
        save_config(config)

    return config


def validate_config_item(key, value):
    if key == "validate_label" and value not in [None, "exact"]:
        raise ValueError(
            f"Unexpected value for config key 'validate_label': {value}"
        )
    if key == "qt_image_allocation_limit" and value is not None:
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(
                "Unexpected value for config key "
                f"'qt_image_allocation_limit': {value}"
            )
    if key == "shape_color" and value not in [None, "auto", "manual"]:
        raise ValueError(
            f"Unexpected value for config key 'shape_color': {value}"
        )
    if key == "labels" and value is not None and len(value) != len(set(value)):
        raise ValueError(
            f"Duplicates are detected for config key 'labels': {value}"
        )


def get_config(config_file_or_yaml=None, config_from_args=None, show_msg=True):
    # 1. Load default configuration
    config = get_default_config()

    # 2. Load configuration from file or YAML string
    if not config_file_or_yaml:
        config_file_or_yaml = current_config_file

    config_from_yaml = yaml.safe_load(config_file_or_yaml)
    if not isinstance(config_from_yaml, dict):
        with open(config_file_or_yaml, encoding="utf-8") as f:
            config_from_yaml = yaml.safe_load(f)
    config_from_yaml = normalize_user_config(config_from_yaml)
    update_dict(config, config_from_yaml, validate_item=validate_config_item)
    if show_msg:
        log.info(f"Initializing config from local file: {config_file_or_yaml}")

    # 3. Update configuration with command line arguments
    if config_from_args:
        config_from_args = normalize_user_config(config_from_args)
        update_dict(
            config, config_from_args, validate_item=validate_config_item
        )
        if show_msg:
            log.info(f"Updated config from CLI arguments: {config_from_args}")

    return config


# def get_chatbot_root_dir():
#     return os.path.join(get_work_directory(), "xanylabeling_data", "chatbot")
#
#
# def get_settings_config_path():
#     return os.path.join(get_chatbot_root_dir(), "settings.json")
#
#
# def get_providers_config_path():
#     return os.path.join(get_chatbot_root_dir(), "providers.json")


# Global design system
ANIMATION_DURATION = "200ms"
BORDER_RADIUS = "8px"
FONT_SIZE_TINY = "9px"
FONT_SIZE_SMALL = "11px"
FONT_SIZE_NORMAL = "13px"
FONT_SIZE_LARGE = "16px"
ICON_SIZE_NORMAL = (32, 32)
ICON_SIZE_SMALL = (16, 16)

# Initialization parameters
DEFAULT_WINDOW_TITLE = "Chatbot"
DEFAULT_WINDOW_SIZE = (1200, 700)  # (w, h)
DEFAULT_FIXED_HEIGHT = 32
CHAT_PANEL_PERCENTAGE = 88
INPUT_PANEL_PERCENTAGE = 12
MIN_MSG_INPUT_HEIGHT = 20
MAX_MSG_INPUT_HEIGHT = 300
USER_MESSAGE_MAX_WIDTH_PERCENT = 70
REFRESH_INTERVAL = 300  # seconds

# THEME = get_theme()


# Providers config
DEFAULT_SETTINGS = {
    "provider": "ollama",
    "model_id": None,
    "temperature": 10,
    "max_length": None,
    "system_prompt": None,
}

DEFAULT_PROVIDERS_DATA = {
    "custom": {
        "api_address": "",
        "api_key": "",
        "api_key_url": None,
        "api_docs_url": None,
        "model_docs_url": None,
    },
    "anthropic": {
        "api_address": "https://api.anthropic.com/v1/",
        "api_key": None,
        "api_key_url": "https://console.anthropic.com/settings/keys",
        "api_docs_url": "https://docs.anthropic.com/en/docs",
        "model_docs_url": "https://docs.anthropic.com/en/docs/about-claude/models/all-models",
    },
    "deepseek": {
        "api_address": "https://api.deepseek.com/v1",
        "api_key": None,
        "api_key_url": "https://platform.deepseek.com/api_keys",
        "api_docs_url": "https://platform.deepseek.com/docs",
        "model_docs_url": "https://platform.deepseek.com/models",
    },
    "google": {
        "api_address": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": None,
        "api_key_url": "https://aistudio.google.com/app/apikey",
        "api_docs_url": "https://ai.google.dev/gemini-api/docs",
        "model_docs_url": "https://ai.google.dev/gemini-api/docs/models",
    },
    "ollama": {
        "api_address": "http://localhost:11434/v1",
        "api_key": "ollama",
        "api_key_url": None,
        "api_docs_url": "https://github.com/ollama/ollama/blob/main/docs/api.md",
        "model_docs_url": "https://ollama.com/search",
    },
    "openai": {
        "api_address": "https://api.openai.com/v1",
        "api_key": None,
        "api_key_url": "https://platform.openai.com/api-keys",
        "api_docs_url": "https://platform.openai.com/docs",
        "model_docs_url": "https://platform.openai.com/docs/models",
    },
    "openrouter": {
        "api_address": "https://openrouter.ai/api/v1",
        "api_key": None,
        "api_key_url": "https://openrouter.ai/settings/keys",
        "api_docs_url": "https://openrouter.ai/docs/quick-start",
        "model_docs_url": "https://openrouter.ai/models",
    },
    "qwen": {
        "api_address": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": None,
        "api_key_url": "https://bailian.console.aliyun.com/?apiKey=1#/api-key",
        "api_docs_url": "https://help.aliyun.com/document_detail/2590237.html",
        "model_docs_url": "https://help.aliyun.com/zh/model-studio/developer-reference/what-is-qwen-llm",
    },
}

SUPPORTED_VISION_MODELS = [
    # Anthropic
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-5-sonnet-20240620",
    # Google AI
    "models/gemini-2.0-flash",
    "models/gemini-2.0-flash-exp",
    "models/gemini-2.0-pro-exp",
    "models/gemini-2.0-pro-exp-02-05",
    "models/gemini-2.0-flash-thinking-exp",
    "models/gemini-2.0-flash-thinking-exp-1219",
    "models/gemini-2.0-flash-thinking-exp-01-21",
    # Ollama
    "gemma3",
    "gemma3:4b",
    "gemma3:12b",
    "gemma3:27b",
    "bakllava",
    "granite3.2-vision",
    "minicpm-v",
    "moondream",
    "llava",
    "llava-llama3",
    "llava-phi3",
    "llama3.2-vision",
    # Qwen
    "qwen-vl-ocr-latest",
    "qwen-vl-ocr",
    "qwen-vl-max",
    "qwen-vl-plus",
    # OpenAI
    "gpt-4.5-preview",
    "gpt-4.5-preview-2025-02-27",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4o-mini-audio-preview-2024-12-17",
]



_CUSTOM_MODELS = [
    "remote_server",
    "florence2",
    "doclayout_yolo",
    "open_vision",
    "segment_anything",
    "segment_anything_2",
    "segment_anything_3",
    "segment_anything_2_video",
    "sam_med2d",
    "sam_hq",
    "yolov5",
    "yolov6",
    "yolov7",
    "yolov8",
    "yolov8_seg",
    "yolox",
    "yolov5_resnet",
    "yolov6_face",
    "rtdetr",
    "yolo_nas",
    "yolox_dwpose",
    "clrnet",
    "ppocr_v4",
    "yolov5_sam",
    "yolov8_sam2",
    "efficientvit_sam",
    "yolov5_track",
    "damo_yolo",
    "yolov5_sahi",
    "yolov8_sahi",
    "yolo11_sahi",
    "yolo26_sahi",
    "grounding_sam",
    "grounding_sam2",
    "grounding_dino",
    "grounding_dino_api",
    "yolov5_obb",
    "gold_yolo",
    "ram",
    "yolov5_seg",
    "yolov5_ram",
    "yolov8_pose",
    "pulc_attribute",
    "internimage_cls",
    "edge_sam",
    "yolov5_cls",
    "yolov8_cls",
    "yolov8_obb",
    "yolov5_car_plate",
    "rtmdet_pose",
    "yolov9",
    "yolow",
    "yolov10",
    "rmbg",
    "depth_anything",
    "depth_anything_v2",
    "yolow_ram",
    "rtdetrv2",
    "yolov8_det_track",
    "yolov8_seg_track",
    "yolov8_obb_track",
    "yolov8_pose_track",
    "yolo11",
    "yolo11_cls",
    "yolo11_obb",
    "yolo11_seg",
    "yolo11_pose",
    "yolo11_det_track",
    "yolo11_seg_track",
    "yolo11_obb_track",
    "yolo11_pose_track",
    "upn",
    "geco",
    "rfdetr",
    "rfdetr_seg",
    "dfine",
    "yolo12",
    "yolo26",
    "yolo26_seg",
    "yolo26_obb",
    "yolo26_pose",
    "u_rtdetr",
    "yoloe",
    "ppocr_v5",
    "deimv2",
]


# --- set_cache_auto_label ---
_CACHED_AUTO_LABELING_MODELS = [
    "segment_anything_2_video",
    "remote_server",
]


# --- set_auto_labeling_marks ---
_AUTO_LABELING_MARKS_MODELS = [
    "remote_server",
    "segment_anything",
    "segment_anything_2",
    "segment_anything_3",
    "segment_anything_2_video",
    "sam_med2d",
    "sam_hq",
    "yolov5_sam",
    "efficientvit_sam",
    "grounding_sam",
    "grounding_sam2",
    "open_vision",
    "edge_sam",
    "florence2",
    "geco",
    "yoloe",
]


# --- set_mask_fineness ---
_AUTO_LABELING_MASK_FINENESS_MODELS = [
    "remote_server",
    "segment_anything",
    "segment_anything_2",
    "segment_anything_3",
    "segment_anything_2_video",
    "sam_med2d",
    "sam_hq",
    "yolov5_sam",
    "efficientvit_sam",
    "grounding_sam",
    "grounding_sam2",
    "edge_sam",
    "rfdetr_seg",
]


# --- set_cropping_mode ---
_AUTO_LABELING_CROPPING_MODE_MODELS = [
    "remote_server",
    "segment_anything",
    "segment_anything_2",
    "segment_anything_2_video",
    "sam_med2d",
    "sam_hq",
    "yolov5_sam",
    "efficientvit_sam",
    "grounding_sam",
    "grounding_sam2",
    "edge_sam",
]


# --- skip detection step ---
_SKIP_DET_MODELS = [
    "ppocr_v4",
    "ppocr_v5",
]


# --- skip_prediction_on_new_marks ---
_SKIP_PREDICTION_ON_NEW_MARKS_MODELS = [
    "yoloe",
]


# --- set_auto_labeling_api_token ---
_AUTO_LABELING_API_TOKEN_MODELS = [
    "remote_server",
    "grounding_dino_api",
]


# --- set_auto_labeling_reset_tracker ---
_AUTO_LABELING_RESET_TRACKER_MODELS = [
    "remote_server",
    "yolov5_det_track",
    "yolov8_det_track",
    "yolov8_obb_track",
    "yolov8_seg_track",
    "yolov8_pose_track",
    "segment_anything_2_video",
    "yolo11_det_track",
    "yolo11_seg_track",
    "yolo11_obb_track",
    "yolo11_pose_track",
]


# --- set_auto_labeling_conf ---
_AUTO_LABELING_CONF_MODELS = [
    "remote_server",
    "upn",
    "segment_anything_3",
    "damo_yolo",
    "gold_yolo",
    "grounding_dino",
    "grounding_dino_api",
    "rtdetr",
    "rtdetrv2",
    "yolo_nas",
    "yolov5_obb",
    "yolov5_seg",
    "yolov5_det_track",
    "yolov5",
    "yolov5_sahi",
    "yolov6",
    "yolov6_face",
    "yolov7",
    "yolov8_sam2",
    "yolov8_obb",
    "yolov8_pose",
    "yolov8_seg",
    "yolov8_det_track",
    "yolov8_seg_track",
    "yolov8_obb_track",
    "yolov8_pose_track",
    "yolov8",
    "yolov8_sahi",
    "yolov9",
    "yolov10",
    "yolo11",
    "yolo11_sahi",
    "yolo11_obb",
    "yolo11_seg",
    "yolo11_pose",
    "yolo11_det_track",
    "yolo11_seg_track",
    "yolo11_obb_track",
    "yolo11_pose_track",
    "yolow",
    "yolox",
    "doclayout_yolo",
    "rfdetr",
    "rfdetr_seg",
    "deimv2",
    "dfine",
    "yolo12",
    "yolo26",
    "yolo26_sahi",
    "yolo26_seg",
    "yolo26_obb",
    "yolo26_pose",
    "u_rtdetr",
    "yoloe",
    "grounding_sam2",
]


# --- set_auto_labeling_iou ---
_AUTO_LABELING_IOU_MODELS = [
    "remote_server",
    "upn",
    "damo_yolo",
    "gold_yolo",
    "yolo_nas",
    "yolov5_obb",
    "yolov5_seg",
    "yolov5_det_track",
    "yolov5",
    "yolov5_sahi",
    "yolov6",
    "yolov7",
    "yolov8_sam2",
    "yolov8_obb",
    "yolov8_pose",
    "yolov8_seg",
    "yolov8_det_track",
    "yolov8_seg_track",
    "yolov8_obb_track",
    "yolov8_pose_track",
    "yolov8",
    "yolov8_sahi",
    "yolov9",
    "yolo11",
    "yolo11_sahi",
    "yolo11_obb",
    "yolo11_seg",
    "yolo11_pose",
    "yolo11_det_track",
    "yolo11_seg_track",
    "yolo11_obb_track",
    "yolo11_pose_track",
    "yolox",
    "yolo12",
    "yoloe",
]


# --- set_auto_labeling_preserve_existing_annotations_state ---
_AUTO_LABELING_PRESERVE_EXISTING_ANNOTATIONS_STATE_MODELS = [
    "remote_server",
    "damo_yolo",
    "gold_yolo",
    "grounding_dino",
    "grounding_dino_api",
    "rtdetr",
    "rtdetrv2",
    "yolo_nas",
    "yolov5_obb",
    "yolov5_seg",
    "yolov5_det_track",
    "yolov5",
    "yolov5_sahi",
    "yolov6",
    "yolov7",
    "yolov8_sam2",
    "yolov8_obb",
    "yolov8_pose",
    "yolov8_seg",
    "yolov8_det_track",
    "yolov8_seg_track",
    "yolov8_obb_track",
    "yolov8_pose_track",
    "yolov8",
    "yolov8_sahi",
    "yolov9",
    "yolov10",
    "yolo11",
    "yolo11_sahi",
    "yolo11_obb",
    "yolo11_seg",
    "yolo11_pose",
    "yolo11_det_track",
    "yolo11_seg_track",
    "yolo11_obb_track",
    "yolo11_pose_track",
    "yolow",
    "yolox",
    "doclayout_yolo",
    "florence2",
    "rfdetr",
    "rfdetr_seg",
    "segment_anything_3",
    "deimv2",
    "dfine",
    "yolo12",
    "yolo26",
    "yolo26_sahi",
    "yolo26_seg",
    "yolo26_obb",
    "yolo26_pose",
    "u_rtdetr",
    "yoloe",
    "segment_anything_2_video",
]


# --- set_auto_labeling_prompt ---
_AUTO_LABELING_PROMPT_MODELS = [
    "segment_anything_2_video",
]


# --- on_next_files_changed ---
_ON_NEXT_FILES_CHANGED_MODELS = [
    "segment_anything",
    "segment_anything_2",
    "sam_med2d",
    "sam_hq",
    "yolov5_sam",
    "yolov8_sam2",
    "efficientvit_sam",
    "grounding_sam",
    "grounding_sam2",
    "edge_sam",
    "geco",
]


# --- update_thumbnail_display ---
_THUMBNAIL_RENDER_MODELS = {
    "rmbg": ("x-anylabeling-matting", ".png"),
    "depth_anything": ("x-anylabeling-depth", ".png"),
    "depth_anything_v2": ("x-anylabeling-depth", ".png"),
}


# --- batch_processing_invalid_models ---
_BATCH_PROCESSING_INVALID_MODELS = [
    "segment_anything",
    "segment_anything_2",
    "sam_med2d",
    "sam_hq",
    "efficientvit_sam",
    "edge_sam",
    "open_vision",
    "geco",
]


# --- batch_processing_text_prompt_models ---
_BATCH_PROCESSING_TEXT_PROMPT_MODELS = [
    "remote_server",
    "grounding_dino",
    "grounding_sam",
    "grounding_sam2",
    "segment_anything_3",
    "yoloe",
]


# --- batch_processing_video_models ---
_BATCH_PROCESSING_VIDEO_MODELS = [
    "segment_anything_2_video",
    # "remote_server",
]
