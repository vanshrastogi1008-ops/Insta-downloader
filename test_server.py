import os, sys, shutil, glob, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fake_yt_dlp
sys.modules["yt_dlp"] = fake_yt_dlp.mod
os.environ["RATE_LIMIT_PER_MIN"] = "1000"
import server

IG = "https://www.instagram.com/reel/XYZ/"

class T(unittest.TestCase):
    def setUp(self): self.c = server.app.test_client()

    def test_home_serves_html(self):
        r = self.c.get("/"); self.assertEqual(r.status_code, 200); self.assertIn("रील सेवर", r.get_data(as_text=True))
    def test_static_assets(self):
        for p in ("/style.css", "/app.js"): self.assertEqual(self.c.get(p).status_code, 200)
    def test_info_ok(self):
        r = self.c.post("/api/info", json={"url": IG}); d = r.get_json()
        self.assertEqual(r.status_code, 200); self.assertEqual(len(d["items"]), 1)
        it = d["items"][0]; self.assertTrue(it["video"] and it["audio"] and it["image"])
    def test_info_carousel(self):
        d = self.c.post("/api/info", json={"url": IG + "carousel"}).get_json()
        self.assertEqual([i["video"] for i in d["items"]], [False, True])
    def test_info_rejects_non_instagram(self):
        for u in ("https://evil.com/?https://instagram.com", "http://localhost:8000", "file:///etc/passwd",
                  "https://instagram.com.evil.com/x", "", "javascript:alert(1)"):
            self.assertEqual(self.c.post("/api/info", json={"url": u}).status_code, 400, u)
    def test_info_bad_body(self):
        self.assertEqual(self.c.post("/api/info", data="x").status_code, 400)
        self.assertEqual(self.c.post("/api/info", json={"url": 123}).status_code, 400)
    def test_info_private(self):
        self.assertEqual(self.c.post("/api/info", json={"url": IG + "private"}).status_code, 422)
    def test_download_video_and_cleanup(self):
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "reel_*")))
        r = self.c.get("/api/download", query_string={"url": IG, "kind": "video", "item": "1"})
        self.assertEqual(r.status_code, 200); self.assertEqual(r.data, b"FAKEDATA")
        self.assertIn("attachment", r.headers["Content-Disposition"]); self.assertIn(".mp4", r.headers["Content-Disposition"])
        r.close()
        self.assertEqual(set(glob.glob(os.path.join(tempfile.gettempdir(), "reel_*"))), before)
    def test_download_audio(self):
        r = self.c.get("/api/download", query_string={"url": IG, "kind": "audio", "item": "1"})
        self.assertIn(".mp3", r.headers["Content-Disposition"]); r.close()
    def test_download_failure_cleans(self):
        before = set(glob.glob(os.path.join(tempfile.gettempdir(), "reel_*")))
        r = self.c.get("/api/download", query_string={"url": IG + "fail", "kind": "video", "item": "1"})
        self.assertEqual(r.status_code, 422)
        self.assertEqual(set(glob.glob(os.path.join(tempfile.gettempdir(), "reel_*"))), before)
    def test_download_bad_params(self):
        for q in ({"url": IG, "kind": "exe", "item": "1"}, {"url": IG, "kind": "video", "item": "../x"},
                  {"url": "https://evil.com", "kind": "video", "item": "1"}, {"url": IG, "kind": "video", "item": "99999"}):
            r = self.c.get("/api/download", query_string=q); self.assertEqual(r.status_code, 400, q); r.close()
    def test_image_ssrf_blocked(self):
        for s in ("http://169.254.169.254/", "https://evil.com/a.jpg", "https://cdninstagram.com.evil.com/a.jpg",
                  "https://localhost/a.jpg", ""):
            self.assertEqual(self.c.get("/api/image", query_string={"src": s}).status_code, 400, s)
    def test_rate_limit(self):
        server.RATE_LIMIT = 3; server._hits.clear()
        codes = [self.c.post("/api/info", json={"url": IG}).status_code for _ in range(5)]
        server.RATE_LIMIT = 1000; server._hits.clear()
        self.assertEqual(codes, [200, 200, 200, 429, 429])
    def test_health(self):
        self.assertEqual(self.c.get("/healthz").status_code, 200)

if __name__ == "__main__": unittest.main(verbosity=2)
