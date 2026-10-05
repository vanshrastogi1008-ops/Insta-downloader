"""Reel Saver - paste an Instagram link, download video / audio / image.
Backend: Flask + yt-dlp. Run locally:  python server.py
"""
import glob
import logging
import mimetypes
import os
import shutil
import tempfile
import threading
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

import requests
import yt_dlp
from flask import Flask, Response, jsonify, request, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__, static_folder="static", static_url_path="")
if os.environ.get("TRUST_PROXY", "1") == "1":  # hosts like Render/Railway sit behind one proxy
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("reelsaver")

IG_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com", "instagr.am"}
IMG_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net")
COOKIES_FILE = os.environ.get("COOKIES_FILE", "cookies.txt")  # optional
RATE_LIMIT = int(os.environ.get("RATE_LIMIT_PER_MIN", "20"))
MAX_FILE_MB = int(os.environ.get("MAX_FILE_MB", "200"))
MAX_ITEM = 50
TMP_PREFIX = "reel_"

_hits = defaultdict(deque)
_hits_lock = threading.Lock()
_slots = threading.BoundedSemaphore(int(os.environ.get("MAX_CONCURRENT_DOWNLOADS", "3")))


def rate_limited(ip: str) -> bool:
    now = time.time()
    with _hits_lock:
        if len(_hits) > 5000:  # drop idle IPs so memory can't grow forever
            for k in [k for k, q in _hits.items() if not q or now - q[-1] > 60]:
                del _hits[k]
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            return True
        q.append(now)
        return False


def sweep_old_temp_dirs(max_age=3600):
    for d in glob.glob(os.path.join(tempfile.gettempdir(), TMP_PREFIX + "*")):
        try:
            if time.time() - os.path.getmtime(d) > max_age:
                shutil.rmtree(d, ignore_errors=True)
        except OSError:
            pass


@app.before_request
def limit():
    if request.path.startswith("/api/") and rate_limited(request.remote_addr or "?"):
        return jsonify(error="बहुत ज़्यादा रिक्वेस्ट। एक मिनट बाद फिर कोशिश करें।"), 429


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


def is_instagram_url(url) -> bool:
    if not isinstance(url, str) or len(url) > 500:
        return False
    try:
        p = urlparse(url)
    except ValueError:
        return False
    return p.scheme in ("http", "https") and (p.hostname or "").lower() in IG_HOSTS


def ydl_opts(extra=None):
    opts = {"quiet": True, "no_warnings": True, "socket_timeout": 25, "noprogress": True}
    if os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    if extra:
        opts.update(extra)
    return opts


def entry_has_video(e: dict) -> bool:
    if e.get("vcodec") not in (None, "none"):
        return True
    return any(f.get("vcodec") not in (None, "none") for f in e.get("formats") or [])


def stream_and_cleanup(path, tmp):
    """Stream the file, then delete the temp folder (also if the client disconnects)."""
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                yield chunk
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/healthz")
def healthz():
    return jsonify(ok=True)


@app.post("/api/info")
def info():
    body = request.get_json(silent=True)
    url = body.get("url") if isinstance(body, dict) else None
    url = url.strip() if isinstance(url, str) else url
    if not is_instagram_url(url):
        return jsonify(error="कृपया Instagram का सही लिंक डालें।"), 400
    try:
        with yt_dlp.YoutubeDL(ydl_opts({"skip_download": True})) as y:
            data = y.extract_info(url, download=False)
    except Exception as exc:
        log.warning("info failed: %s", str(exc)[:200])
        return jsonify(error="यह लिंक नहीं खुल पाया। पोस्ट प्राइवेट हो सकती है, या Instagram ने रिक्वेस्ट रोक दी है।"), 422

    entries = [e for e in (data.get("entries") or [data]) if e]
    items = []
    for i, e in enumerate(entries[:MAX_ITEM], start=1):
        video = entry_has_video(e)
        items.append({
            "index": i,
            "title": e.get("title") or data.get("title") or f"Instagram {i}",
            "uploader": e.get("uploader") or data.get("uploader"),
            "thumbnail": e.get("thumbnail"),
            "duration": e.get("duration"),
            "video": video,
            "audio": video,
            "image": bool(e.get("thumbnail")),
        })
    return jsonify(url=url, items=items)


@app.get("/api/download")
def download():
    url = (request.args.get("url") or "").strip()
    kind = request.args.get("kind", "video")
    item = request.args.get("item", "1")
    if (not is_instagram_url(url) or kind not in ("video", "audio")
            or not item.isdigit() or not 1 <= int(item) <= MAX_ITEM):
        return jsonify(error="गलत रिक्वेस्ट"), 400
    if not _slots.acquire(blocking=False):
        return jsonify(error="सर्वर अभी व्यस्त है। थोड़ी देर बाद फिर कोशिश करें।"), 503

    tmp = tempfile.mkdtemp(prefix=TMP_PREFIX)
    extra = {"outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
             "playlist_items": item, "max_filesize": MAX_FILE_MB * 1024 * 1024}
    if kind == "video":
        extra["format"] = "best[ext=mp4]/bestvideo*+bestaudio/best"
        extra["merge_output_format"] = "mp4"
    else:
        extra["format"] = "bestaudio/best"
        extra["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                    "preferredcodec": "mp3", "preferredquality": "192"}]
    try:
        with yt_dlp.YoutubeDL(ydl_opts(extra)) as y:
            y.download([url])
        files = os.listdir(tmp)
        if not files:
            raise RuntimeError("no file produced")
        path = os.path.join(tmp, files[0])
    except Exception as exc:
        log.warning("download failed: %s", str(exc)[:200])
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error="डाउनलोड नहीं हो पाया।"), 422
    finally:
        _slots.release()

    filename = f"instagram_{item}{os.path.splitext(path)[1]}"
    mime = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    return Response(stream_and_cleanup(path, tmp), mimetype=mime, headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(os.path.getsize(path))})


@app.get("/api/image")
def image():
    src = request.args.get("src", "")
    host = (urlparse(src).hostname or "").lower()
    if not src.startswith("https://") or not host.endswith(IMG_HOST_SUFFIXES):
        return jsonify(error="गलत इमेज लिंक"), 400
    try:
        # no redirects: a redirect could point to an internal address
        r = requests.get(src, timeout=20, stream=True, allow_redirects=False)
        r.raise_for_status()
    except requests.RequestException:
        return jsonify(error="इमेज नहीं मिली।"), 422
    ctype = r.headers.get("Content-Type", "")
    if not ctype.startswith("image/"):
        r.close()
        return jsonify(error="यह इमेज नहीं है।"), 422
    ext = "png" if "png" in ctype else "webp" if "webp" in ctype else "jpg"
    resp = Response(r.iter_content(65536), content_type=ctype, headers={
        "Content-Disposition": f'attachment; filename="instagram_image.{ext}"'})
    resp.call_on_close(r.close)
    return resp


sweep_old_temp_dirs()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
