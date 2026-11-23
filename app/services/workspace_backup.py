"""Portable, non-destructive snapshots; importing a backup is a separate operation."""
from datetime import datetime
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import uuid
import zipfile

from .errors import NotFoundError, ValidationError


def create_backup(app, payload):
    scope = payload.get("scope", "database")
    if scope not in {"database", "workspace"}:
        raise ValidationError("备份范围必须为 database 或 workspace。")
    root = Path(app.instance_path).resolve()
    source = root / "research.db"
    if not source.is_file():
        raise NotFoundError("当前数据库文件不存在。")
    destination = Path(app.config["BACKUP_DIR"]).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:12]}"
    output = destination / f"research-{stamp}{'.zip' if scope == 'workspace' else '.db'}"
    with tempfile.TemporaryDirectory(prefix=".rlab-backup-", dir=destination) as staging:
        snapshot = Path(staging) / "research.db"
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original, closing(sqlite3.connect(snapshot)) as copy:
            original.backup(copy)
        if scope == "database":
            snapshot.replace(output)
            return {"path": str(output), "size_bytes": output.stat().st_size, "scope": scope}

        # Only app-managed roots are copied. Symlinks must never expand this scope.
        files = [(snapshot, "research.db")]
        for directory in (root / "library", root / "uploads"):
            if directory.is_symlink():
                raise ValidationError("托管目录不能是外部符号链接。")
            if not directory.exists():
                continue
            for path in sorted(directory.rglob("*")):
                if path.is_symlink() or not path.resolve().is_relative_to(root):
                    raise ValidationError("托管目录包含外部链接，未生成备份。")
                if path.is_file():
                    files.append((path, path.relative_to(root).as_posix()))
        manifest = {"format_version": 1, "scope": scope, "created_at": datetime.now().astimezone().isoformat(),
                    "files": [], "excluded": ["external_files", "credential_keys", "logs", "webview_profile", "previous_backups"],
                    "notes": "External files remain at their original locations. Reconfigure API credentials after recovery on another computer."}
        temporary = Path(staging) / "workspace.zip"
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for path, name in files:
                digest, size = hashlib.sha256(), 0
                with path.open("rb") as stream, archive.open(name, "w", force_zip64=True) as entry:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        entry.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                manifest["files"].append({"path": name, "sha256": digest.hexdigest(), "size_bytes": size})
            _verify_managed_references(snapshot, manifest)
            archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        temporary.replace(output)
    return {"path": str(output), "size_bytes": output.stat().st_size, "scope": scope,
            "file_count": len(manifest["files"]), "excluded": manifest["excluded"]}


def _verify_managed_references(snapshot, manifest):
    """Refuse to advertise a complete archive if a registered file is missing/changed."""
    archived = {item["path"]: item for item in manifest["files"]}
    with closing(sqlite3.connect(snapshot)) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(library_item)")}
        if not {"storage_mode", "managed_relative_path", "sha256", "size_bytes"} <= columns:
            return
        for relative, digest, size in connection.execute(
            "SELECT managed_relative_path, sha256, size_bytes FROM library_item WHERE storage_mode='managed'"
        ):
            item = archived.get(f"library/{relative}")
            if not item or (digest and item["sha256"] != digest) or item["size_bytes"] != size:
                raise ValidationError("托管文件缺失或内容变化，未生成完整备份；请先在资料库核验文件。")
