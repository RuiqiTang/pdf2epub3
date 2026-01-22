#!/usr/bin/env python3
"""
诊断脚本：验证 EPUB 预览功能的所有组件
"""
import sys
from pathlib import Path

print("=" * 60)
print("EPUB 预览功能诊断")
print("=" * 60)

# 1. 检查必需的文件
print("\n📁 检查文件存在性:")
files_to_check = [
    ("HTML 查看器", "ui/epub_viewer/index.html"),
    ("应用文件", "ui/app.py"),
    ("主程序", "main.py"),
]

all_exist = True
for name, path_str in files_to_check:
    path = Path(path_str)
    if path.exists():
        print(f"  ✓ {name}: {path}")
    else:
        print(f"  ❌ {name}: {path} (不存在)")
        all_exist = False

if not all_exist:
    print("\n❌ 缺少关键文件，无法继续")
    sys.exit(1)

# 2. 检查代码配置
print("\n⚙️  检查代码配置:")

# 检查 index.html
html_content = Path("ui/epub_viewer/index.html").read_text()
html_checks = [
    ("CDN EPUB.js", "https://cdn.jsdelivr.net/npm/epubjs"),
    ("调试面板", 'id="debug"'),
    ("时间戳日志", "toLocaleTimeString"),
    ("HEAD 请求检查", "method: 'HEAD'"),
    ("简化的 URL 构造", "window.location.origin"),
]

print("  HTML 检查:")
for check_name, check_str in html_checks:
    if check_str in html_content:
        print(f"    ✓ {check_name}")
    else:
        print(f"    ❌ {check_name} (缺少)")

# 检查 app.py
app_content = Path("ui/app.py").read_text()
app_checks = [
    ("CORS 头", "Access-Control-Allow-Origin"),
    ("HEAD 方法", "def do_HEAD"),
    ("持久临时目录", "_TEMP_DIR"),
    ("自定义处理器", "class CustomHTTPRequestHandler"),
]

print("  App.py 检查:")
for check_name, check_str in app_checks:
    if check_str in app_content:
        print(f"    ✓ {check_name}")
    else:
        print(f"    ❌ {check_name} (缺少)")

print("\n" + "=" * 60)
print("✅ 诊断完成！")
print("\n建议的测试步骤:")
print("1. 运行: streamlit run ui/app.py")
print("2. 打开 http://localhost:8501")
print("3. 上传一个 PDF 文件")
print("4. 点击 '开始转换' 按钮")
print("5. 等待转换完成，检查预览区域")
print("6. 如有问题，查看右下角的调试面板")
print("\n调试面板会显示:")
print("  - Page loaded: 页面已加载")
print("  - ePub library loaded: CDN 库已加载")
print("  - HEAD request status: 文件可访问性")
print("  - Book ready: EPUB 解析成功")
print("  - ✓ EPUB loaded and displayed: 成功！")
print("=" * 60)
