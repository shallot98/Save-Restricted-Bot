#!/bin/bash
# 修复磁力链接转发问题 - 完整流程

echo "========================================================================"
echo "修复磁力链接转发到备份频道的问题"
echo "========================================================================"
echo ""

echo "步骤1: 验证配置文件已更新"
echo "------------------------------------------------------------------------"
python3 -c "
import json

with open('data/watch_config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

for user_id, watches in config.items():
    for watch_key, watch_data in watches.items():
        if isinstance(watch_data, dict):
            source = watch_data.get('source')
            dest = watch_data.get('dest')

            if source == '-1003202156769' and dest:
                print(f'✅ 找到磁力频道转发配置:')
                print(f'   源频道: {source}')
                print(f'   目标频道: {dest}')

                if int(dest) < 0:
                    print(f'   ✅ 目标ID格式正确（频道/群组）')
                else:
                    print(f'   ❌ 目标ID格式错误（应该是负数）')
                    exit(1)
"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 配置验证失败！"
    exit 1
fi

echo ""
echo "步骤2: 重启Bot以应用新配置"
echo "------------------------------------------------------------------------"
docker-compose restart bot

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Bot重启失败！"
    exit 1
fi

echo ""
echo "✅ Bot已重启"
echo ""
echo "步骤3: 等待Bot启动并初始化Peer缓存（30秒）"
echo "------------------------------------------------------------------------"
sleep 5

echo "查看启动日志（前50行）:"
docker logs --tail 50 save-restricted-bot-bot 2>&1 | grep -E "Peer|缓存|初始化|✅|❌" || echo "（未找到相关日志）"

echo ""
echo "========================================================================"
echo "修复完成！"
echo "========================================================================"
echo ""
echo "下一步操作:"
echo "  1. 查看完整日志确认Peer缓存成功:"
echo "     docker logs -f save-restricted-bot-bot"
echo ""
echo "  2. 在磁力频道发送测试消息:"
echo "     magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678"
echo ""
echo "  3. 检查备份频道是否收到转发的消息"
echo ""
echo "  4. 如果仍然失败，查看日志中的错误信息:"
echo "     docker logs -f save-restricted-bot-bot | grep -E '转发|forward|❌'"
echo ""
echo "========================================================================"
