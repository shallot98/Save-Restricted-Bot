"""
Helper utility functions
"""
import logging

import pyrogram

logger = logging.getLogger(__name__)

# 消息属性 -> 返回的类型名（顺序即优先级，与历史行为一致）
_MEDIA_ATTRIBUTES = (
    ("document", "Document"),
    ("video", "Video"),
    ("animation", "Animation"),
    ("sticker", "Sticker"),
    ("voice", "Voice"),
    ("audio", "Audio"),
    ("photo", "Photo"),
)

UNSUPPORTED_MESSAGE_TYPE = "Unsupported"


def get_message_type(msg: pyrogram.types.messages_and_media.message.Message) -> str:
    """识别消息类型

    Returns:
        "Document"/"Video"/"Animation"/"Sticker"/"Voice"/"Audio"/"Photo"/"Text"，
        无法识别时返回 "Unsupported"。

    失败方向：识别不出来就显式返回 "Unsupported" 并告警，不再伪装成 "Text"
    （投票/位置/联系人等消息此前会被当成正文为空的文本消息转发）。
    """
    for attr, type_name in _MEDIA_ATTRIBUTES:
        if _has_file_id(msg, attr):
            return type_name

    if getattr(msg, "text", None):
        return "Text"

    logger.warning(
        "无法识别的消息类型: message_id=%s chat=%s",
        getattr(msg, "id", None),
        getattr(getattr(msg, "chat", None), "id", None),
    )
    return UNSUPPORTED_MESSAGE_TYPE


def _has_file_id(msg: object, attr: str) -> bool:
    """判断消息的某个媒体属性是否携带 file_id。"""
    try:
        return bool(getattr(getattr(msg, attr), "file_id", None))
    except AttributeError:
        # 属性不存在或为 None：正常的「不是这个类型」，无需日志
        return False
    except Exception as exc:  # 其他异常属于异常情况，需要留痕
        logger.warning("读取消息属性 %s 失败: %s", attr, exc)
        return False
