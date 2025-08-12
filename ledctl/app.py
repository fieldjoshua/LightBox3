from __future__ import annotations
import logging
import os
import signal
import time
import secrets
import mimetypes
import io
from typing import Any, Dict, Optional, List
from flask import (
    Flask,
    jsonify,
    render_template,
    g,
    request,
    send_from_directory,
    abort,
)
from werkzeug.utils import secure_filename
from flask_socketio import SocketIO
import yaml

# Local imports
from core.drivers import OutputDevice
from core.drivers.preview import NullPreviewDriver
from core.renderer import Renderer


socketio: Optional[SocketIO] = None


def create_app() -> Flask:
    """
    Create and configure the Flask application.

    - Loads YAML config from config/device.default.yml or env override
    - Initializes logging
    - Initializes Socket.IO
    - Prepares output device (PREVIEW by default for dev)
    """
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
    )

    _init_logging()
    app.config["_server_started_at_s"] = time.time()
    app.config["metrics"] = {
        "requests_total": 0,
        "last_request_ms": 0.0,
    }
    app.config["upload_dir"] = os.path.join(
        os.path.dirname(__file__),
        "uploads",
    )
    _ensure_dir(app.config["upload_dir"])
    config_path = os.environ.get(
        "LEDCTL_CONFIG",
        os.path.join(
            os.path.dirname(__file__),
            "config",
            "device.default.yml",
        ),
    )

    try:
        cfg = _load_yaml_config(config_path)
    except Exception as exc:  # broad but logged; boot in safe defaults
        logging.exception("Failed to load config: %s", exc)
        cfg = _default_config()
    app.config["config"] = cfg

    # Realtime communications
    global socketio
    socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

    # Output device selection; start with Preview
    try:
        device = _create_output_device(cfg)
        # Attempt to open the device (no-op for preview)
        with _suppress_ex("device.open"):
            device.open()
        app.config["output_device"] = device
    except Exception as exc:
        logging.exception(
            "Failed to initialize output device: %s",
            exc,
        )
        # Fallback to preview driver to avoid boot failure
        app.config["output_device"] = NullPreviewDriver(
            device_name="PREVIEW_FALLBACK"
        )

    # Renderer service
    try:
        renderer = Renderer(app.config["output_device"], cfg)
        app.config["renderer"] = renderer
    except Exception:
        logging.exception("Failed to initialize renderer")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.get("/health")
    def health() -> Any:
        return jsonify({"status": "ok"})

    @app.get("/metrics")
    def metrics() -> Any:
        try:
            uptime_s = time.time() - float(app.config["_server_started_at_s"])
        except Exception:
            uptime_s = 0.0
        data = dict(app.config.get("metrics", {}))
        data["uptime_s"] = round(float(uptime_s), 3)
        return jsonify(data)

    # Playback controls
    @app.post("/api/playback/start")
    def api_playback_start() -> Any:
        try:
            payload = request.get_json(silent=True) or {}
            name = str(
                payload.get("file") or payload.get("name") or ""
            ).strip()
            if not name:
                return jsonify({"error": "missing file"}), 400
            upload_dir = app.config.get("upload_dir")
            if not upload_dir:
                return jsonify({"error": "upload_dir_missing"}), 500
            # Only allow files inside uploads
            path = os.path.abspath(os.path.join(upload_dir, name))
            if not path.startswith(os.path.abspath(upload_dir) + os.sep):
                return jsonify({"error": "invalid path"}), 400
            renderer: Renderer = app.config.get(
                "renderer"
            )  # type: ignore[assignment]
            if not renderer:
                return jsonify({"error": "renderer_unavailable"}), 500
            renderer.start(path)
            return jsonify({"ok": True})
        except FileNotFoundError:
            return jsonify({"error": "not_found"}), 404
        except Exception as exc:
            logging.exception("playback start failed: %s", exc)
            return jsonify({"error": "start_failed"}), 500

    @app.post("/api/playback/stop")
    def api_playback_stop() -> Any:
        try:
            renderer: Renderer = app.config.get(
                "renderer"
            )  # type: ignore[assignment]
            if not renderer:
                return jsonify({"error": "renderer_unavailable"}), 500
            renderer.stop()
            return jsonify({"ok": True})
        except Exception as exc:
            logging.exception("playback stop failed: %s", exc)
            return jsonify({"error": "stop_failed"}), 500

    @app.get("/api/playback/status")
    def api_playback_status() -> Any:
        try:
            renderer: Renderer = app.config.get(
                "renderer"
            )  # type: ignore[assignment]
            if not renderer:
                return jsonify({"error": "renderer_unavailable"}), 500
            return jsonify(renderer.get_status())
        except Exception as exc:
            logging.exception("playback status failed: %s", exc)
            return jsonify({"error": "status_failed"}), 500

    @app.get("/api/preview.png")
    def api_preview() -> Any:
        try:
            renderer: Renderer = app.config.get(
                "renderer"
            )  # type: ignore[assignment]
            img = None
            if renderer:
                img = renderer.get_latest_image()
            # Fallback: if preview device stores latest
            if img is None:
                device: OutputDevice = app.config.get(
                    "output_device"
                )  # type: ignore[assignment]
                if isinstance(device, NullPreviewDriver):
                    img = device.get_latest_image()
            if img is None:
                return abort(404)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return app.response_class(buf.getvalue(), mimetype="image/png")
        except Exception as exc:
            logging.exception("preview failed: %s", exc)
            return jsonify({"error": "preview_failed"}), 500

    @app.before_request
    def _before_request_hook() -> None:  # type: ignore[override]
        g._req_start = time.perf_counter()

    @app.after_request
    def _after_request_hook(response):  # type: ignore[override]
        try:
            start = getattr(g, "_req_start", None)
            if start is not None:
                elapsed_ms = (time.perf_counter() - float(start)) * 1000.0
                m = app.config.get("metrics", {})
                m["requests_total"] = int(m.get("requests_total", 0)) + 1
                m["last_request_ms"] = round(float(elapsed_ms), 3)
                app.config["metrics"] = m
        except Exception:
            logging.exception("metrics update failure")
        return response

    # Static file serving for uploaded assets (dev only)
    @app.get("/uploads/<path:filename>")
    def get_upload(filename: str):
        try:
            return send_from_directory(app.config["upload_dir"], filename)
        except Exception:
            abort(404)

    # REST: list uploads
    @app.get("/api/files")
    def api_list_files() -> Any:
        try:
            files = _list_uploads(app.config["upload_dir"])
            return jsonify({"files": files})
        except Exception as exc:
            logging.exception("list files failed: %s", exc)
            return jsonify({"error": "list_failed"}), 500

    # REST: upload asset
    @app.post("/api/upload")
    def api_upload_file() -> Any:
        if "file" not in request.files:
            return jsonify({"error": "missing file"}), 400
        up = request.files["file"]
        if up.filename is None or up.filename.strip() == "":
            return jsonify({"error": "empty filename"}), 400
        filename = secure_filename(up.filename)
        if not _allowed_upload(filename, up.mimetype or ""):
            return jsonify({"error": "unsupported type"}), 400
        # Randomize to avoid collisions
        base, ext = os.path.splitext(filename)
        rand = secrets.token_hex(4)
        final_name = f"{base}-{rand}{ext.lower()}"
        dest_path = os.path.join(app.config["upload_dir"], final_name)
        try:
            up.save(dest_path)
            meta = _probe_asset(dest_path)
            return jsonify({"ok": True, "file": meta}), 201
        except Exception as exc:
            logging.exception("upload failed: %s", exc)
            return jsonify({"error": "save_failed"}), 500

    # Socket.IO: set params
    @socketio.on("set_params")
    def ws_set_params(payload: Dict[str, Any]) -> None:  # type: ignore
        try:
            render = _validate_render_params(payload)
            # Persist to app config
            cfg: Dict[str, Any] = app.config.get("config", _default_config())
            cfg.setdefault("render", {}).update(render)
            app.config["config"] = cfg
            # Apply to renderer
            renderer: Renderer = app.config.get(
                "renderer"
            )  # type: ignore[assignment]
            if renderer:
                renderer.set_render_params(render)
        except Exception as exc:
            logging.exception("set_params error: %s", exc)

    @app.post("/api/brightness")
    def api_brightness() -> Any:
        try:
            payload = request.get_json(silent=True) or {}
            value = float(payload.get("value01", 1.0))
            value = max(0.0, min(1.0, value))
            device: OutputDevice = app.config.get(
                "output_device"
            )  # type: ignore[assignment]
            if not device:
                return jsonify({"error": "device_unavailable"}), 500
            with _suppress_ex("device.set_brightness"):
                device.set_brightness(value)
            return jsonify({"ok": True})
        except Exception as exc:
            logging.exception("brightness failed: %s", exc)
            return jsonify({"error": "brightness_failed"}), 500

    # Graceful shutdown hooks
    _install_signal_handlers(app)

    return app


def _init_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def _ensure_dir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        logging.exception("mkdir failed for %s", path)


def _load_yaml_config(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Config not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")
    return data


def _allowed_upload(filename: str, mime: str) -> bool:
    allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".mp4"}
    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_ext:
        return False
    guessed, _ = mimetypes.guess_type(filename)
    return (guessed or "").startswith(("image/", "video/")) or mime.startswith(
        ("image/", "video/")
    )


def _list_uploads(upload_dir: str) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for name in sorted(os.listdir(upload_dir)):
        path = os.path.join(upload_dir, name)
        if not os.path.isfile(path):
            continue
        meta = _probe_asset(path)
        results.append(meta)
    return results


def _probe_asset(path: str) -> Dict[str, Any]:
    try:
        stat = os.stat(path)
        _, ext = os.path.splitext(path)
        kind = "video" if ext.lower() == ".mp4" else "image"
        return {
            "name": os.path.basename(path),
            "size": stat.st_size,
            "type": kind,
            "url": f"/uploads/{os.path.basename(path)}",
        }
    except Exception:
        logging.exception("probe failed for %s", path)
        return {"name": os.path.basename(path), "size": 0, "type": "unknown"}


def _validate_render_params(payload: Dict[str, Any]) -> Dict[str, Any]:
    def _f(name: str, lo: float, hi: float, default: float) -> float:
        try:
            val = float(payload.get(name, default))
        except Exception:
            val = default
        return max(lo, min(hi, val))

    def _b(name: str, default: bool) -> bool:
        return bool(payload.get(name, default))

    rotate = int(payload.get("rotate", 0))
    if rotate not in (0, 90, 180, 270):
        rotate = 0

    rgb_balance = payload.get("rgb_balance", [1.0, 1.0, 1.0])
    if not isinstance(rgb_balance, (list, tuple)) or len(rgb_balance) != 3:
        rgb_balance = [1.0, 1.0, 1.0]
    rgb_balance = [max(0.5, min(1.5, float(x))) for x in rgb_balance]

    return {
        "fps_cap": int(_f("fps_cap", 1, 240, 60)),
        "gamma": _f("gamma", 1.0, 3.0, 2.2),
        "mirror_x": _b("mirror_x", False),
        "mirror_y": _b("mirror_y", False),
        "rotate": rotate,
        "rgb_balance": rgb_balance,
    }


def _default_config() -> Dict[str, Any]:
    return {
        "device": "PREVIEW",
        "render": {
            "scale": "LANCZOS",
            "fps_cap": 60,
            "gamma": 2.2,
            "rgb_balance": [1.0, 1.0, 1.0],
            "mirror_x": False,
            "mirror_y": False,
            "rotate": 0,
        },
        "ws2811": {
            "width": 10,
            "height": 10,
            "count": 100,
            "gpio": 18,
            "brightness": 128,
            "pixel_order": "GRB",
            "map_file": "config/ws2811.map.json",
        },
    }


def _create_output_device(cfg: Dict[str, Any]) -> OutputDevice:
    device_name = str(cfg.get("device", "PREVIEW")).upper()

    if device_name == "PREVIEW":
        return NullPreviewDriver(device_name="PREVIEW")

    # Placeholders for future drivers in M2
    if device_name == "HUB75":
        from core.drivers.hub75 import Hub75Driver  # lazy import

        return Hub75Driver(cfg)
    if device_name in ("WS2811", "WS2811_PI"):
        from core.drivers.ws2811_pi import Ws2811PiDriver

        return Ws2811PiDriver(cfg)
    if device_name == "WLED":
        from core.drivers.wled_udp import WledUdpDriver

        return WledUdpDriver(cfg)

    logging.warning(
        "Unknown device '%s', falling back to PREVIEW",
        device_name,
    )
    return NullPreviewDriver(device_name="PREVIEW_UNKNOWN")


def _install_signal_handlers(app: Flask) -> None:
    def _shutdown_handler(signum: int, _frame: Any) -> None:
        logging.info("Signal %s received, shutting down output device", signum)
        try:
            device: OutputDevice = app.config.get(
                "output_device"
            )  # type: ignore[assignment]
            if device:
                device.close()
        except Exception:
            logging.exception(
                "Error while closing output device",
            )
        finally:
            # Ensure process exits on SIGINT/SIGTERM after cleanup
            os._exit(0)

    # Register common termination signals
    try:
        signal.signal(signal.SIGINT, _shutdown_handler)
        signal.signal(signal.SIGTERM, _shutdown_handler)
    except Exception:
        logging.exception("Failed to install signal handlers")


class _suppress_ex:
    def __init__(self, context: str) -> None:
        self._ctx = context

    def __enter__(self) -> None:  # type: ignore[override]
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:  # type: ignore[override]
        if exc:
            logging.exception("%s: %s", self._ctx, exc)
        # Suppress exceptions
        return True


if __name__ == "__main__":
    flask_app = create_app()
    # Bind to localhost by default; override with HOST env when needed
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 5000))
    socketio.run(flask_app, host=host, port=port)
