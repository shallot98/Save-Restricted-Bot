#!/bin/bash
# 测试 WebDAV 缓存并发性能

echo "=== WebDAV 并发缓存性能测试 ==="
echo ""

# 清空缓存
echo "1. 清空缓存目录..."
docker exec save-restricted-bot-web rm -rf /app/data/cache/webdav/*
echo "✅ 缓存已清空"
echo ""

# 等待服务稳定
sleep 2

echo "2. 开始监控日志（请在浏览器中打开 http://你的域名:10000/notes）"
echo "   按 Ctrl+C 停止监控"
echo ""

# 实时监控日志，显示下载和缓存情况
docker logs -f save-restricted-bot-web 2>&1 | grep --line-buffered -E "Cache miss|Cached:|慢请求" | while read line; do
    timestamp=$(date '+%H:%M:%S')
    echo "[$timestamp] $line"
done
