#!/usr/bin/env python3
"""
验证笔记文本显示修复
检查关键修复是否已正确应用到代码中
"""

import re
import sys

def check_file_content(filepath, patterns, description):
    """检查文件是否包含指定的模式"""
    print(f"\n检查 {description}...")
    print(f"文件: {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        all_found = True
        for pattern_name, pattern in patterns.items():
            if re.search(pattern, content, re.MULTILINE | re.DOTALL):
                print(f"  ✅ {pattern_name}")
            else:
                print(f"  ❌ {pattern_name} - 未找到")
                all_found = False

        return all_found
    except FileNotFoundError:
        print(f"  ❌ 文件不存在")
        return False
    except Exception as e:
        print(f"  ❌ 读取文件时出错: {e}")
        return False

def main():
    print("=" * 60)
    print("笔记文本显示修复验证")
    print("=" * 60)

    results = []

    # 检查 1: templates/notes.html 中的自定义 line-clamp CSS
    patterns_1 = {
        "line-clamp-3 类定义": r"\.line-clamp-3\s*{",
        "-webkit-line-clamp: 3": r"-webkit-line-clamp:\s*3",
        "word-break: break-all": r"word-break:\s*break-all",
        "overflow-wrap: anywhere": r"overflow-wrap:\s*anywhere",
        "max-width: 100%": r"max-width:\s*100%",
    }
    results.append(check_file_content(
        "templates/notes.html",
        patterns_1,
        "自定义 line-clamp CSS"
    ))

    # 检查 2: templates/notes.html 中的展开按钮检测优化
    patterns_2 = {
        "window.load 事件": r"window\.addEventListener\(['\"]load['\"]",
        "setTimeout 延迟": r"setTimeout\(function\(\)",
        "scrollHeight 检测": r"scrollHeight\s*>\s*.*clientHeight",
    }
    results.append(check_file_content(
        "templates/notes.html",
        patterns_2,
        "展开按钮检测优化"
    ))

    # 检查 3: static/css/pages/notes.css 中的文本处理规则
    patterns_3 = {
        ".note-text 类定义": r"\.note-text\s*{",
        "word-break 属性": r"word-break:\s*break-word",
        "overflow-wrap 属性": r"overflow-wrap:\s*break-word",
        "max-height 限制": r"max-height:\s*120px",
    }
    results.append(check_file_content(
        "static/css/pages/notes.css",
        patterns_3,
        "CSS 文本处理规则"
    ))

    # 总结
    print("\n" + "=" * 60)
    print("验证结果总结")
    print("=" * 60)

    if all(results):
        print("✅ 所有修复已正确应用！")
        print("\n建议:")
        print("1. 访问 http://localhost:10000/notes 查看实际效果")
        print("2. 测试包含长文本和磁力链接的笔记")
        print("3. 验证展开/收起按钮功能")
        print("4. 在移动端和桌面端分别测试")
        return 0
    else:
        print("❌ 部分修复未正确应用，请检查上述失败项")
        return 1

if __name__ == "__main__":
    sys.exit(main())
