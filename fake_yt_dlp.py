"""Stand-in for yt_dlp so the server logic can be tested without internet."""
import os, types

class FakeYDL:
    last_opts = None
    def __init__(self, opts): self.opts = opts; FakeYDL.last_opts = opts
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def extract_info(self, url, download=False):
        if "private" in url: raise Exception("login required")
        if "carousel" in url:
            return {"title": "Album", "entries": [
                {"title": "a", "thumbnail": "https://scontent.cdninstagram.com/a.jpg", "formats": []},
                {"title": "b", "thumbnail": "https://scontent.cdninstagram.com/b.jpg", "vcodec": "h264", "duration": 12}]}
        return {"title": "My reel", "uploader": "tester", "duration": 65,
                "thumbnail": "https://scontent.cdninstagram.com/t.jpg",
                "formats": [{"vcodec": "h264"}]}
    def download(self, urls):
        if "fail" in urls[0]: raise Exception("boom")
        out = self.opts["outtmpl"].replace("%(id)s", "abc").replace("%(ext)s",
              "mp3" if self.opts.get("postprocessors") else "mp4")
        open(out, "wb").write(b"FAKEDATA")

mod = types.ModuleType("yt_dlp"); mod.YoutubeDL = FakeYDL
