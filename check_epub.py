#!/usr/bin/env python3
"""
验证生成的 EPUB 文件是否有效的脚本
"""
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

def check_epub(epub_path):
    """检查 EPUB 文件的有效性"""
    print(f"检查 EPUB 文件: {epub_path}")
    print("=" * 60)
    
    if not epub_path.exists():
        print(f"❌ 文件不存在: {epub_path}")
        return False
    
    file_size = epub_path.stat().st_size
    print(f"📦 文件大小: {file_size:,} 字节")
    
    if file_size == 0:
        print("❌ 文件为空！")
        return False
    
    if file_size < 1000:
        print("⚠️  文件非常小，可能存在问题")
    
    # 检查是否是有效的 ZIP 文件（EPUB 是 ZIP 格式）
    try:
        with zipfile.ZipFile(epub_path, 'r') as zip_file:
            print(f"\n✓ 有效的 ZIP 文件")
            
            # 列出文件
            file_list = zip_file.namelist()
            print(f"✓ 包含 {len(file_list)} 个文件")
            
            # 检查必需的文件
            required_files = [
                'mimetype',
                'META-INF/container.xml',
                'META-INF/package.opf'
            ]
            
            print("\n检查必需文件:")
            for required in required_files:
                if required in file_list:
                    print(f"  ✓ {required}")
                else:
                    print(f"  ❌ {required} (缺少)")
            
            # 尝试读取 package.opf
            try:
                with zip_file.open('META-INF/package.opf') as f:
                    opf_content = f.read()
                    root = ET.fromstring(opf_content)
                    print(f"\n✓ 成功解析 package.opf")
                    print(f"  文件大小: {len(opf_content)} 字节")
            except Exception as e:
                print(f"\n❌ 无法解析 package.opf: {e}")
                return False
            
            # 尝试列出 XHTML 文件
            xhtml_files = [f for f in file_list if f.endswith('.xhtml') or f.endswith('.html')]
            print(f"\n包含的内容文件:")
            if xhtml_files:
                for xhtml in xhtml_files[:5]:  # 只显示前 5 个
                    try:
                        with zip_file.open(xhtml) as f:
                            content = f.read()
                            print(f"  ✓ {xhtml} ({len(content)} 字节)")
                    except Exception as e:
                        print(f"  ❌ {xhtml}: {e}")
                if len(xhtml_files) > 5:
                    print(f"  ... 以及其他 {len(xhtml_files) - 5} 个文件")
            else:
                print("  ❌ 没有找到 XHTML 文件!")
                return False
            
            return True
            
    except zipfile.BadZipFile:
        print("❌ 不是有效的 ZIP 文件（EPUB 必须是 ZIP 格式）")
        return False
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        return False

if __name__ == "__main__":
    # 查找最近的 EPUB 文件
    from datetime import datetime
    import tempfile
    
    # 检查临时目录中是否有 EPUB 文件
    temp_dir = Path(tempfile.gettempdir())
    
    print("搜索 EPUB 文件...\n")
    
    epub_files = []
    for temp_subdir in temp_dir.glob('tmp*'):
        if temp_subdir.is_dir():
            for epub in temp_subdir.rglob('*.epub'):
                mtime = epub.stat().st_mtime
                epub_files.append((mtime, epub))
    
    if epub_files:
        # 获取最新的 EPUB 文件
        epub_files.sort(reverse=True)
        latest_epub = epub_files[0][1]
        
        print(f"最新的 EPUB 文件: {latest_epub}")
        print(f"修改时间: {datetime.fromtimestamp(epub_files[0][0])}\n")
        
        success = check_epub(latest_epub)
        
        print("\n" + "=" * 60)
        if success:
            print("✅ EPUB 文件看起来有效")
        else:
            print("❌ EPUB 文件可能有问题")
    else:
        print("❌ 没有找到 EPUB 文件")
        print("\n建议:")
        print("1. 首先运行 'streamlit run ui/app.py'")
        print("2. 上传 PDF 并转换")
        print("3. 然后运行此脚本来检查生成的 EPUB")
