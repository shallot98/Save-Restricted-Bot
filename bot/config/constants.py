"""
应用配置常量
集中管理所有可配置的常量值
"""
import os
import secrets


class AppConstants:
    """应用级配置常量"""

    # Web界面配置
    NOTES_PER_PAGE = int(os.getenv('NOTES_PER_PAGE', 50))
    """每页显示的笔记数量"""

    # 安全：自动生成随机密钥，或使用环境变量
    FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY') or secrets.token_hex(32)
    """Flask会话密钥 - 自动生成或从环境变量读取"""

    SESSION_LIFETIME_DAYS = int(os.getenv('SESSION_LIFETIME_DAYS', 30))
    """会话有效期（天）"""


class DatabaseConstants:
    """数据库配置常量"""

    DB_DEDUP_WINDOW = int(os.getenv('DB_DEDUP_WINDOW', 300))
    """消息去重时间窗口（秒）"""

    DB_CONNECTION_TIMEOUT = int(os.getenv('DB_CONNECTION_TIMEOUT', 30))
    """数据库连接超时（秒）"""


class CalibrationConstants:
    """校准系统配置常量"""

    # 默认延迟时间（秒）
    DEFAULT_FIRST_DELAY = int(os.getenv('CALIBRATION_FIRST_DELAY', 600))
    """首次校准延迟（秒）"""

    DEFAULT_RETRY_DELAY_1 = int(os.getenv('CALIBRATION_RETRY_DELAY_1', 3600))
    """第一次重试延迟（秒）"""

    DEFAULT_RETRY_DELAY_2 = int(os.getenv('CALIBRATION_RETRY_DELAY_2', 14400))
    """第二次重试延迟（秒）"""

    DEFAULT_RETRY_DELAY_3 = int(os.getenv('CALIBRATION_RETRY_DELAY_3', 28800))
    """第三次重试延迟（秒）"""

    # 并发和超时配置
    DEFAULT_MAX_RETRIES = int(os.getenv('CALIBRATION_MAX_RETRIES', 3))
    """最大重试次数"""

    DEFAULT_CONCURRENT_LIMIT = int(os.getenv('CALIBRATION_CONCURRENT_LIMIT', 5))
    """最大并发校准任务数"""

    DEFAULT_TIMEOUT_PER_MAGNET = int(os.getenv('CALIBRATION_TIMEOUT_PER_MAGNET', 30))
    """单个磁力链接校准超时（秒）"""

    DEFAULT_BATCH_TIMEOUT = int(os.getenv('CALIBRATION_BATCH_TIMEOUT', 300))
    """批量校准超时（秒）"""

    # 调度器配置
    SCHEDULER_INTERVAL = int(os.getenv('CALIBRATION_SCHEDULER_INTERVAL', 60))
    """校准调度器执行间隔（秒）"""


class MessageConstants:
    """消息处理配置常量"""

    MESSAGE_FORWARD_DELAY = float(os.getenv('MESSAGE_FORWARD_DELAY', 1.0))
    """消息转发延迟（秒），避免触发Telegram限流"""

    DOWNLOAD_STATUS_UPDATE_INTERVAL = float(os.getenv('DOWNLOAD_STATUS_UPDATE_INTERVAL', 0.5))
    """下载状态更新间隔（秒）"""

    UPLOAD_STATUS_UPDATE_INTERVAL = float(os.getenv('UPLOAD_STATUS_UPDATE_INTERVAL', 0.5))
    """上传状态更新间隔（秒）"""


class StorageConstants:
    """存储配置常量"""

    MEDIA_CHUNK_SIZE = int(os.getenv('MEDIA_CHUNK_SIZE', 8192))
    """媒体文件传输块大小（字节）"""

    WEBDAV_CONNECTION_TIMEOUT = int(os.getenv('WEBDAV_CONNECTION_TIMEOUT', 30))
    """WebDAV连接超时（秒）"""

    CACHE_MAX_AGE = int(os.getenv('CACHE_MAX_AGE', 31536000))
    """静态资源缓存时间（秒），默认1年"""


class LoggingConstants:
    """日志配置常量"""

    LOG_MAX_BYTES = int(os.getenv('LOG_MAX_BYTES', 10 * 1024 * 1024))
    """单个日志文件最大大小（字节），默认10MB"""

    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))
    """日志文件备份数量"""

    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    """日志级别"""


# 向后兼容：导出到根命名空间
NOTES_PER_PAGE = AppConstants.NOTES_PER_PAGE
DB_DEDUP_WINDOW = DatabaseConstants.DB_DEDUP_WINDOW
MESSAGE_FORWARD_DELAY = MessageConstants.MESSAGE_FORWARD_DELAY
