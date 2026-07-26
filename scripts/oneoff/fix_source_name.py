#!/usr/bin/env python3
"""
修复数据库中被截断的 source_name 字段

问题：由于之前的 bug，部分笔记的 source_name 在遇到空格时被截断
例如："磁力备份" 被截断为 "磁力"

修复方案：
1. 查找同一个 source_chat_id 下的正确 source_name
2. 更新被截断的记录
"""

import sqlite3
import sys
from collections import defaultdict

DATABASE_FILE = "data/notes.db"


def analyze_source_names():
    """分析数据库中的 source_name 数据"""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # 统计每个 source_chat_id 的 source_name 分布
    cursor.execute("""
        SELECT source_chat_id, source_name, COUNT(*) as count
        FROM notes
        WHERE source_name IS NOT NULL
        GROUP BY source_chat_id, source_name
        ORDER BY source_chat_id, count DESC
    """)

    results = cursor.fetchall()
    conn.close()

    # 按 source_chat_id 分组
    chat_names = defaultdict(list)
    for chat_id, name, count in results:
        chat_names[chat_id].append((name, count))

    print("=" * 80)
    print("数据库中的 source_name 统计：")
    print("=" * 80)

    for chat_id, names in chat_names.items():
        print(f"\n频道 ID: {chat_id}")
        for name, count in names:
            print(f"  - '{name}': {count} 条记录")

    return chat_names


def find_correct_names(chat_names):
    """找出需要修复的记录

    规则：
    1. 如果一个 source_chat_id 有多个 source_name
    2. 其中一个是另一个的前缀（说明被截断了）
    3. 选择较长的作为正确的名称
    """
    fixes = []

    for chat_id, names in chat_names.items():
        if len(names) <= 1:
            continue

        # 按长度排序，长的在前
        sorted_names = sorted(names, key=lambda x: len(x[0]), reverse=True)

        # 检查是否有截断的情况
        correct_name = sorted_names[0][0]

        for name, count in sorted_names[1:]:
            # 如果短名称是长名称的前缀，说明被截断了
            if correct_name.startswith(name):
                fixes.append({
                    'chat_id': chat_id,
                    'wrong_name': name,
                    'correct_name': correct_name,
                    'count': count
                })

    return fixes


def preview_fixes(fixes):
    """预览需要修复的记录"""
    if not fixes:
        print("\n✅ 没有发现需要修复的记录")
        return False

    print("\n" + "=" * 80)
    print("发现需要修复的记录：")
    print("=" * 80)

    total_count = 0
    for fix in fixes:
        print(f"\n频道 ID: {fix['chat_id']}")
        print(f"  错误名称: '{fix['wrong_name']}'")
        print(f"  正确名称: '{fix['correct_name']}'")
        print(f"  影响记录: {fix['count']} 条")
        total_count += fix['count']

    print(f"\n总计需要修复: {total_count} 条记录")
    return True


def apply_fixes(fixes, dry_run=True, limit=None):
    """应用修复

    Args:
        fixes: 修复列表
        dry_run: 是否为预览模式（不实际修改）
        limit: 限制修复的记录数量（None表示不限制）
    """
    if not fixes:
        return

    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    print("\n" + "=" * 80)
    if dry_run:
        print("预览模式 - 不会实际修改数据库")
    else:
        print("开始修复数据库...")
        if limit:
            print(f"限制修复数量: 最近 {limit} 条记录")
    print("=" * 80)

    total_updated = 0

    for fix in fixes:
        chat_id = fix['chat_id']
        wrong_name = fix['wrong_name']
        correct_name = fix['correct_name']

        if dry_run:
            # 预览模式：只查询不更新
            cursor.execute("""
                SELECT id, source_name
                FROM notes
                WHERE source_chat_id = ? AND source_name = ?
                ORDER BY id DESC
                LIMIT 5
            """, (chat_id, wrong_name))

            samples = cursor.fetchall()
            print(f"\n频道 {chat_id}:")
            print(f"  将 '{wrong_name}' 更新为 '{correct_name}'")
            print(f"  示例记录 ID (最新的5条): {[s[0] for s in samples]}")
            if limit:
                print(f"  实际修复时将只修复最近 {limit} 条")
        else:
            # 实际修复
            if limit:
                # 先获取需要更新的记录ID（按ID降序，取最新的N条）
                cursor.execute("""
                    SELECT id
                    FROM notes
                    WHERE source_chat_id = ? AND source_name = ?
                    ORDER BY id DESC
                    LIMIT ?
                """, (chat_id, wrong_name, limit))

                ids_to_update = [row[0] for row in cursor.fetchall()]

                if ids_to_update:
                    # 使用IN子句更新这些记录
                    placeholders = ','.join('?' * len(ids_to_update))
                    cursor.execute(f"""
                        UPDATE notes
                        SET source_name = ?
                        WHERE id IN ({placeholders})
                    """, [correct_name] + ids_to_update)

                    updated = cursor.rowcount
                    total_updated += updated
                    print(f"\n✅ 频道 {chat_id}: 已更新 {updated} 条记录（最新的 {limit} 条）")
                    print(f"   '{wrong_name}' → '{correct_name}'")
                    print(f"   更新的记录 ID 范围: {min(ids_to_update)} - {max(ids_to_update)}")
            else:
                # 不限制数量，更新所有记录
                cursor.execute("""
                    UPDATE notes
                    SET source_name = ?
                    WHERE source_chat_id = ? AND source_name = ?
                """, (correct_name, chat_id, wrong_name))

                updated = cursor.rowcount
                total_updated += updated
                print(f"\n✅ 频道 {chat_id}: 已更新 {updated} 条记录")
                print(f"   '{wrong_name}' → '{correct_name}'")

    if not dry_run:
        conn.commit()
        print(f"\n" + "=" * 80)
        print(f"✅ 修复完成！共更新 {total_updated} 条记录")
        print("=" * 80)

    conn.close()


def main():
    """主函数"""
    print("=" * 80)
    print("source_name 修复工具")
    print("=" * 80)

    # 分析数据
    chat_names = analyze_source_names()

    # 找出需要修复的记录
    fixes = find_correct_names(chat_names)

    # 预览修复
    has_fixes = preview_fixes(fixes)

    if not has_fixes:
        return

    # 检查是否为实际修复模式
    if '--apply' in sys.argv:
        print("\n" + "=" * 80)
        response = input("⚠️  确认要修复数据库吗？(输入 'yes' 确认): ")
        if response.lower() == 'yes':
            apply_fixes(fixes, dry_run=False)
        else:
            print("❌ 已取消修复")
    else:
        print("\n" + "=" * 80)
        print("💡 这是预览模式，不会实际修改数据库")
        print("💡 如果确认要修复，请运行: python3 fix_source_name.py --apply")
        print("=" * 80)

        # 预览模式下显示示例
        apply_fixes(fixes, dry_run=True)


if __name__ == "__main__":
    main()
