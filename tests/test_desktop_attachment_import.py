from uuid import uuid4

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen.canvas import Canvas

from app import db
from app.desktop.bridge import DesktopBridge
from app.desktop.native import NativeCapabilities
from app.models import SearchDocument
from app.services.desktop_workspace import DesktopApplicationService


def invoke(bridge, command, **payload):
    return bridge.invoke({"request_id": str(uuid4()), "command": command, "payload": payload})


def test_native_folder_import_indexes_nested_files_under_one_entry(app, tmp_path):
    source = tmp_path / "色卡图"
    nested = source / "子目录"
    nested.mkdir(parents=True)
    (nested / "标签.txt").write_text("蓝色纸鹤标签复核", encoding="utf-8-sig")
    pdf = source / "颜色表.pdf"
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    page = Canvas(str(pdf))
    page.setFont("STSong-Light", 12)
    page.drawString(80, 750, "黄色样本颜色编号")
    page.save()

    native = NativeCapabilities(tmp_path)
    bridge = DesktopBridge(DesktopApplicationService(app), native, {})
    commands = invoke(bridge, "system.app_info")["data"]["commands"]
    assert {"library.import_directory", "library.open_directory", "library.location"} <= set(commands)
    unauthorised = invoke(bridge, "library.import_directory", path=str(source))
    assert not unauthorised["ok"] and unauthorised["error"]["code"] == "invalid_native_request"

    class FolderPicker:
        def create_file_dialog(self, *args, **kwargs):
            return str(source)

    native.attach_window(FolderPicker())
    selected = invoke(bridge, "dialog.select_directory")
    assert selected["data"] == [str(source.resolve())]
    project = invoke(bridge, "project.create", title="色卡演示")["data"]
    record = invoke(bridge, "record.create", project_id=project["id"], title="颜色复核")["data"]
    result = invoke(bridge, "library.import_directory", path=selected["data"][0],
                    project_id=project["id"], record_id=record["id"])
    assert result["ok"] and result["data"]["kind"] == "directory"
    folder_id = result["data"]["id"]
    repeated = invoke(bridge, "library.import_directory", path=selected["data"][0],
                      project_id=project["id"], record_id=record["id"])
    assert repeated["data"]["id"] == folder_id
    linked = invoke(bridge, "library.list", project_id=project["id"], record_id=record["id"])["data"]
    assert [item["display_name"] for item in linked] == [source.name]
    match = invoke(bridge, "search.query", query="黄色样本颜色编号")["data"]["items"]
    assert len(match) == 1 and match[0]["id"] == folder_id and match[0]["title"] == source.name
    assert "黄色样本颜色编号" in match[0]["excerpt"]
    assert invoke(bridge, "library.list", search="蓝色纸鹤")["data"][0]["display_name"] == source.name
    assert invoke(bridge, "library.list", search="子目录/标签.txt")["data"][0]["id"] == folder_id

    # Simulate an index created by a version that stored only file metadata.
    with app.app_context():
        entry = SearchDocument.query.filter_by(entity_type="file", entity_id=match[0]["id"]).one()
        entry.body = ""
        db.session.commit()
    assert invoke(bridge, "search.query", query="黄色样本颜色编号")["data"]["items"] == []
    assert invoke(bridge, "search.rebuild")["ok"]
    assert invoke(bridge, "search.query", query="黄色样本颜色编号")["data"]["items"][0]["id"] == match[0]["id"]
    native.open_authorized_path = lambda path: {"directory": path}
    assert invoke(bridge, "library.open_directory", id=folder_id)["data"]["directory"] == str(source.resolve())
    assert invoke(bridge, "library.location", id=folder_id)["data"]["record_id"] == record["id"]


def test_file_library_scopes_group_older_external_imports_without_modifying_them(app, tmp_path):
    source = tmp_path / "参考图像"
    detail = source / "子目录"
    detail.mkdir(parents=True)
    first = source / "first.txt"
    second = detail / "second.txt"
    project_only = tmp_path / "项目资料.txt"
    unassigned = tmp_path / "单独资料.txt"
    for path in (first, second, project_only, unassigned):
        path.write_text(path.stem, "utf-8")

    native = NativeCapabilities(tmp_path)
    native._remember([str(path) for path in (first, second, project_only, unassigned)])
    native.open_authorized_path = lambda path: {"directory": path}
    bridge = DesktopBridge(DesktopApplicationService(app), native, {})
    project = invoke(bridge, "project.create", title="色卡演示")["data"]
    record = invoke(bridge, "record.create", project_id=project["id"], title="颜色复核")["data"]
    for path in (first, second):
        provenance = source.name + "/" + path.relative_to(source).as_posix()
        assert invoke(
            bridge, "library.import", path=str(path), storage_mode="external",
            description="来源：" + provenance, project_id=project["id"], record_id=record["id"],
        )["ok"]
    direct = invoke(bridge, "library.import", path=str(project_only), storage_mode="external", project_id=project["id"])["data"]
    unlinked = invoke(bridge, "library.import", path=str(unassigned), storage_mode="external")["data"]
    old_rows = invoke(bridge, "library.list", record_id=record["id"])["data"]
    assert len(old_rows) == 2
    grouped = invoke(bridge, "library.list", record_id=record["id"], group_directories=True, pagination=True)["data"]
    group = grouped["items"][0]
    assert grouped["pagination"]["total"] == 1
    assert group["display_name"] == source.name and group["legacy_directory"]
    assert invoke(bridge, "library.open_directory", id=group["id"])["data"]["directory"] == str(source.resolve())
    assert invoke(bridge, "library.list", record_id=record["id"])["data"] == old_rows
    assert invoke(bridge, "library.location", id=direct["id"])["data"]["project_id"] == project["id"]
    project_rows = invoke(bridge, "library.list", project_id=project["id"], scope="project_files")["data"]
    assert [item["id"] for item in project_rows] == [direct["id"]]
    assert [item["id"] for item in invoke(bridge, "library.list", scope="unassigned")["data"]] == [unlinked["id"]]
    assert invoke(bridge, "library.open_directory", id=unlinked["id"])["data"]["directory"] == str(tmp_path.resolve())


def test_single_file_picker_accepts_a_path_and_preserves_unreadable_file_entry(app, tmp_path):
    sample = tmp_path / "scan.pdf"
    sample.write_bytes(b"%PDF-1.7\n")

    class FilePicker:
        def create_file_dialog(self, *args, **kwargs):
            return str(sample)

    native = NativeCapabilities(tmp_path)
    native.attach_window(FilePicker())
    bridge = DesktopBridge(DesktopApplicationService(app), native, {})
    selected = invoke(bridge, "dialog.open_file", kind="any")
    assert selected["data"] == [str(sample.resolve())]
    imported = invoke(bridge, "library.import", path=selected["data"][0], storage_mode="managed")
    assert imported["ok"]
    matches = invoke(bridge, "search.query", query="scan.pdf")["data"]["items"]
    assert [item["id"] for item in matches] == [imported["data"]["id"]]
