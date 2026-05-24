"""热词表管理 — 通过 DashScope VocabularyService 创建/更新 phrase_id"""

import dashscope
from dashscope.audio.asr import VocabularyService, VocabularyServiceException


def sync_vocabulary(api_key: str, hotwords: list, phrase_id: str = None) -> str | None:
    """
    同步热词表：创建或更新，返回 phrase_id。

    Args:
        api_key: DashScope API Key
        hotwords: 热词列表 ["CUDA", "GitHub", ...]
        phrase_id: 已有的 phrase_id，如果有则更新，否则新建

    Returns:
        新的或更新后的 phrase_id，失败返回 None
    """
    if not api_key or not hotwords:
        return None

    dashscope.api_key = api_key
    service = VocabularyService()

    # 构建热词字典（API需要的格式），weight: 1-5，5为最强
    vocabulary = [{"text": word, "weight": 5} for word in hotwords]

    try:
        if phrase_id:
            # 已有热词表，更新
            service.update_vocabulary(phrase_id, vocabulary)
            return phrase_id
        else:
            # 新建热词表
            new_id = service.create_vocabulary(
                target_model="paraformer-realtime-v2",
                prefix="vt",  # voice_typing 缩写
                vocabulary=vocabulary,
            )
            return new_id
    except VocabularyServiceException as e:
        # 如果旧的 phrase_id 失效，创建新的
        if phrase_id:
            try:
                new_id = service.create_vocabulary(
                    target_model="paraformer-realtime-v2",
                    prefix="vt",
                    vocabulary=vocabulary,
                )
                return new_id
            except VocabularyServiceException:
                pass
        print(f"[热词] 同步失败: {e}")
        return None
