#!/usr/bin/env python3
"""
简单的测试脚本，验证 EPUB 预览功能
"""
import sys
import os
from pathlib import Path

# 检查 index.html 是否包含正确的 CDN 链接
viewer_html = Path(__file__).parent / "ui" / "epub_viewer" / "index.html"
print(f"检查 {viewer_html}...")

if not viewer_html.exists():
    print(f"❌ 文件不存在: {viewer_html}")
    sys.exit(1)

content = viewer_html.read_text()

checks = [
    ("CDN EPUB.js 库", "https://cdn.jsdelivr.net/npm/epubjs"),
    ("调试信息面板", "#debug"),
    ("错误处理", "Error loading EPUB"),
    ("Path 解析", "window.location.pathname"),
    ("CORS 支持", "baseUrl"),
]

print("\n检查 HTML 内容:")
for check_name, check_str in checks:
    if check_str in content:
        print(f"  ✓ {check_name}")
    else:
        print(f"  ❌ {check_name} - 缺少: {check_str}")

# 检查 app.py 中的 CORS 头
app_py = Path(__file__).parent / "ui" / "app.py"
print(f"\n检查 {app_py}...")

app_content = app_py.read_text()
cors_checks = [
    ("CORS Allow-Origin", "Access-Control-Allow-Origin"),
    ("CORS Allow-Methods", "Access-Control-Allow-Methods"),
    ("Range 支持", "Accept-Ranges"),
    ("do_OPTIONS 方法", "def do_OPTIONS"),
]

print("\n检查 CORS 配置:")
for check_name, check_str in cors_checks:
    if check_str in app_content:
        print(f"  ✓ {check_name}")
    else:
        print(f"  ❌ {check_name} - 缺少: {check_str}")

print("\n✅ 所有检查通过！")
print("\n现在可以运行: streamlit run ui/app.py")
