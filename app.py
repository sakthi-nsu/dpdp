import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from flask import Flask, abort, redirect, request, send_from_directory


BASE_DIR = Path(__file__).resolve().parent
WEB3FORMS_URL = "https://api.web3forms.com/submit"
WEB3FORMS_ACCESS_KEY = os.getenv("WEB3FORMS_ACCESS_KEY", "").strip()

app = Flask(__name__)


def _append_query(url: str, key: str, value: str) -> str:
    parts = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parts.query, keep_blank_values=True)
    query[key] = [value]
    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, new_query, parts.fragment)
    )


def _safe_return_url(url: str) -> str:
    if not url:
        return "/contact"
    if url.startswith("//"):
        return "/contact"
    if url.startswith("/"):
        return url
    if url.endswith(".html"):
        clean = url[:-5]
        if clean == "index":
            return "/"
        return f"/{clean}"
    return "/contact"


def _forward_to_web3forms(payload: dict) -> tuple[bool, str]:
    data = urllib.parse.urlencode(payload).encode("utf-8")
    req = urllib.request.Request(
        WEB3FORMS_URL,
        data=data,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body)
            return bool(parsed.get("success")), parsed.get("message", "")
    except Exception as exc:
        return False, str(exc)


@app.post("/submit-form")
def submit_form():
    return_url = _safe_return_url(request.form.get("return_url", ""))

    if not WEB3FORMS_ACCESS_KEY:
        return redirect(_append_query(return_url, "status", "missing_access_key"))

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    message = request.form.get("message", "").strip()
    subject = request.form.get("subject", "").strip()
    company = request.form.get("company", "").strip()

    if not (name and email and message):
        return redirect(_append_query(return_url, "status", "invalid_form"))

    payload = {
        "access_key": WEB3FORMS_ACCESS_KEY,
        "name": name,
        "email": email,
        "message": message,
    }
    if subject:
        payload["subject"] = subject
    if company:
        payload["company"] = company

    ok, _ = _forward_to_web3forms(payload)
    status = "success" if ok else "error"
    return redirect(_append_query(return_url, "status", status))


@app.get("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/<path:filename>")
def static_pages(filename: str):
    # Redirect legacy .html URLs to clean extensionless URLs.
    if filename.endswith(".html"):
        clean = filename[:-5]
        if clean == "index":
            return redirect("/", code=301)
        return redirect(f"/{clean}", code=301)

    # Serve clean extensionless routes: /contact -> contact.html
    clean_html = BASE_DIR / f"{filename}.html"
    if clean_html.is_file():
        return send_from_directory(BASE_DIR, f"{filename}.html")

    # Serve static files directly: css/js/images/svg/etc.
    file_path = BASE_DIR / filename
    if not file_path.is_file():
        abort(404)
    return send_from_directory(BASE_DIR, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
