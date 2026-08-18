import json
import threading
import urllib.error

from app import db
from app.models import LibraryItem, LiteratureItem, User, ZoteroCollection, literature_library_item
from app.services.desktop_workspace import DesktopApplicationService
import app.services.desktop_modules as desktop_modules


def desktop_service(app):
    with app.app_context():
        db.session.add(User(
            name="Zotero 同步测试",
            email="zotero-sync@example.invalid",
            password_hash="local",
            role="system_admin",
        ))
        db.session.commit()
    return DesktopApplicationService(app)


class Response:
    def __init__(self, payload, headers=None):
        self.payload = payload
        self.headers = headers or {}

    def read(self):
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def zotero_item(key, title=None, version=1):
    return {
        "key": key,
        "version": version,
        "data": {
            "key": key,
            "title": title if title is not None else f"文献 {key}",
            "creators": [],
        },
    }


def test_zotero_select_url_supports_personal_and_group_libraries():
    assert (
        desktop_modules._zotero_select_url("zotero:0:ABCD1234")
        == "zotero://select/library/items/ABCD1234"
    )
    assert (
        desktop_modules._zotero_select_url("zotero:groups:12345:WXYZ6789")
        == "zotero://select/groups/12345/items/WXYZ6789"
    )
    assert desktop_modules._zotero_select_url("manual:item") == ""


def test_zotero_sync_fetches_every_page_before_reconciling_missing_items(app, monkeypatch):
    service = desktop_service(app)
    first_page = [zotero_item(f"ITEM{i:04d}") for i in range(100)]
    second_page = [zotero_item("ITEM0100")]
    requested_urls = []

    def urlopen(request, **_kwargs):
        requested_urls.append(request.full_url)
        if "start=0" in request.full_url:
            return Response(first_page, {"Total-Results": "101"})
        if "start=100" in request.full_url:
            return Response(second_page, {"Total-Results": "101"})
        raise AssertionError(f"unexpected Zotero page: {request.full_url}")

    monkeypatch.setattr(desktop_modules.urllib.request, "urlopen", urlopen)
    result = service.zotero_sync()

    assert result["state"] == "connected"
    assert result["added"] == 101
    assert result["updated"] == 0
    assert result["restored"] == 0
    assert result["missing"] == 0
    assert result["incremental"] is False
    assert len(service.list_literature()) == 101
    assert any("/items?" in url for url in requested_urls)
    assert any("start=100" in url for url in requested_urls)


def test_zotero_sync_only_marks_missing_after_a_complete_fetch(app, monkeypatch):
    service = desktop_service(app)
    existing = service.save_literature({
        "title": "应保留来源状态",
        "source": "zotero",
        "source_key": "zotero:0:KEEP0001",
    })
    first_page = [zotero_item(f"PAGE{i:04d}") for i in range(100)]

    def urlopen(request, **_kwargs):
        if "start=0" in request.full_url:
            return Response(first_page, {"Total-Results": "101"})
        raise urllib.error.URLError("second page failed")

    monkeypatch.setattr(desktop_modules.urllib.request, "urlopen", urlopen)
    result = service.zotero_sync()

    assert result["state"] == "unavailable"
    assert result["added"] == 0
    assert service.get_literature({"id": existing["id"]})["source_missing"] is False


def test_zotero_sync_reports_real_missing_count_after_complete_fetch(app, monkeypatch):
    service = desktop_service(app)
    existing = service.save_literature({
        "title": "已从 Zotero 移除",
        "source": "zotero",
        "source_key": "zotero:0:MISSING1",
    })
    monkeypatch.setattr(
        desktop_modules.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response([], {"Total-Results": "0"}),
    )

    result = service.zotero_sync()

    assert result["missing"] == 1
    assert service.get_literature({"id": existing["id"]})["source_missing"] is True


def test_zotero_item_with_empty_title_is_seen_but_does_not_overwrite_cache(app, monkeypatch):
    service = desktop_service(app)
    existing = service.save_literature({
        "title": "保留的缓存标题",
        "source": "zotero",
        "source_key": "zotero:0:EMPTYTITLE",
    })
    monkeypatch.setattr(
        desktop_modules.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response(
            [zotero_item("EMPTYTITLE", title="")],
            {"Total-Results": "1"},
        ),
    )

    result = service.zotero_sync()
    detail = service.get_literature({"id": existing["id"]})

    assert result["missing"] == 0
    assert detail["source_missing"] is False
    assert detail["title"] == "保留的缓存标题"


def test_zotero_sync_distinguishes_disabled_local_api(app, monkeypatch):
    service = desktop_service(app)

    def urlopen(request, **_kwargs):
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, None)

    monkeypatch.setattr(desktop_modules.urllib.request, "urlopen", urlopen)
    result = service.zotero_sync()
    status = service.zotero_status()

    assert result["state"] == "unavailable"
    assert "未启用" in result["error"]
    assert status["last_error_code"] == "zotero_api_disabled"


def test_zotero_sync_uses_incremental_version_and_mirrors_attachments(app, monkeypatch):
    service = desktop_service(app)
    calls = []
    parent = zotero_item("PARENT01", title="带附件文献", version=10)
    attachment = {
        "key": "ATTACH01",
        "version": 11,
        "data": {
            "key": "ATTACH01",
            "itemType": "attachment",
            "parentItem": "PARENT01",
            "title": "全文 PDF",
            "filename": "paper.pdf",
            "contentType": "application/pdf",
        },
    }

    def urlopen(request, **_kwargs):
        calls.append(request.full_url)
        if "since=" in request.full_url:
            return Response([attachment], {
                "Total-Results": "1",
                "Zotero-Server-ID": "desktop-a",
                "Last-Modified-Version": "11",
            })
        return Response([parent], {
            "Total-Results": "1",
            "Zotero-Server-ID": "desktop-a",
            "Last-Modified-Version": "10",
        })

    monkeypatch.setattr(desktop_modules.urllib.request, "urlopen", urlopen)
    first = service.zotero_sync()
    second = service.zotero_sync()

    assert first["library_version"] == 10
    assert second["incremental"] is True
    assert second["attachments"] == 1
    assert any("since=10" in url for url in calls)
    with app.app_context():
        literature = LiteratureItem.query.filter_by(source_key="zotero:0:PARENT01").one()
        attachment_item = LibraryItem.query.filter_by(source_key="zotero:0:ATTACH01").one()
        assert attachment_item.storage_mode == "zotero"
        assert attachment_item.mime_type == "application/pdf"
        assert db.session.execute(
            db.select(literature_library_item).where(
                literature_library_item.c.literature_id == literature.id,
                literature_library_item.c.library_item_id == attachment_item.id,
            )
        ).first()


def test_zotero_server_change_forces_full_sync_without_losing_local_fields(app, monkeypatch):
    service = desktop_service(app)
    responses = iter([
        Response([zotero_item("KEEP01", title="初始标题")], {
            "Total-Results": "1",
            "Zotero-Server-ID": "desktop-a",
            "Last-Modified-Version": "5",
        }),
        Response([], {
            "Total-Results": "0",
            "Zotero-Server-ID": "desktop-b",
            "Last-Modified-Version": "1",
        }),
        Response([zotero_item("KEEP01", title="切换后的标题")], {
            "Total-Results": "1",
            "Zotero-Server-ID": "desktop-b",
            "Last-Modified-Version": "2",
        }),
    ])
    monkeypatch.setattr(
        desktop_modules.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: next(responses),
    )
    first = service.zotero_sync()
    item = service.list_literature()[0]
    service.save_literature({**service.get_literature({"id": item["id"]}), "reading_notes": "本地笔记"})

    second = service.zotero_sync()

    assert first["library_version"] == 5
    assert second["server_changed"] is True
    assert second["incremental"] is False
    detail = service.get_literature({"id": item["id"]})
    assert detail["title"] == "切换后的标题"
    assert detail["reading_notes"] == "本地笔记"


def test_cancelled_zotero_sync_does_not_mark_unseen_items_missing(app, monkeypatch):
    service = desktop_service(app)
    existing = service.save_literature({
        "title": "Keep local state", "source": "zotero", "source_key": "zotero:0:KEEP01",
    })
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(
        desktop_modules.urllib.request, "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cancel should stop before HTTP")),
    )

    result = service.zotero_sync({"force_full": True, "_cancel_event": cancel})

    assert result["cancelled"] is True
    assert service.get_literature({"id": existing["id"]})["source_missing"] is False


def test_literature_detail_returns_clickable_relation_metadata(app):
    service = desktop_service(app)
    project = service.create_project({"title": "文献关系项目"})
    record = service.create_record({
        "project_id": project["id"],
        "title": "引用文献的实验",
        "experiment_date": "2026-08-12",
    })
    literature = service.save_literature({"title": "关系文献"})
    service.link_literature({
        "literature_id": literature["id"],
        "project_id": project["id"],
        "record_id": record["id"],
    })

    detail = service.get_literature({"id": literature["id"]})

    assert detail["projects"] == [{"id": project["id"], "title": "文献关系项目"}]
    assert detail["records"] == [{
        "id": record["id"],
        "title": "引用文献的实验",
        "project_id": project["id"],
        "project_title": "文献关系项目",
        "experiment_date": "2026-08-12",
    }]


def test_zotero_collections_are_mirrored_and_filter_literature(app, monkeypatch):
    service = desktop_service(app)
    paper = zotero_item("PAPER01", title="Collection paper")
    paper["data"]["collections"] = ["COLL01"]
    monkeypatch.setattr(
        desktop_modules.urllib.request, "urlopen",
        lambda *_args, **_kwargs: Response([paper], {
            "Total-Results": "1", "Zotero-Server-ID": "desktop-a", "Last-Modified-Version": "1",
        }),
    )
    service.zotero_sync()

    def collection_urlopen(request, **_kwargs):
        assert "/collections?" in request.full_url
        return Response([{
            "key": "COLL01", "version": 2,
            "data": {"key": "COLL01", "name": "Methods", "parentCollection": False},
        }], {"Total-Results": "1", "Last-Modified-Version": "2"})

    monkeypatch.setattr(desktop_modules.urllib.request, "urlopen", collection_urlopen)
    result = service.zotero_collections_sync()
    collection = service.zotero_collections()[0]
    filtered = service.list_literature({"collection_id": collection["id"]})

    assert result == {"collections": 1, "memberships": 1}
    assert collection["name"] == "Methods"
    assert [item["title"] for item in filtered] == ["Collection paper"]
    with app.app_context():
        assert ZoteroCollection.query.one().source_missing is False


def test_literature_save_detects_stale_version(app):
    service = desktop_service(app)
    literature = service.save_literature({"title": "Versioned paper"})
    updated = service.save_literature({**literature, "title": "Current title"})

    from app.services.errors import ConflictError
    try:
        service.save_literature({**literature, "title": "Stale title"})
    except ConflictError:
        pass
    else:  # pragma: no cover
        raise AssertionError("A stale literature write was accepted")
    assert updated["row_version"] == literature["row_version"] + 1


def test_switching_zotero_library_forces_full_sync_and_resets_cursor(app, monkeypatch):
    service = desktop_service(app)
    urls = []
    responses = iter([
        Response([zotero_item("PERSON01")], {
            "Total-Results": "1", "Zotero-Server-ID": "desktop-a", "Last-Modified-Version": "100",
        }),
        Response([zotero_item("GROUP01")], {
            "Total-Results": "1", "Zotero-Server-ID": "desktop-a", "Last-Modified-Version": "20",
        }),
    ])

    def urlopen(request, **_kwargs):
        urls.append(request.full_url)
        return next(responses)

    monkeypatch.setattr(desktop_modules.urllib.request, "urlopen", urlopen)
    service.zotero_sync({"library_key": "personal"})
    result = service.zotero_sync({"library_key": "group:42"})

    assert result["incremental"] is False
    assert result["library_version"] == 20
    assert "/api/groups/42/items?" in urls[-1]
    assert "since=" not in urls[-1]
    assert {item["source_key"] for item in service.list_literature({})} == {
        "zotero:0:PERSON01", "zotero:groups:42:GROUP01",
    }


def test_malformed_full_zotero_response_rolls_back_missing_reconciliation(app, monkeypatch):
    service = desktop_service(app)
    existing = service.save_literature({
        "title": "Keep me", "source": "zotero", "source_key": "zotero:0:KEEP01",
    })
    monkeypatch.setattr(
        desktop_modules.urllib.request, "urlopen",
        lambda *_args, **_kwargs: Response([{"unexpected": True}], {
            "Total-Results": "1", "Zotero-Server-ID": "desktop-a", "Last-Modified-Version": "3",
        }),
    )

    result = service.zotero_sync({"force_full": True})

    assert result["state"] == "error"
    assert result["added"] == 0
    assert service.get_literature({"id": existing["id"]})["source_missing"] is False
