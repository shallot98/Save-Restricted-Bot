#!/usr/bin/env python3
"""
批量检测和修复DN参数重复问题

扫描数据库中所有笔记,找出可能存在DN重复的笔记并提供修复选项

问题类型：
1. DN参数值内部重复: dn=XX XX XX XX (同一个文本重复多次)
2. 磁力链接粘连: dn=XXXmagnet:?... (缺少分隔符)
3. 重复的中文文本块
"""

import sqlite3
import re
from urllib.parse import quote, unquote_plus
from src.domain.magnet import MagnetLinkParser


def deduplicate_dn_value(dn_value: str) -> str:
    """去除DN参数值中的重复内容

    例如:
    - "文件名 文件名 文件名" -> "文件名"
    - "前缀 后缀 后缀 后缀" -> "前缀 后缀"
    - "前缀 A B A B A B 后缀" -> "前缀 A B 后缀"
    """
    if not dn_value:
        return dn_value

    # 解码URL编码
    decoded = unquote_plus(dn_value)

    # 分词
    parts = decoded.split()
    if len(parts) < 2:
        return decoded

    # 策略1: 检测连续重复的词，只保留一个
    result = []
    prev_part = None
    for part in parts:
        if part != prev_part:
            result.append(part)
            prev_part = part

    if len(result) < len(parts):
        return ' '.join(result)

    # 策略2: 检测连续重复的多词块
    # 例如: "A B A B A B" 或 "前缀 A B A B A B 后缀"
    def find_repeating_block(parts_list):
        """查找并去除连续重复的块，返回去重后的列表"""
        n = len(parts_list)
        if n < 4:  # 至少需要4个词才能有块重复
            return parts_list

        # 尝试不同的块大小 (1-4个词的块)
        for chunk_size in range(1, min(5, n // 2 + 1)):
            i = 0
            new_parts = []
            while i < n:
                # 检查从位置i开始是否有重复块
                chunk = parts_list[i:i + chunk_size]
                if len(chunk) < chunk_size:
                    # 剩余词不够一个块
                    new_parts.extend(parts_list[i:])
                    break

                # 计算这个块重复了多少次
                repeat_count = 1
                j = i + chunk_size
                while j + chunk_size <= n and parts_list[j:j + chunk_size] == chunk:
                    repeat_count += 1
                    j += chunk_size

                if repeat_count >= 2:
                    # 找到重复，只保留一个
                    new_parts.extend(chunk)
                    i = j
                else:
                    # 没有重复，保留当前词并继续
                    new_parts.append(parts_list[i])
                    i += 1

            if len(new_parts) < n:
                return new_parts

        return parts_list

    deduped = find_repeating_block(parts)
    if len(deduped) < len(parts):
        return ' '.join(deduped)

    return decoded


def detect_duplicate_dn_issues(db_path='/root/Save-Restricted-Bot/data/notes.db'):
    """检测所有笔记中的DN重复问题"""
    print("🔍 扫描数据库中的DN重复问题...\n")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 查询所有有磁力链接的笔记
    cursor.execute('''
        SELECT id, message_text, magnet_link, filename
        FROM notes
        WHERE magnet_link IS NOT NULL
        ORDER BY id
    ''')

    rows = cursor.fetchall()
    print(f"📊 总共找到 {len(rows)} 个包含磁力链接的笔记\n")

    suspicious_notes = []

    for note_id, message_text, magnet_link, filename in rows:
        if not message_text:
            continue

        # 策略1: 检测DN参数值内部重复
        # 匹配 dn= 后面的内容
        dn_matches = re.findall(r'[&?]dn=([^&\n]+)', message_text, re.IGNORECASE)
        for dn_raw in dn_matches:
            decoded = unquote_plus(dn_raw)
            deduped = deduplicate_dn_value(dn_raw)
            if len(deduped) < len(decoded) * 0.7:  # 去重后长度减少超过30%
                suspicious_notes.append({
                    'id': note_id,
                    'reason': 'dn_value_duplicated',
                    'details': f"DN值重复: '{decoded[:50]}...' -> '{deduped[:50]}...'",
                    'message_text': message_text,
                    'magnet_link': magnet_link,
                    'filename': filename
                })
                break
        else:
            # 策略2: 检测是否有重复的中文短语(如"XX XX XX")
            repeat_pattern = re.compile(r'([\u4e00-\u9fa5]{5,})\s+\1')
            repeat_matches = repeat_pattern.findall(message_text)
            if repeat_matches:
                suspicious_notes.append({
                    'id': note_id,
                    'reason': 'repeated_chinese_text',
                    'details': f"发现重复文本: {repeat_matches[0][:30]}...",
                    'message_text': message_text,
                    'magnet_link': magnet_link,
                    'filename': filename
                })
                continue

    conn.close()

    print(f"⚠️ 发现 {len(suspicious_notes)} 个可疑笔记:\n")

    for i, note in enumerate(suspicious_notes, 1):
        print(f"{i}. 笔记ID {note['id']}:")
        print(f"   原因: {note['reason']}")
        print(f"   详情: {note['details']}")
        print(f"   message_text 长度: {len(note['message_text'])} 字符")
        print(f"   message_text 预览: {note['message_text'][:100]}...")
        print()

    return suspicious_notes


def fix_dn_in_message_text(message_text: str, magnet_link: str = None, filename: str = None) -> str:
    """修复 message_text 中的 DN 参数重复问题

    处理以下情况：
    1. DN参数值内部重复: dn=XX XX XX XX -> dn=XX
    2. 多余的空格
    """
    if not message_text:
        return message_text

    fixed_text = message_text

    # 修复每个 DN 参数值内部的重复
    def fix_dn_value(match):
        prefix = match.group(1)  # &dn= 或 ?dn=
        dn_raw = match.group(2)   # DN 参数值

        # 去除重复
        deduped = deduplicate_dn_value(dn_raw)

        # 如果没有变化，返回原值
        if deduped == unquote_plus(dn_raw):
            return match.group(0)

        return f"{prefix}{deduped}"

    # 匹配 &dn= 或 ?dn= 及其后面的值
    fixed_text = re.sub(
        r'([&?]dn=)([^&\n]+)',
        fix_dn_value,
        fixed_text,
        flags=re.IGNORECASE
    )

    # 清理多余的空格（超过2个连续空格的替换为1个）
    fixed_text = re.sub(r' {3,}', ' ', fixed_text)

    return fixed_text


def fix_note_dn_duplication(note_id, db_path='/root/Save-Restricted-Bot/data/notes.db', dry_run=False):
    """修复单个笔记的DN重复问题

    Args:
        note_id: 笔记ID
        db_path: 数据库路径
        dry_run: 如果为True，只显示将要做的修改，不实际写入
    """
    print(f"\n🔧 开始修复笔记 {note_id}{'（预览模式）' if dry_run else ''}...\n")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 读取笔记数据
        cursor.execute('SELECT message_text, magnet_link, filename FROM notes WHERE id = ?', (note_id,))
        row = cursor.fetchone()

        if not row:
            print(f"❌ 笔记 {note_id} 不存在")
            return False

        message_text, magnet_link, filename = row

        print(f"📄 当前状态:")
        print(f"  message_text 长度: {len(message_text)} 字符")
        if magnet_link:
            print(f"  magnet_link: {magnet_link[:80]}...")
        print(f"  filename: {filename}\n")

        # 使用统一的修复函数
        fixed_message_text = fix_dn_in_message_text(message_text, magnet_link, filename)

        # 显示修复结果
        print(f"📝 修复后的 message_text 长度: {len(fixed_message_text)} 字符")
        print(f"   字符变化: {len(fixed_message_text) - len(message_text)}")

        if fixed_message_text == message_text:
            print(f"\n✅ 笔记 {note_id} 无需修复")
            return True

        # 显示修复前后的对比
        print(f"\n📋 修复前预览:")
        print(f"   {message_text[:200]}...")
        print(f"\n📋 修复后预览:")
        print(f"   {fixed_message_text[:200]}...")

        if dry_run:
            print(f"\n⚠️ 预览模式，未实际修改")
            return True

        # 更新数据库
        cursor.execute('UPDATE notes SET message_text = ? WHERE id = ?', (fixed_message_text, note_id))
        conn.commit()

        print(f"\n✅ 笔记 {note_id} 修复完成!")

        return True

    except Exception as e:
        print(f"❌ 修复失败: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False

    finally:
        conn.close()


def batch_fix_all_suspicious_notes(dry_run=False):
    """批量修复所有可疑笔记

    Args:
        dry_run: 如果为True，只显示将要做的修改，不实际写入
    """
    suspicious_notes = detect_duplicate_dn_issues()

    if not suspicious_notes:
        print("✅ 未发现任何可疑笔记,无需修复!")
        return

    print(f"\n🔧 准备修复 {len(suspicious_notes)} 个可疑笔记{'（预览模式）' if dry_run else ''}...\n")

    success_count = 0
    for note in suspicious_notes:
        note_id = note['id']
        print(f"{'='*60}")
        if fix_note_dn_duplication(note_id, dry_run=dry_run):
            success_count += 1
        print()

    print(f"\n{'='*60}")
    print(f"📊 修复完成统计:")
    print(f"   总共发现: {len(suspicious_notes)} 个可疑笔记")
    print(f"   成功修复: {success_count} 个")
    if dry_run:
        print(f"   ⚠️ 预览模式，以上修改均未实际执行")


if __name__ == '__main__':
    import sys

    dry_run = '--dry-run' in sys.argv or '-n' in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith('-')]

    if args:
        # 修复指定笔记
        note_id = int(args[0])
        fix_note_dn_duplication(note_id, dry_run=dry_run)
    else:
        # 批量检测和修复
        batch_fix_all_suspicious_notes(dry_run=dry_run)
