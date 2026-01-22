# ui/app.py
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
import mimetypes

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
    def __init__(self) -> None:
        self._progress_bar = st.progress(0.0)
        self._status = st.empty()
        self._total = 0

    def on_start(self, total_pages: int) -> None:
        self._total = total_pages
        self._status.info(f"开始处理 PDF，共 {total_pages} 页")

    def on_page_processed(self, page_number: int) -> None:
        self._progress_bar.progress(page_number / self._total)
        self._status.info(
            f"正在处理第 {page_number} / {self._total} 页"
        )

    def on_finish(self, output_path: str) -> None:
        self._progress_bar.progress(1.0)
        self._status.success("EPUB3 转换完成")


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


def render_epub_preview(epub_path: Path, work_dir: Path) -> None:
    static_root = work_dir / "static"
    preview_dir = static_root / "preview"

    preview_dir.mkdir(parents=True, exist_ok=True)

    viewer_src = Path(__file__).parent / "epub_viewer"

    # Copy epub_viewer → preview/
    if not viewer_src.exists():
        st.error(f"viewer assets not found at {viewer_src}")
        return

    print(f"[COPY] Starting to copy viewer assets from {viewer_src}", flush=True)
    for p in viewer_src.rglob("*"):
        # Skip hidden files
        if p.name.startswith("."):
            continue

        target = preview_dir / p.relative_to(viewer_src)

        if p.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(p.read_bytes())

    # 放 epub 到同一目录
    try:
        print(f"[COPY] Writing EPUB to {preview_dir / 'output.epub'}", flush=True)
        epub_bytes = epub_path.read_bytes()
        print(f"[COPY] EPUB file size: {len(epub_bytes)} bytes", flush=True)
        (preview_dir / "output.epub").write_bytes(epub_bytes)
        print(f"[COPY] EPUB written, exists now: {(preview_dir / 'output.epub').exists()}", flush=True)
    except FileNotFoundError:
        st.error("转换后 EPUB 文件未找到")
        return

    # Verify all files exist before starting server
    print(f"[VERIFY] Checking files exist in {preview_dir}:", flush=True)
    for f in preview_dir.rglob("*"):
        if f.is_file():
            print(f"  ✓ {f.relative_to(preview_dir)}", flush=True)

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
        page_title="PDF → EPUB3",
        layout="centered",
    )

    st.title("PDF 转 EPUB3（含数学公式）")

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
    epub_path = work_dir / "output.epub"

    pdf_path.write_bytes(uploaded_file.read())

    if st.button("开始转换"):
        progress = StreamlitProgress()

        pipeline = PDFToEPUBPipeline(
            pdf_path=pdf_path,
            output_path=epub_path,
            progress_callback=progress,
        )
        pipeline.run()

        st.success("转换完成")

        st.download_button(
            label="下载 EPUB3",
            data=epub_path.read_bytes(),
            file_name="output.epub",
            mime="application/epub+zip",
        )

        render_epub_preview(epub_path, work_dir)


if __name__ == "__main__":
    main()