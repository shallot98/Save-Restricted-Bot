# 🚨 自动转发失效快速修复指南

## 症状
- ✅ Bot 运行正常，命令有效
- ❌ 自动转发不工作，无消息被转发
- ❌ 日志为空，无转发记录

## 快速修复（v2.3.2）

### 1. 更新代码
```bash
git pull origin main
```

### 2. 重启服务
```bash
# Docker
docker-compose restart

# 直接运行
pkill -f "python.*main.py"
python3 main.py
```

### 3. 验证修复
启动后应该看到：
```
✅ 正在注册 auto_forward 消息处理器...
✅ Bot 客户端已启动
✅ User 客户端已启动（监听消息中...）
⏳ 进入空闲模式，保持客户端运行...
```

### 4. 测试转发
发送测试消息，日志应显示：
```
📨 收到消息 - 来源: ...
✅ 匹配任务: ...
🎯 消息通过所有过滤器，开始处理...
✅ 已转发消息到 ...
```

## 问题原因
**`acc` 客户端未运行消息处理循环**
- 旧代码只调用了 `bot.run()` (阻塞)
- 新代码使用 `bot.start()` + `idle()` (双客户端并发)

## 技术细节
查看 `FIX_AUTO_FORWARD.md` 了解完整说明

## 仍有问题？

### 检查 String Session
```bash
# 确认环境变量
echo $STRING

# 或检查配置文件
cat /data/save_restricted_bot/config/config.json
```

如果看到：
```
⚠️ 未配置 String Session (acc 客户端)，自动转发功能将不可用
```
需要配置 String Session：
```bash
python3 setup.py
```

### 检查监控配置
```bash
cat /data/save_restricted_bot/config/watch_config.json
```

应该包含监控任务配置。

### 运行测试
```bash
python3 test_auto_forward_fix.py
```

应该全部通过（4/4）。

---

**版本**: v2.3.2  
**优先级**: 🔴 必须升级
