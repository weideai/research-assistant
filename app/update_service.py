import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from flask import Blueprint, current_app, jsonify, request
from flask_login import login_required

from .version import APP_VERSION, GITHUB_REPOSITORY, UPDATE_CACHE_HOURS


bp = Blueprint("updates", __name__, url_prefix="/updates")


def _utcnow():
    return datetime.now(timezone.utc)


def _version_tuple(value):
    normalized = str(value or "").strip().lower().lstrip("v")
    core = normalized.split("+", 1)[0].split("-", 1)[0]
    parts = core.split(".")
    if not parts or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in (parts + ["0", "0"])[:3])


def is_newer_version(latest, current=APP_VERSION):
    latest_parts = _version_tuple(latest)
    current_parts = _version_tuple(current)
    return bool(latest_parts and current_parts and latest_parts > current_parts)


def _read_cache(cache_path):
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        checked_at = datetime.fromisoformat(payload["checked_at"])
        if checked_at.tzinfo is None:
            checked_at = checked_at.replace(tzinfo=timezone.utc)
        return payload, checked_at
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None, None


def _write_cache(cache_path, payload):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(cache_path)


def _fetch_latest_release(repository, timeout=4):
    request = Request(
        f"https://api.github.com/repos/{repository}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"R-LAB-Research-Assistant/{APP_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        release = json.loads(response.read().decode("utf-8"))
    return {
        "latest_version": str(release.get("tag_name") or "").lstrip("v"),
        "release_url": str(release.get("html_url") or ""),
        "release_name": str(release.get("name") or release.get("tag_name") or ""),
        "published_at": str(release.get("published_at") or ""),
    }


def check_for_update(instance_path, repository=GITHUB_REPOSITORY, cache_hours=UPDATE_CACHE_HOURS, force=False):
    cache_path = Path(instance_path) / "update-check.json"
    cached, checked_at = _read_cache(cache_path)
    now = _utcnow()
    if cached and checked_at and not force and now - checked_at < timedelta(hours=cache_hours):
        return {**cached, "cached": True, "stale": False}

    try:
        release = _fetch_latest_release(repository)
        result = {
            "status": "ok",
            "current_version": APP_VERSION,
            "update_available": is_newer_version(release["latest_version"]),
            "checked_at": now.isoformat(),
            **release,
        }
        _write_cache(cache_path, result)
        return {**result, "cached": False, "stale": False}
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError):
        if cached:
            return {**cached, "cached": True, "stale": True}
        return {
            "status": "offline",
            "current_version": APP_VERSION,
            "latest_version": "",
            "release_url": "",
            "release_name": "",
            "published_at": "",
            "checked_at": now.isoformat(),
            "update_available": False,
            "cached": False,
            "stale": False,
        }


@bp.get("/check")
@login_required
def check():
    if not current_app.config["UPDATE_CHECK_ENABLED"]:
        return jsonify({
            "enabled": False,
            "status": "disabled",
            "current_version": APP_VERSION,
            "latest_version": "",
            "update_available": False,
        })
    force = request.args.get("force") == "1"
    result = check_for_update(
        current_app.instance_path,
        repository=current_app.config["UPDATE_REPOSITORY"],
        cache_hours=current_app.config["UPDATE_CACHE_HOURS"],
        force=force,
    )
    result["enabled"] = True
    return jsonify(result)
