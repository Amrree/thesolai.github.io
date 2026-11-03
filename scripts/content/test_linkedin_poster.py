#!/usr/bin/env python3
"""
Integration test for linkedin-poster.py against a mock LinkedIn API.

Runs the real poster against a local HTTP server that mimics the three
LinkedIn endpoints the script uses, so the request shapes, the image
upload handshake, the rest -> legacy fallback, and the state log are all
verified without touching the real API.

Usage:  python3 scripts/content/test_linkedin_poster.py
"""
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PORT = 8799
CALLS = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, payload):
        body = json.dumps(payload).encode() if payload is not None else b""
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        CALLS.append(("GET", self.path))
        if self.path.startswith("/v2/me"):
            self._send(200, {"id": "TESTPERSON123"})
        elif self.path.startswith("/v2/organizations"):
            self._send(200, {"elements": [{"organization": "urn:li:organization:TESTORG", "role": "ADMINISTRATOR"}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        CALLS.append(("POST", self.path, raw.decode() if raw else ""))

        if self.path.startswith("/rest/images"):
            self._send(200, {"value": {
                "image": "urn:li:image:MOCKIMAGE",
                "uploadUrl": f"http://127.0.0.1:{PORT}/upload-binary",
            }})
        elif self.path.startswith("/rest/posts"):
            body = json.loads(raw)
            version = self.headers.get("LinkedIn-Version")
            if version != "202408":
                # Simulate a retired API version so the script falls back
                # to the legacy endpoint.
                self._send(400, {"message": f"unsupported version {version}"})
                return
            # Assert the shape LinkedIn expects.
            assert body["author"] == "urn:li:person:TESTPERSON123", body["author"]
            assert body["lifecycleState"] == "PUBLISHED"
            assert body["visibility"] == "PUBLIC"
            assert body["distribution"]["feedDistribution"] == "MAIN_FEED"
            assert "text" in body["content"]
            assert body["content"]["media"]["id"] == "urn:li:image:MOCKIMAGE"
            assert self.headers.get("Authorization") == "Bearer TESTTOKEN"
            self._send(201, {"id": "urn:li:share:MOCKSHARE"})
        elif self.path.startswith("/v2/ugcPosts"):
            body = json.loads(raw)
            assert body["lifecycleState"] == "PUBLISHED"
            assert body["author"]["ln"] == "person"
            share = body["specificContent"]["com.linkedin.ugc.ShareContent"]
            assert "shareCommentary" in share
            self._send(201, {"id": "urn:li:share:MOCKLEGACY"})
        else:
            self._send(404, {"error": "not found"})

    def do_PUT(self):
        length = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(length)
        CALLS.append(("PUT", self.path, len(data)))
        assert self.path == "/upload-binary"
        assert len(data) > 1000, "image binary was not uploaded"
        self._send(201, None)


def run(args, env):
    return subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts/content/linkedin-poster.py")] + args,
        capture_output=True, text=True, env=env, cwd=REPO,
    )


def main():
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    home = os.path.join(REPO, ".testhome")
    os.makedirs(home, exist_ok=True)
    env = dict(os.environ, HOME=home, LINKEDIN_ACCESS_TOKEN="TESTTOKEN")

    # Point the script at the mock. The user config lives in the secrets
    # directory and takes precedence over the repo copy.
    secrets_dir = os.path.join(home, ".openclaw/workspace/secrets")
    os.makedirs(secrets_dir, exist_ok=True)
    cfg_path = os.path.join(secrets_dir, "linkedin-config.json")
    cfg = {
        "site_url": "https://thesolai.github.io",
        "authors": {"person": {"urn": "urn:li:person:TESTPERSON123"}},
        "default_author": "person",
        "default_voice": "hybrid",
        "hashtags": {"always": ["aiagents", "automation"], "max": 5},
        "link": {"in_body": True},
        "api": {"base_url": f"http://127.0.0.1:{PORT}", "version": "202408", "visibility": "PUBLIC"},
    }
    with open(cfg_path, "w") as f:
        json.dump(cfg, f)

    failures = []

    # --- test 1: publish happy path -------------------------------------
    result = run(["--post", "--file", "_posts/2026-07-21-the-skills-audit.md"], env)
    if result.returncode != 0:
        failures.append(f"publish failed: {result.stderr[-600:]}")
    if "Published:" not in result.stdout:
        failures.append("no 'Published' in stdout")

    posted_log = os.path.join(home, ".openclaw/workspace/scripts/content/logs/linkedin-posted.json")
    if not os.path.exists(posted_log):
        failures.append("posted log was not written")
    else:
        with open(posted_log) as f:
            log = json.load(f)
        if "2026-07-21-the-skills-audit.md" not in log:
            failures.append("posted log does not record the post")
        if log["2026-07-21-the-skills-audit.md"]["url"] != "urn:li:share:MOCKSHARE":
            failures.append("posted log has the wrong url")

    # The post must not be selected again.
    listing = run(["--list", "--limit", "3"], env)
    if "the-skills-audit" in listing.stdout:
        failures.append("an already-posted post is still being offered")

    # --- test 2: the rest -> legacy fallback ---------------------------
    CALLS.clear()
    cfg["api"]["version"] = "199901"  # force a version error from the mock
    with open(cfg_path, "w") as f:
        json.dump(cfg, f)
    result = run(["--post", "--file", "_posts/2026-06-15-the-skills-problem.md"], env)
    if "retrying with the legacy endpoint" not in result.stderr:
        failures.append("the legacy fallback did not trigger")

    server.shutdown()

    print("\n=== calls made ===")
    for call in CALLS:
        detail = str(call[2]) if len(call) > 2 else ""
        print(" ", call[0], call[1], (detail[:110] + "...") if len(detail) > 110 else detail)

    print()
    if failures:
        print("FAILURES:")
        for failure in failures:
            print("  -", failure)
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
