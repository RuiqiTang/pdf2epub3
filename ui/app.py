# ui/app.py
import os
import sys
import tempfile
import threading
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
import mimetypes

# 添加项目根目录到 Python 路径
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st

from main import PDFToEPUBPipeline
from ui.progress import ProgressCallback


_STATIC_SERVER_PORT = 8899
_SERVER: Optional[ThreadingHTTPServer] = None
_SERVER_PORT: Optional[int] = None
_TEMP_DIR: Optional[tempfile.TemporaryDirectory] = None  # Keep temp dir alive for the session


class CustomHTTPRequestHandler(BaseHTTPRequestHandler):
    """Custom handler that serves files from a specific directory."""
    
    _serve_directory: Optional[str] = None
    
    def do_GET(self):
        """Handle GET request by serving files from the configured directory."""
        # Remove query string
        request_path = self.path.split('?')[0]
        
        # Remove leading slash
        if request_path.startswith('/'):
            request_path = request_path[1:]
        
        # Construct full file path
        if self._serve_directory:
            full_path = os.path.normpath(os.path.join(self._serve_directory, request_path))
        else:
            self.send_error(500, "Server not configured")
            return
        
        # Security check: ensure the path is within serve_directory
        real_serve_dir = os.path.realpath(self._serve_directory)
        real_full_path = os.path.realpath(full_path)
        if not real_full_path.startswith(real_serve_dir):
            self.send_error(403, "Forbidden")
            return
        
        # Check if path is a file or directory
        if os.path.isdir(full_path):
            # Try to serve index.html from the directory
            index_path = os.path.join(full_path, 'index.html')
            if os.path.isfile(index_path):
                full_path = index_path
            else:
                self.send_error(404, "Not Found")
                return
        
        # Try to serve the file
        if not os.path.isfile(full_path):
            self.send_error(404, "Not Found")
            return
        
        # Guess content type
        mime_type, _ = mimetypes.guess_type(full_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        
        try:
            with open(full_path, 'rb') as f:
                file_size = os.path.getsize(full_path)
                
                self.send_response(200)
                self.send_header('Content-Type', mime_type)
                self.send_header('Content-Length', str(file_size))
                self.send_header('Cache-Control', 'no-cache')
                # Add CORS headers to allow cross-origin requests
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type, Range')
                # Allow Range requests for seeking in EPUB
                self.send_header('Accept-Ranges', 'bytes')
                self.end_headers()
                
                self.wfile.write(f.read())
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {e}")
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Range')
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
    
    def do_HEAD(self):
        """Handle HEAD requests by sending headers without body."""
        # Remove query string
        request_path = self.path.split('?')[0]
        
        # Remove leading slash
        if request_path.startswith('/'):
            request_path = request_path[1:]
        
        # Construct full file path
        if self._serve_directory:
            full_path = os.path.normpath(os.path.join(self._serve_directory, request_path))
        else:
            self.send_error(500, "Server not configured")
            return
        
        # Security check: ensure the path is within serve_directory
        real_serve_dir = os.path.realpath(self._serve_directory)
        real_full_path = os.path.realpath(full_path)
        if not real_full_path.startswith(real_serve_dir):
            self.send_error(403, "Forbidden")
            return
        
        # Check if path is a file or directory
        if os.path.isdir(full_path):
            # Try to serve index.html from the directory
            index_path = os.path.join(full_path, 'index.html')
            if os.path.isfile(index_path):
                full_path = index_path
            else:
                self.send_error(404, "Not Found")
                return
        
        # Try to serve the file
        if not os.path.isfile(full_path):
            self.send_error(404, "Not Found")
            return
        
        # Guess content type
        mime_type, _ = mimetypes.guess_type(full_path)
        if mime_type is None:
            mime_type = 'application/octet-stream'
        
        try:
            file_size = os.path.getsize(full_path)
            
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(file_size))
            self.send_header('Cache-Control', 'no-cache')
            # Add CORS headers to allow cross-origin requests
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Range')
            # Allow Range requests for seeking in EPUB
            self.send_header('Accept-Ranges', 'bytes')
            self.end_headers()
            # Don't send body for HEAD request
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {e}")
    
    def log_message(self, format, *args):
        """Suppress default logging since we're doing custom logging."""
        pass


class StreamlitProgress(ProgressCallback):
    def __init__(
        self,
        html_path: Optional[Path] = None,
        preview_placeholder: Optional["st.delta_generator.DeltaGenerator"] = None,
    ) -> None:
        self._progress_bar = st.progress(0.0)
        self._status = st.empty()
        self._total = 0
        self._html_path = html_path
        self._preview_placeholder = preview_placeholder

    def _render_streaming_preview(self) -> None:
        """在转换过程中实时预览（HTML 文件可能尚未写入 footer，所以要补齐关闭标签）。"""
        if self._html_path is None or self._preview_placeholder is None:
            return
        if not self._html_path.exists():
            return

        try:
            content = self._html_path.read_text(encoding="utf-8")
        except Exception:
            return

        # HTML 可能还没写 footer：补齐以便浏览器/Streamlit 能渲染
        if "</html>" not in content:
            content += "\n    </div>\n  </div>\n</body>\n</html>\n"

        # 提取样式与 body 内容（避免把整份 <html> 嵌进 Streamlit）
        import re

        style_match = re.search(r"<style>(.*?)</style>", content, re.DOTALL | re.IGNORECASE)
        styles = style_match.group(1) if style_match else ""

        body_match = re.search(r"<body[^>]*>(.*?)</body>", content, re.DOTALL | re.IGNORECASE)
        body_content = body_match.group(1) if body_match else content

        final_html = f"<style>{styles}</style>{body_content}"
        self._preview_placeholder.markdown(final_html, unsafe_allow_html=True)
    
    def render_preview(self) -> None:
        """公开方法：立即更新预览（供外部调用）"""
        self._render_streaming_preview()

    def on_start(self, total_pages: int) -> None:
        self._total = total_pages
        self._status.info(f"开始处理 PDF，共 {total_pages} 页")
        if self._preview_placeholder is not None:
            self._preview_placeholder.info("实时预览将在第 1 页生成后显示…")

    def on_page_processed(self, page_number: int) -> None:
        self._progress_bar.progress(page_number / self._total)
        self._status.info(
            f"正在处理第 {page_number} / {self._total} 页"
        )
        # 每页处理完就刷新一次预览
        self._render_streaming_preview()

    def on_finish(self, output_path: str) -> None:
        self._progress_bar.progress(1.0)
        self._status.success("HTML 转换完成")
    
    def update(self, message: str) -> None:
        """更新进度消息"""
        self._status.info(message)


def _start_static_server(static_root: Path) -> Optional[int]:
    global _SERVER
    global _SERVER_PORT

    # Always create a fresh server for each preview request (since temp dirs change per Streamlit run)
    # First, shut down the old server if it exists
    if _SERVER is not None:
        try:
            _SERVER.shutdown()
            _SERVER.server_close()
        except Exception as e:
            print(f"[SERVER] Error shutting down old server: {e}", flush=True)
        _SERVER = None
        _SERVER_PORT = None
        # Give the port time to be released
        import time
        time.sleep(0.5)

    # Set the serve directory on the handler class
    static_root_str = str(static_root)
    CustomHTTPRequestHandler._serve_directory = static_root_str
    
    # List contents for debugging
    if os.path.exists(static_root_str):
        print(f"[SERVER] Serving from {static_root_str}", flush=True)

    # Bind to 0.0.0.0 so that the server is reachable from other interfaces if needed
    server_address = ("0.0.0.0", _STATIC_SERVER_PORT)

    try:
        httpd = ThreadingHTTPServer(server_address, CustomHTTPRequestHandler)
        port = server_address[1]
    except OSError as exc:
        # If the desired port is already in use, probe the existing server to see
        # if it already serves our preview. If it does, reuse that port. Otherwise
        # bind to an ephemeral port assigned by the OS.
        if getattr(exc, 'errno', None) in (48,):
            # probe existing server for /preview/index.html
            import urllib.request
            import urllib.error

            probe_url = f"http://localhost:{server_address[1]}/preview/index.html"
            try:
                with urllib.request.urlopen(probe_url, timeout=1) as resp:
                    if resp.status == 200:
                        # Existing server already serves preview; reuse desired port
                        _SERVER_PORT = server_address[1]
                        return _SERVER_PORT
            except Exception:
                # Existing process on port is not serving our preview; fall back
                # to starting on an ephemeral port
                pass

            # Start on an ephemeral port
            httpd = ThreadingHTTPServer(("0.0.0.0", 0), CustomHTTPRequestHandler)
            port = httpd.server_address[1]
        else:
            raise

    thread = threading.Thread(
        target=httpd.serve_forever,
        daemon=True,
    )
    thread.start()

    _SERVER = httpd
    _SERVER_PORT = port

    return _SERVER_PORT


def render_html_preview(html_path: Path, work_dir: Path) -> None:
    """直接显示HTML预览 - 不使用iframe，直接嵌入到页面中"""
    try:
        # 直接读取HTML内容
        html_content = html_path.read_text(encoding='utf-8')
        
        st.subheader("HTML 在线预览")
        
        # 提取 body 标签内的内容，直接显示在 Streamlit 页面中
        import re
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
        style_match = re.search(r'<style[^>]*>(.*?)</style>', html_content, re.DOTALL | re.IGNORECASE)
        
        if body_match and style_match:
            # 提取样式和内容
            style_content = style_match.group(1)
            body_content = body_match.group(1)
            
            # 将样式和内容组合，直接嵌入到页面中
            combined_html = f"""
            <style>
            {style_content}
            </style>
            {body_content}
            """
            
            # 使用 st.markdown 直接显示，不使用 iframe
            st.markdown(combined_html, unsafe_allow_html=True)
        else:
            # 如果无法提取，直接显示整个HTML（去掉html和body标签）
            # 移除 DOCTYPE, html, head, body 标签，只保留内容
            content = re.sub(r'<!DOCTYPE[^>]*>', '', html_content, flags=re.IGNORECASE)
            content = re.sub(r'<html[^>]*>', '', content, flags=re.IGNORECASE)
            content = re.sub(r'</html>', '', content, flags=re.IGNORECASE)
            content = re.sub(r'<head[^>]*>.*?</head>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<body[^>]*>', '', content, flags=re.IGNORECASE)
            content = re.sub(r'</body>', '', content, flags=re.IGNORECASE)
            
            st.markdown(content, unsafe_allow_html=True)
            
    except Exception as e:
        st.error(f"无法显示HTML预览: {e}")
        import traceback
        st.code(traceback.format_exc())


def render_epub_preview(epub_path: Path, work_dir: Path) -> None:
    static_root = work_dir / "static"
    preview_dir = static_root / "preview"

    preview_dir.mkdir(parents=True, exist_ok=True)

    viewer_src = Path(__file__).parent / "epub_viewer"

    # Copy epub_viewer → preview/
    if not viewer_src.exists():
        st.error(f"viewer assets not found at {viewer_src}")
        return

    # 快速复制 viewer 资源（只在文件不存在时复制）
    for p in viewer_src.rglob("*"):
        if p.name.startswith("."):
            continue

        target = preview_dir / p.relative_to(viewer_src)

        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            # 只在目标文件不存在或源文件更新时才复制
            if not target.exists() or target.stat().st_mtime < p.stat().st_mtime:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(p.read_bytes())

    # 快速复制 EPUB 文件
    try:
        epub_bytes = epub_path.read_bytes()
        epub_target = preview_dir / "output.epub"
        # 只在文件不存在或源文件更新时才复制
        if not epub_target.exists() or epub_target.stat().st_mtime < epub_path.stat().st_mtime:
            epub_target.write_bytes(epub_bytes)
    except FileNotFoundError:
        st.error("转换后 EPUB 文件未找到")
        return

    port = _start_static_server(static_root)

    if port is None:
        st.error("无法启动静态预览服务器")
        return

    # Use localhost in the browser URL; server listens on all interfaces but browsers use localhost
    # Pass the epub file path as a query parameter since index.html expects it
    viewer_url = f"http://localhost:{port}/preview/index.html?epub=/preview/output.epub"
    print(f"[PREVIEW] URL: {viewer_url}", flush=True)

    st.subheader("EPUB3 在线预览")

    st.components.v1.iframe(
        viewer_url,
        height=650,
        scrolling=True,
    )


def main() -> None:
    global _TEMP_DIR
    
    st.set_page_config(
        page_title="PDF → HTML",
        layout="centered",
    )

    st.title("PDF 转 HTML（含数学公式）")

    uploaded_file = st.file_uploader(
        "上传 PDF 文件",
        type=["pdf"],
        accept_multiple_files=False,
    )

    if uploaded_file is None:
        return

    # Create a persistent temp directory for this session
    if _TEMP_DIR is None:
        _TEMP_DIR = tempfile.TemporaryDirectory()
    
    tmpdir = _TEMP_DIR.name
    work_dir = Path(tmpdir)

    pdf_path = work_dir / uploaded_file.name
    html_path = work_dir / "output.html"

    pdf_path.write_bytes(uploaded_file.read())

    # OCR选项
    st.sidebar.header("OCR 选项")
    
    # 检查 poppler 是否可用
    poppler_available = False
    try:
        result = subprocess.run(
            ['pdftoppm', '-v'],
            capture_output=True,
            timeout=2
        )
        poppler_available = True
    except (FileNotFoundError, subprocess.TimeoutExpired, ImportError):
        poppler_available = False
    
    if not poppler_available:
        st.sidebar.warning(
            "⚠️ OCR 功能需要安装 poppler\n\n"
            "**macOS:**\n"
            "```bash\nbrew install poppler\n```\n\n"
            "**Linux:**\n"
            "```bash\nsudo apt-get install poppler-utils\n```\n\n"
            "**Windows:**\n"
            "下载 poppler 并添加到 PATH"
        )
    
    use_ocr = st.sidebar.checkbox(
        "启用 OCR（用于扫描版PDF）",
        value=False,
        disabled=not poppler_available,
        help="如果PDF是扫描版或文本提取效果差，可以启用OCR" if poppler_available else "需要先安装 poppler"
    )
    
    if use_ocr:
        ocr_backend = st.sidebar.selectbox(
            "OCR 引擎",
            options=["paddleocr", "easyocr", "tesseract"],
            index=0,
            help="PaddleOCR: 推荐，支持中文和数学公式\nEasyOCR: 多语言支持\nTesseract: 传统OCR引擎"
        )
    else:
        ocr_backend = "paddleocr"

    if st.button("开始转换"):
        st.subheader("HTML 在线预览（实时）")
        preview_placeholder = st.empty()

        progress = StreamlitProgress(
            html_path=html_path,
            preview_placeholder=preview_placeholder,
        )
        
        # 如果启用 OCR，显示初始化提示
        if use_ocr:
            st.info("ℹ️ **提示**: PaddleOCR 首次初始化可能需要几分钟时间，请耐心等待。模型加载完成后会显示进度。")

        try:
            pipeline = PDFToEPUBPipeline(
                pdf_path=pdf_path,
                output_path=html_path,
                progress_callback=progress,
                output_format="html",  # 使用HTML格式
                use_ocr=use_ocr,
                ocr_backend=ocr_backend,
            )
            pipeline.run()
        except RuntimeError as e:
            error_msg = str(e)
            if "poppler" in error_msg.lower():
                st.error(f"❌ {error_msg}")
                st.info(
                    "**安装 poppler 后，请重启 Streamlit 应用。**\n\n"
                    "重启命令：停止当前应用（Ctrl+C），然后重新运行：\n"
                    "```bash\nstreamlit run ui/app.py\n```"
                )
            else:
                st.error(f"转换失败: {error_msg}")
            return
        except Exception as e:
            st.error(f"转换失败: {e}")
            import traceback
            st.code(traceback.format_exc())
            return

        st.success("转换完成")

        # 下载按钮
        st.download_button(
            label="下载 HTML",
            data=html_path.read_bytes(),
            file_name="output.html",
            mime="text/html",
        )

        # 直接显示HTML预览
        render_html_preview(html_path, work_dir)


if __name__ == "__main__":
    main()