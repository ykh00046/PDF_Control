from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem
from PySide6.QtGui import QPixmap, QImage, QPainter, QBrush, QColor, QPen
from PySide6.QtCore import Qt, QPointF, Signal, QRectF, QTimer

import fitz # PyMuPDF
from typing import Optional, Dict, List
from pathlib import Path
import subprocess
import sys
import uuid
import hashlib
import json
from app.model import DocumentSession
from app.logger import get_logger, log_render_performance
from app.path_helper import get_base_path, get_temp_dir, is_frozen

class PDFViewer(QGraphicsView):
    selection_made = Signal(fitz.Rect)
    page_changed = Signal(int)
    render_started = Signal()
    render_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        
        self.session: Optional[DocumentSession] = None
        self.current_page_index = -1
        self.current_pixmap_item = None
        self.zoom_level = 1.0

        self.start_point: Optional[QPointF] = None
        self.end_point: Optional[QPointF] = None
        self.selection_rect_item: Optional[QGraphicsRectItem] = None
        
        # Process-based rendering & cache
        self.image_cache = {} # Key: hash string, Value: QImage
        self.cache_size = 20 # Max number of cached images
        self._active_render_process: Optional[subprocess.Popen] = None
        self._active_request_key: Optional[str] = None
        self._active_render_context: Optional[Dict] = None
        self._render_poll_timer = QTimer(self)
        self._render_poll_timer.setInterval(50)
        self._render_poll_timer.timeout.connect(self._poll_render_process)

    def set_document_session(self, session: DocumentSession):
        self.image_cache.clear() # Clear cache on new document
        try:
            self._cancel_active_render()
            self.session = session
            if self.session and self.session.doc.page_count > 0:
                self.current_page_index = 0
                self.page_changed.emit(self.current_page_index)
                self.request_render()
            else:
                self.session = None
                self.current_page_index = -1
                self.scene.clear()
                self.page_changed.emit(self.current_page_index)
        except Exception as e:
            get_logger().error(f"Error setting document session: {e}")

    def _compute_cache_key(self, page_index, zoom, ops_data):
        # Serialize ops data to string for hash
        ops_str = json.dumps(ops_data, sort_keys=True)
        key_str = f"{self.session.file_path}_{page_index}_{zoom:.2f}_{ops_str}"
        return hashlib.md5(key_str.encode('utf-8')).hexdigest()

    def _current_ops_data(self, page_index: Optional[int] = None) -> List[Dict]:
        if not self.session:
            return []

        target_page = self.current_page_index if page_index is None else page_index
        operations = [op for op in self.session.history if op.page_index == target_page]
        return [op.to_dict() for op in operations]

    def _current_cache_key(self) -> Optional[str]:
        if not self.session or self.current_page_index < 0:
            return None
        return self._compute_cache_key(
            self.current_page_index,
            self.zoom_level,
            self._current_ops_data(),
        )

    def _build_render_paths(self):
        render_dir = get_temp_dir() / "renders"
        render_dir.mkdir(parents=True, exist_ok=True)
        render_id = uuid.uuid4().hex
        job_path = render_dir / f"{render_id}.job.json"
        response_path = render_dir / f"{render_id}.response.json"
        image_path = render_dir / f"{render_id}.png"
        return job_path, response_path, image_path

    def _cleanup_render_files(self, *paths: Path):
        for path in paths:
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                continue

    def _cancel_active_render(self):
        if self._active_render_process is None:
            return

        self._render_poll_timer.stop()
        if self._active_render_process.poll() is None:
            self._active_render_process.terminate()
            try:
                self._active_render_process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self._active_render_process.kill()
                self._active_render_process.wait(timeout=1)

        if self._active_render_context is not None:
            self._cleanup_render_files(
                self._active_render_context["job_path"],
                self._active_render_context["response_path"],
                self._active_render_context["image_path"],
            )

        self._active_render_process = None
        self._active_request_key = None
        self._active_render_context = None

    def _build_render_command(self, job_path: Path):
        if is_frozen():
            return sys.executable, ["--render-worker", str(job_path)]
        return sys.executable, [str(get_base_path() / "main.py"), "--render-worker", str(job_path)]

    def _start_render_process(self, page_index: int, zoom: float, ops_data: List[Dict], request_key: str):
        job_path, response_path, image_path = self._build_render_paths()
        payload = {
            "file_path": self.session.file_path,
            "page_index": page_index,
            "zoom_level": zoom,
            "operations_data": ops_data,
            "output_path": str(image_path),
            "response_path": str(response_path),
        }
        # An encrypted source can only be re-opened by the worker with its
        # password. The password itself is sent over the stdin pipe (never
        # written to the job file, so it cannot linger on disk after a
        # crash); the job file only carries the announcement flag.
        password = self.session.render_password()
        if password is not None:
            payload["password_stdin"] = True

        with open(job_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)

        self._cancel_active_render()
        self._active_request_key = request_key

        program, arguments = self._build_render_command(job_path)
        try:
            process = subprocess.Popen(
                [program, *arguments],
                cwd=str(get_base_path()),
                stdin=subprocess.PIPE if password is not None else subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                # UTF-8 pinned for the stdin password line (worker side
                # reconfigures to match). The worker's stderr may still be
                # locale-encoded, so don't hard-fail on a mismatch there.
                encoding="utf-8",
                errors="replace",
            )
            if password is not None and process.stdin is not None:
                # One-line protocol matched by render_worker. A write failure
                # means the worker died instantly; the response poller will
                # surface that error, so just log here.
                try:
                    process.stdin.write(password + "\n")
                except OSError as exc:
                    get_logger().debug(f"Render stdin write failed: {exc}")
                finally:
                    try:
                        process.stdin.close()
                    except OSError:
                        pass
        except OSError as exc:
            self._cleanup_render_files(job_path, response_path, image_path)
            self._active_render_process = None
            self._active_request_key = None
            self._active_render_context = None
            self._on_render_error((request_key, str(exc)))
            return

        self._active_render_process = process
        self._active_render_context = {
            "request_key": request_key,
            "job_path": job_path,
            "response_path": response_path,
            "image_path": image_path,
        }
        self._render_poll_timer.start()

    def _poll_render_process(self):
        if self._active_render_process is None or self._active_render_context is None:
            self._render_poll_timer.stop()
            return

        if self._active_render_process.poll() is None:
            return

        self._render_poll_timer.stop()
        process = self._active_render_process
        context = self._active_render_context
        self._active_render_process = None
        self._active_render_context = None
        self._active_request_key = None

        stderr_output = ""
        if process.stderr is not None:
            stderr_output = process.stderr.read().strip()

        self._on_render_process_finished(process.returncode, stderr_output, context)

    def _on_render_process_finished(self, return_code, stderr_output, context):
        request_key = context["request_key"]
        job_path = context["job_path"]
        response_path = context["response_path"]
        image_path = context["image_path"]
        if stderr_output:
            get_logger().debug(f"Render worker stderr [{request_key}]: {stderr_output}")

        try:
            if request_key != self._current_cache_key():
                get_logger().debug(f"Ignoring stale render process result for key={request_key}")
                return

            if return_code != 0:
                error_message = f"Render worker exited with code {return_code}"
                if response_path.exists():
                    try:
                        with open(response_path, "r", encoding="utf-8") as handle:
                            response = json.load(handle)
                        error_message = response.get("error", error_message)
                    except (json.JSONDecodeError, ValueError, OSError):
                        pass
                elif stderr_output:
                    error_message = stderr_output
                self._on_render_error((request_key, error_message))
                return

            with open(response_path, "r", encoding="utf-8") as handle:
                response = json.load(handle)

            if not response.get("success"):
                self._on_render_error((request_key, response.get("error", "Render worker failed")))
                return

            image = QImage(str(image_path))
            if image.isNull():
                self._on_render_error((request_key, "Render worker produced an invalid image"))
                return

            # Push preview warnings (may be empty) into the session cache so
            # status bar and history panel can reflect fit issues.
            if self.session is not None:
                self.session.update_warnings(
                    response["page_index"],
                    response.get("warnings", []) or [],
                )

            self._on_render_finished(
                (
                    response["page_index"],
                    image,
                    response["duration_ms"],
                    response["zoom_level"],
                    request_key,
                )
            )
        finally:
            self._cleanup_render_files(job_path, response_path, image_path)

    def request_render(self):
        if not self.session or self.current_page_index < 0:
            self._cancel_active_render()
            self.scene.clear()
            return

        # 1. Prepare operations data
        ops_data = self._current_ops_data()
        
        # 2. Check Cache
        cache_key = self._compute_cache_key(self.current_page_index, self.zoom_level, ops_data)
        if cache_key in self.image_cache:
            self._cancel_active_render()
            get_logger().debug(f"Cache hit for page {self.current_page_index}")
            self._update_scene(self.image_cache[cache_key])
            return

        # 3. Start render worker process
        self.render_started.emit()
        self._start_render_process(
            self.current_page_index,
            self.zoom_level,
            ops_data,
            cache_key,
        )

    def _on_render_finished(self, result):
        page_index, img, duration, zoom, request_key = result
        
        if not self.session:
            self.render_finished.emit()
            return

        current_ops = [op for op in self.session.history if op.page_index == self.current_page_index]
        current_ops_data = [op.to_dict() for op in current_ops]
        current_cache_key = self._compute_cache_key(
            self.current_page_index,
            self.zoom_level,
            current_ops_data,
        )

        # Only update if it matches the current render state.
        if page_index != self.current_page_index or request_key != current_cache_key:
            get_logger().debug(
                f"Ignoring stale render result: page={page_index}, zoom={zoom:.2f}, key={request_key}"
            )
            self.render_finished.emit()
            return

        # Cache result
        # LRU eviction
        if len(self.image_cache) >= self.cache_size:
            # Remove arbitrary item (first key) - simple FIFO/random actually
            self.image_cache.pop(next(iter(self.image_cache)))
            
        self.image_cache[request_key] = img
             
        self._update_scene(img)
        log_render_performance(page_index, duration, zoom)
        self.render_finished.emit()

    def _on_render_error(self, error):
        request_key, error_msg = error
        if self.session and self.current_page_index >= 0:
            current_ops = [op for op in self.session.history if op.page_index == self.current_page_index]
            current_ops_data = [op.to_dict() for op in current_ops]
            current_cache_key = self._compute_cache_key(
                self.current_page_index,
                self.zoom_level,
                current_ops_data,
            )
            if request_key != current_cache_key:
                get_logger().debug(f"Ignoring stale render error for key={request_key}: {error_msg}")
                return
        get_logger().error(f"Async render error: {error_msg}")
        # Keep last successful image; just log and notify
        self.render_finished.emit()

    def _update_scene(self, img: QImage):
        self.scene.clear()
        self.selection_rect_item = None
        self.current_pixmap_item = QGraphicsPixmapItem(QPixmap.fromImage(img))
        self.scene.addItem(self.current_pixmap_item)
        self.scene.setSceneRect(self.current_pixmap_item.boundingRect())
        
        # Only fitInView if scene was empty or size changed significantly?
        # Or just rely on user scroll?
        # Maintain legacy behavior: only on first load? 
        # For now, call fitInView only if zoom is 1.0 (initial) or fit mode?
        # Actually, request_render is called by zoom methods too.
        # We shouldn't force fitInView on every render if user zoomed.
        # But original code did `fitInView` in render_current_page.
        # Let's keep it simple: update scene. User keeps scroll/zoom.
        # If we want "fit to width", we change zoom level, which triggers render.
        
        self.viewport().update()
        self.update()

    # --- API Compatibility ---
    def render_current_page(self):
        self.request_render()

    def render_current_page_with_operations(self):
        self.request_render()

    def set_zoom(self, level):
        new_zoom = max(0.1, min(level, 5.0))
        if abs(new_zoom - self.zoom_level) < 0.001:
            return
        self.zoom_level = new_zoom
        self.request_render()

    def zoom_in(self):
        self.set_zoom(self.zoom_level * 1.2)

    def zoom_out(self):
        self.set_zoom(self.zoom_level / 1.2)

    def fit_to_width(self):
        if not self.session or self.current_page_index < 0: return
        view_width = self.viewport().width()
        if view_width <= 0: return

        if self.current_pixmap_item is not None:
            rendered_width = self.current_pixmap_item.pixmap().width()
            if rendered_width > 0:
                target_zoom = self.zoom_level * view_width / rendered_width
                self.set_zoom(target_zoom)
                return

        page = self.session.doc[self.current_page_index]
        page_width_pt = page.rect.width
        pixels_per_point = 150 / 72
        target_zoom = view_width / (page_width_pt * pixels_per_point)
        self.set_zoom(target_zoom)

    def next_page(self):
        if self.session and self.current_page_index < self.session.doc.page_count - 1:
            self.current_page_index += 1
            self.page_changed.emit(self.current_page_index)
            self.request_render()

    def prev_page(self):
        if self.session and self.current_page_index > 0:
            self.current_page_index -= 1
            self.page_changed.emit(self.current_page_index)
            self.request_render()

    # --- Mouse Events (Keep existing) ---
    def wheelEvent(self, event):
        if self.session and event.modifiers() == Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self.set_zoom(self.zoom_level * 1.1)
            else:
                self.set_zoom(self.zoom_level / 1.1)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event):
        if self.current_pixmap_item and event.button() == Qt.LeftButton:
            self.clear_selection()
            self.start_point = self.mapToScene(event.pos())
            self.end_point = self.start_point
            self.setDragMode(QGraphicsView.NoDrag)
            self._update_selection_rect()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.start_point:
            self.end_point = self.mapToScene(event.pos())
            self._update_selection_rect()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.start_point and event.button() == Qt.LeftButton:
            self.end_point = self.mapToScene(event.pos())
            self.start_point = None
            if self.selection_rect_item:
                selected_qrect = self.selection_rect_item.rect()
                if selected_qrect.width() > 5 and selected_qrect.height() > 5:
                    pdf_rect = self._qrectf_to_fitz_rect(selected_qrect)
                    self.selection_made.emit(pdf_rect)
                else:
                    self.clear_selection()
            self.setDragMode(QGraphicsView.ScrollHandDrag)
        else:
            super().mouseReleaseEvent(event)

    def clear_selection(self):
        try:
            if self.selection_rect_item:
                if self.selection_rect_item.scene() == self.scene:
                    self.scene.removeItem(self.selection_rect_item)
                self.selection_rect_item = None
        except Exception as e:
            get_logger().debug(f"Error clearing selection rect: {e}")
            self.selection_rect_item = None

    def _update_selection_rect(self):
        if self.start_point and self.end_point:
            rect = QRectF(self.start_point, self.end_point).normalized()
            if not self.selection_rect_item:
                self.selection_rect_item = QGraphicsRectItem(rect)
                self.selection_rect_item.setPen(QPen(QColor(Qt.blue), 2))
                self.selection_rect_item.setBrush(QBrush(QColor(0, 0, 255, 50)))
                self.scene.addItem(self.selection_rect_item)
            else:
                self.selection_rect_item.setRect(rect)

    def _qrectf_to_fitz_rect(self, qrectf):
        try:
            if not self.current_pixmap_item or not self.session: return fitz.Rect(0,0,0,0)
            top_left_item = self.current_pixmap_item.mapFromScene(qrectf.topLeft())
            bottom_right_item = self.current_pixmap_item.mapFromScene(qrectf.bottomRight())
            scale = self.zoom_level * 150 / 72
            pdf_rect = fitz.Rect(top_left_item.x()/scale, top_left_item.y()/scale, bottom_right_item.x()/scale, bottom_right_item.y()/scale)
            return pdf_rect & self.session.doc[self.current_page_index].rect
        except Exception as e:
            get_logger().debug(f"Error converting QRectF to fitz.Rect: {e}")
            return fitz.Rect(0,0,0,0)

    def closeEvent(self, event):
        self._cancel_active_render()
        super().closeEvent(event)
