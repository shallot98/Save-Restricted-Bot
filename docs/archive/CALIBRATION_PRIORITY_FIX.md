# 校准优先级修复总结

## 问题描述

用户反馈：虽然909笔记的两个磁力链接都进入了校准队列，但实际只有第一个磁力链接发送给了Telegram机器人校准，第二个磁力链接使用了qBittorrent API校准。

## 原因分析

校准逻辑的优先级设置错误：
- **自动校准**：应该优先使用Telegram机器人（避免占用qBittorrent资源）
- **手动校准**：应该优先使用qBittorrent API（更快）

但原代码中，自动校准和手动校准都使用相同的优先级（优先qBittorrent API）。

## 解决方案

### 1. 修改`calibrate_magnet`方法签名

添加`prefer_bot`参数来区分自动和手动校准：

```python
def calibrate_magnet(self, magnet_hash: str, timeout: int = 30, prefer_bot: bool = True) -> Optional[str]:
    """校准单个磁力链接，获取真实文件名

    Args:
        magnet_hash: 磁力链接的info hash
        timeout: 超时时间（秒）
        prefer_bot: 是否优先使用机器人方式（True=自动校准优先机器人，False=手动校准优先qBittorrent）

    Returns:
        文件名，失败返回None
    """
```

### 2. 实现不同的优先级逻辑

#### 自动校准模式（prefer_bot=True）
```python
if prefer_bot:
    # 自动校准：优先使用Telegram机器人
    logger.info(f"🔄 自动校准模式：优先使用Telegram机器人")

    # 优先尝试机器人方式
    if os.path.exists(bot_script_path):
        logger.info(f"🔄 使用Telegram机器人校准: {magnet_hash[:16]}...")
        # ... 执行校准 ...

    # 回退到qBittorrent API方式
    if not filename and os.path.exists(qbt_script_path):
        logger.info(f"🔄 尝试使用qBittorrent API校准: {magnet_hash[:16]}...")
        # ... 执行校准 ...
```

#### 手动校准模式（prefer_bot=False）
```python
else:
    # 手动校准：优先使用qBittorrent API
    logger.info(f"🔄 手动校准模式：优先使用qBittorrent API")

    # 优先尝试qBittorrent API方式
    if os.path.exists(qbt_script_path):
        logger.info(f"🔄 尝试使用qBittorrent API校准: {magnet_hash[:16]}...")
        # ... 执行校准 ...

    # 回退到机器人方式
    if not filename and os.path.exists(bot_script_path):
        logger.info(f"🔄 使用Telegram机器人校准: {magnet_hash[:16]}...")
        # ... 执行校准 ...
```

### 3. 更新调用点

#### 自动校准（CalibrationManager.process_calibration_task）
```python
# 校准该磁力链接（自动校准优先使用机器人）
timeout = self.config.get('timeout_per_magnet', 30)
filename = self.calibrate_magnet(magnet_hash, timeout, prefer_bot=True)
```

#### 手动校准（Web API）
Web API的手动校准已经是优先qBittorrent API，无需修改。

## 测试结果

### 测试笔记909
```
笔记内容：
猥琐眼镜kk哥全集127G超清无水印
magnet:?xt=urn:btih:094DD6D482B31DCF7DDBE7D3F45111349D8A58C6&dn=[ThZu.Cc]猥琐眼镜kk哥全集127G超清无水印
magnet:?xt=urn:btih:292DA7E94DC52C42D8603284379E89A727C1E46D&dn=YE0505_16_眼镜KK哥绳艺教学【71V】66G
```

### 自动校准日志
```
2025-12-17 22:50:11,892 - INFO - 🔧 开始处理校准任务: task_id=171, note_id=909, hash=094DD6D482B31DCF..., retry=0
2025-12-17 22:50:11,893 - INFO - 🔄 自动校准模式：优先使用Telegram机器人
2025-12-17 22:50:11,893 - INFO - 🔄 使用Telegram机器人校准: 094DD6D482B31DCF...
2025-12-17 22:50:20,272 - INFO - ✅ Telegram机器人校准成功: [ThZu.Cc]猥琐眼镜kk哥全集127G超清无水印...

2025-12-17 22:50:20,273 - INFO - 🔧 开始处理校准任务: task_id=172, note_id=909, hash=292DA7E94DC52C42..., retry=0
2025-12-17 22:50:20,274 - INFO - 🔄 自动校准模式：优先使用Telegram机器人
2025-12-17 22:50:20,274 - INFO - 🔄 使用Telegram机器人校准: 292DA7E94DC52C42...
2025-12-17 22:50:26,913 - INFO - ✅ Telegram机器人校准成功: YE0505_16_眼镜KK哥绳艺教学【71V】66G...
```

✅ **两个磁力链接都使用Telegram机器人校准成功！**

## 改进优势

### 1. 资源优化
- ✅ 自动校准使用Telegram机器人，不占用qBittorrent资源
- ✅ 手动校准使用qBittorrent API，速度更快

### 2. 灵活性
- ✅ 通过`prefer_bot`参数灵活控制优先级
- ✅ 两种方式互为备份，提高成功率

### 3. 可追踪性
- ✅ 日志清晰显示使用的校准模式
- ✅ 便于问题定位和性能分析

## 部署说明

由于Docker构建缓存问题，当前采用直接复制文件到容器的方式：

```bash
# 复制更新后的文件到容器
docker cp /root/Save-Restricted-Bot/bot/services/calibration_manager.py save-restricted-bot:/app/bot/services/calibration_manager.py

# 重启容器
docker compose restart
```

后续正式部署时，需要重新构建镜像：

```bash
# 删除旧镜像
docker rmi save-restricted-bot:latest

# 重新构建
docker compose build --no-cache

# 重启容器
docker compose restart
```

## 日期
2025-12-17
