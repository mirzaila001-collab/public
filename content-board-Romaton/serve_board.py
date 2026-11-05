# -*- coding: utf-8 -*-
"""Serve the content board and keep stage clicks in stages.json."""
import json
import subprocess
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STAGES = ROOT / "data" / "stages.json"
LOCK = threading.Lock()
ALLOWED = {"open", "write", "live"}


def read_stages():
    if not STAGES.exists():
        return {}
    try:
        data = json.loads(STAGES.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and v in ALLOWED}


def write_stages(data):
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    tmp = STAGES.with_suffix(".json.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(STAGES)
    if (ROOT / ".git").is_dir():
        subprocess.run(["git", "add", "--", "stages.json"], cwd=ROOT, check=False)
        subprocess.run(
            ["git", "commit", "-m", "Update content board stages", "--", "stages.json"],
            cwd=ROOT,
            check=False,
        )


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/api/stages":
            body = json.dumps(read_stages(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/stages":
            self.send_error(404)
            return
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0 or n > 20000:
            self.send_error(400)
            return
        try:
            payload = json.loads(self.rfile.read(n).decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400)
            return
        sid = str(payload.get("id") or "")
        stage = payload.get("stage")
        if stage not in ALLOWED or not sid or len(sid) > 80 or any(c in sid for c in " \t\r\n"):
            self.send_error(400)
            return
        with LOCK:
            cur = read_stages()
            if stage == "open":
                cur.pop(sid, None)
            else:
                cur[sid] = stage
            write_stages(cur)
            saved = dict(cur)
        body = json.dumps(saved, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    if not STAGES.exists():
        write_stages({})
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("http://127.0.0.1:8765/romatone-content-board.html")
    server.serve_forever()
