#!/usr/bin/env python3
"""测试缓存key模式匹配"""

# 模拟实际的缓存key生成
def generate_cache_key(user_id=None, source=None, search="", date_from="", date_to="", favorite=False, page=1, page_size=20):
    user_part = str(user_id) if user_id is not None else "all"
    source_part = source or "all"
    search_part = search or ""
    date_from_part = date_from or ""
    date_to_part = date_to or ""

    cache_key = (
        f"notes:list:{user_part}:{source_part}:{search_part}:"
        f"{date_from_part}:{date_to_part}:{favorite}:{page}:{page_size}"
    )
    return cache_key

# 生成各种场景的缓存key
scenarios = [
    ("默认列表", {}),
    ("第2页", {"page": 2}),
    ("搜索查询", {"search": "胖爺"}),
    ("来源过滤", {"source": "-1002203159247"}),
    ("收藏过滤", {"favorite": True}),
    ("日期范围", {"date_from": "2024-01-01", "date_to": "2024-12-31"}),
    ("组合条件", {"source": "-1002203159247", "search": "合集", "page": 2}),
]

print("生成的缓存key示例：\n")
for name, params in scenarios:
    key = generate_cache_key(**params)
    print(f"{name:12s}: {key}")

print("\n" + "="*80)
print("\n当前失效模式: notes:list:all:*")
print("\n问题分析:")
print("- ✅ 能匹配: notes:list:all:all:::False:1:20")
print("- ❌ 不能匹配其他所有带参数的key（source、search、date等）")
print("\n解决方案: 失效时需要遍历并删除所有匹配 'notes:list:*' 的key")
