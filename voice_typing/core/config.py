"""配置持久化管理，JSON 格式"""

import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/voice_typing")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "engine": "alibaba",            # "alibaba" | "volcengine" | "mimo" | "local"
    "alibaba_api_key": "",          # 阿里云 DashScope API Key（ASR + 润色共用）
    "volc_asr_app_id": "",          # 火山引擎 ASR App ID
    "volc_asr_access_token": "",   # 火山引擎 ASR Access Token
    "mimo_api_key": "",             # 小米 Mify API Key
    "local_model": "base",
    "hotkey": ["ctrl", "alt", "v"],
    "first_run": True,
    "custom_vocabulary": [],        # 自定义热词列表：["CUDA", "GitHub", "Python"]
    "phrase_id": "",                # 阿里云热词表ID（UUID，由VocabularyService创建）
    "polish_enabled": True,         # 润色开关
    "polish_strength": "medium",    # 润色强度：light / medium / strong
    "doubao_api_key": "",           # 豆包 ARK API Key
    "doubao_endpoint_id": "",       # 豆包推理接入点 ID（ep-xxxxxxxxxxxx）
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_PATH, "r") as f:
        data = json.load(f)
    # 合并缺失的默认值
    for k, v in DEFAULT_CONFIG.items():
        if k not in data:
            data[k] = v
    return data


def save_config(config):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
