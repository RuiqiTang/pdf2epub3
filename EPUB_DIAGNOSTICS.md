# EPUB 预览诊断指南

## 当前症状
- ✓ 页面加载成功
- ✓ EPUB.js 库加载成功
- ✓ 文件可以通过 HTTP 访问 (HEAD 200)
- ✗ book.ready Promise 从未 resolve

## 可能原因

### 1. 生成的 EPUB 文件无效 (最可能)
- PDF 转换过程中出错
- 生成的 EPUB 缺少必要文件或结构不正确
- EPUB.js 无法解析文件格式

### 2. EPUB.js 配置问题
- 库版本不兼容
- 缺少必要的配置选项
- 跨域问题（虽然已配置 CORS）

## 诊断步骤

### 第一步：验证生成的 EPUB 文件

1. 运行转换：
```bash
streamlit run ui/app.py
```

2. 上传任何 PDF 文件

3. 等待转换完成并生成预览

4. 在另一个终端运行：
```bash
python check_epub.py
```

这会显示：
- ✓ EPUB 文件大小
- ✓ ZIP 文件有效性
- ✓ 必需文件存在
- ✓ 内容文件数量
- ✓ 具体错误信息

### 第二步：检查浏览器控制台

1. 打开 Streamlit 应用
2. 按 F12 打开开发者工具
3. 切换到 "Console" 标签页
4. 观察错误信息

### 第三步：查看调试面板

预览窗口右下角的绿色面板会显示详细的加载过程。

## 可能的修复方案

### 如果 EPUB 文件无效

检查 `core/epub_builder.py`，确保：
1. 正确生成了 mimetype 文件
2. 正确生成了 META-INF/container.xml
3. 正确生成了 META-INF/package.opf
4. 正确生成了内容 XHTML 文件

### 如果 EPUB 文件有效但 EPUB.js 无法解析

1. 尝试使用更新的 EPUB.js 版本：
   ```html
   <script src="https://cdn.jsdelivr.net/npm/epubjs@0.4.1/dist/epub.min.js"></script>
   ```

2. 添加详细的调试日志（已在最新版本中完成）

## 快速测试

```bash
# 1. 启动应用
streamlit run ui/app.py

# 2. 上传 PDF 并转换

# 3. 检查 EPUB 文件
python check_epub.py

# 4. 查看输出，特别注意：
#    - 文件大小（应该 > 10KB）
#    - ZIP 有效性
#    - 包含的文件数
#    - 任何错误消息
```

## 调试 EPUB 文件内容

如果需要手动检查 EPUB 文件，可以这样做：

```bash
# 1. 找到最新的 EPUB 文件
find /tmp -name "*.epub" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -f2- -d" "

# 2. 解压并检查结构
unzip -l /path/to/output.epub

# 3. 查看核心文件
unzip -p /path/to/output.epub META-INF/container.xml
unzip -p /path/to/output.epub META-INF/package.opf
```

## 下一步

1. **立即运行** `python check_epub.py`，提供输出
2. **检查** 浏览器控制台中是否有特定的错误信息
3. **查看** 调试面板中的完整日志，特别是超时时的错误
4. 根据输出信息，我可以继续诊断问题

## 相关文件

- 前端代码: `ui/epub_viewer/index.html`
- HTTP 服务器: `ui/app.py` (CustomHTTPRequestHandler)
- EPUB 生成: `core/epub_builder.py`
- 转换管道: `main.py`
- 诊断工具: `check_epub.py`
