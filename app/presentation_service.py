import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class PresentationBuildError(RuntimeError):
    pass


def _node_executable():
    configured = os.getenv("PRESENTATION_NODE_PATH", "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path(shutil.which("node")) if shutil.which("node") else None,
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise PresentationBuildError("未找到 Node.js。请设置 PRESENTATION_NODE_PATH 后重试。")


def _artifact_tool_module():
    configured = os.getenv("ARTIFACT_TOOL_MODULE", "").strip()
    candidates = [
        Path(configured) if configured else None,
        Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "node_modules" / "@oai" / "artifact-tool" / "dist" / "artifact_tool.mjs",
    ]
    for candidate in candidates:
        if candidate and candidate.is_file():
            return candidate
    raise PresentationBuildError(
        "未找到演示文稿运行时。请设置 ARTIFACT_TOOL_MODULE 指向 artifact_tool.mjs。"
    )


def build_weekly_presentation(payload):
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "build_weekly_presentation.mjs"
    if not script_path.is_file():
        raise PresentationBuildError("PPT 生成脚本缺失。")
    with tempfile.TemporaryDirectory(prefix="research-presentation-") as temp_dir:
        work_dir = Path(temp_dir)
        input_path = work_dir / "report.json"
        output_path = work_dir / "weekly-report.pptx"
        input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        environment = os.environ.copy()
        environment["ARTIFACT_TOOL_MODULE"] = _artifact_tool_module().as_uri()
        try:
            completed = subprocess.run(
                [str(_node_executable()), str(script_path), str(input_path), str(output_path)],
                cwd=str(work_dir), env=environment, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=180, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PresentationBuildError(f"PPT 生成进程启动失败：{exc}") from exc
        if completed.returncode != 0 or not output_path.is_file():
            detail = (completed.stderr or completed.stdout or "未知错误").strip()[-1200:]
            raise PresentationBuildError(f"PPT 生成失败：{detail}")
        return output_path.read_bytes()
