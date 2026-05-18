"""配置持久化管理，JSON 格式"""

import json
import os

CONFIG_DIR = os.path.expanduser("~/.config/voice_typing")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "engine": "alibaba",
    "alibaba_api_key": "",
    "local_model": "base",
    "hotkey": ["ctrl", "alt", "v"],
    "first_run": True,
    "custom_vocabulary": [],  # 自定义词库 [{"wrong": "错误词", "correct": "正确词"}]
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
