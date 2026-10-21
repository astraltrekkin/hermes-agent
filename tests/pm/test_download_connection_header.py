"""pm downloads must not send urllib's forced Connection: close (#142463).

Some CDN edges RST mid-body when they see that fingerprint. The downloader
opener strips it; this pins the wire header, not the implementation shape.
"""

from __future__ import annotations

import hashlib
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

from pm.downloader import Download, Source, _OPENER, _UA
from pm import network


def test_opener_omits_connection_close_on_the_wire():
    seen = []

    class Capture(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append(self.headers.get("Connection"))
            body = b"ok"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with HTTPServer(("127.0.0.1", 0), Capture) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/asset"
            with _OPENER.open(urllib.request.Request(url, headers=_UA), timeout=5) as resp:
                assert resp.read() == b"ok"
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert seen == [None] or seen == [""]
    assert all((value or "").lower() != "close" for value in seen)


def test_ranged_download_also_omits_connection_close(tmp_path):
    payload = b"0123456789" * 200_000  # ~2 MiB so parallel ranges fire
    seen = []

    class Capture(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            seen.append(self.headers.get("Connection"))
            rng = self.headers.get("Range")
            if rng == "bytes=0-0":
                self.send_response(206)
                self.send_header("Content-Range", f"bytes 0-0/{len(payload)}")
                self.send_header("Content-Length", "1")
                self.send_header("ETag", '"probe"')
                self.end_headers()
                self.wfile.write(payload[:1])
                return
            start_s, end_s = rng.removeprefix("bytes=").split("-", 1)
            start, end = int(start_s), int(end_s)
            body = payload[start:end + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(payload)}")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", '"probe"')
            self.end_headers()
            self.wfile.write(body)

    dest = tmp_path / "blob.bin"
    with HTTPServer(("127.0.0.1", 0), Capture) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_address[1]}/blob"
            Download(
                [Source(url, dest, hashlib.sha256(payload).hexdigest())],
                connections=2,
                partials_dir=tmp_path / "partials",
            ).run()
        finally:
            server.shutdown()
            thread.join(timeout=5)

    assert dest.read_bytes() == payload
    assert seen
    assert all((value or "").lower() != "close" for value in seen)


def test_without_connection_close_strips_urllib_injection():
    import http.client as http_client

    captured = {}

    class Recording(http_client.HTTPConnection):
        def request(self, method, url, body=None, headers=None, *, encode_chunked=False):
            captured.clear()
            captured.update(headers or {})
            # Do not open a real socket; callers only inspect headers.

    wrapped = network.without_connection_close(Recording)
    conn = wrapped("example.invalid")
    conn.request("GET", "/", headers={"Connection": "close", "User-Agent": "t"})
    assert all(k.lower() != "connection" for k in captured)
    assert captured["User-Agent"] == "t"
