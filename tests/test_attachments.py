import base64
import io
from pathlib import Path

from app import db
from app.models import Experiment, ExperimentAttachment, ExperimentRecord


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def create_record(client, app):
    client.post("/experiments", data={"title": "附件实验", "code": "EXP-FILE-001", "status": "进行中"})
    with app.app_context():
        experiment_id = Experiment.query.one().id
    client.post(f"/experiments/{experiment_id}/records", data={
        "record_date": "2026-07-21", "operator": "研究员", "content": "完成数据采集。",
        "result": "成功",
    })
    with app.app_context():
        return experiment_id, ExperimentRecord.query.one().id


def test_folder_files_are_classified_stored_and_downloadable(client, auth, app):
    auth.register()
    experiment_id, record_id = create_record(client, app)
    response = client.post(f"/records/{record_id}/attachments", data={
        "files": [
            (io.BytesIO(ONE_PIXEL_PNG), "microscopy/day1/cells.png"),
            (io.BytesIO(b"sample,value\nA,1\n"), "analysis/results.csv"),
            (io.BytesIO(b"arbitrary-binary-data"), "raw/sample.ab1"),
        ]
    }, content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200
    assert "已导入 3 个".encode() in response.data
    assert "microscopy/day1/cells.png".encode() in response.data

    with app.app_context():
        attachments = ExperimentAttachment.query.order_by(ExperimentAttachment.id).all()
        assert {item.category for item in attachments} == {"图片", "数据", "其他"}
        assert all(f"experiment-{experiment_id}/2026-07-21/record-{record_id}" in item.stored_path for item in attachments)
        assert all((Path(app.config["ATTACHMENT_UPLOAD_DIR"]) / item.stored_path).is_file() for item in attachments)
        image_id = next(item.id for item in attachments if item.category == "图片")
        data_id = next(item.id for item in attachments if item.category == "数据")

    preview = client.get(f"/attachments/{image_id}/preview")
    assert preview.status_code == 200
    assert preview.mimetype == "image/png"
    preview.close()
    assert client.get(f"/attachments/{data_id}/preview").status_code == 404
    download = client.get(f"/attachments/{data_id}/download")
    assert download.status_code == 200
    assert "attachment" in download.headers["Content-Disposition"]
    assert download.data == b"sample,value\nA,1\n"
    download.close()

    client.post(f"/records/{record_id}", data={
        "record_date": "2026-07-22", "operator": "研究员", "content": "完成数据采集。",
        "result": "成功", "conditions": "", "remark": "",
    })
    with app.app_context():
        moved = ExperimentAttachment.query.all()
        assert all("/2026-07-22/" in item.stored_path for item in moved)
        assert all((Path(app.config["ATTACHMENT_UPLOAD_DIR"]) / item.stored_path).is_file() for item in moved)


def test_files_can_be_categorized_when_record_is_created(client, auth, app):
    auth.register()
    client.post("/experiments", data={"title": "创建时上传", "status": "进行中"})
    with app.app_context():
        experiment_id = Experiment.query.one().id

    response = client.post(f"/experiments/{experiment_id}/records", data={
        "record_date": "2026-07-21",
        "operator": "研究员",
        "content": "完成原始数据采集。",
        "result": "待确认",
        "attachment_category": "原始数据",
        "files": [
            (io.BytesIO(b"raw-value-1"), "plate-reader/run-01.raw"),
            (io.BytesIO(b"raw-value-2"), "plate-reader/run-02.raw"),
        ],
    }, content_type="multipart/form-data", follow_redirects=True)

    assert response.status_code == 200
    assert "已同时导入 2 个文件".encode() in response.data
    assert "原始数据".encode() in response.data
    assert "plate-reader/run-01.raw".encode() in response.data
    with app.app_context():
        record = ExperimentRecord.query.one()
        attachments = ExperimentAttachment.query.order_by(ExperimentAttachment.id).all()
        assert len(attachments) == 2
        assert {item.category for item in attachments} == {"原始数据"}
        assert all(item.record_id == record.id for item in attachments)


def test_attachments_are_private_and_deleted_with_record(client, auth, app):
    auth.register(email="file-owner@example.com")
    _experiment_id, record_id = create_record(client, app)
    client.post(f"/records/{record_id}/attachments", data={
        "files": (io.BytesIO(b"private-data"), "private.xyz")
    }, content_type="multipart/form-data")
    with app.app_context():
        attachment = ExperimentAttachment.query.one()
        attachment_id = attachment.id
        stored_file = Path(app.config["ATTACHMENT_UPLOAD_DIR"]) / attachment.stored_path
        assert stored_file.is_file()

    auth.logout()
    auth.register(email="other-file-user@example.com")
    assert client.get(f"/attachments/{attachment_id}/download").status_code == 404
    assert client.post(f"/attachments/{attachment_id}/delete").status_code == 404

    auth.logout()
    auth.login(email="file-owner@example.com")
    client.post(f"/records/{record_id}/delete")
    assert not stored_file.exists()
    with app.app_context():
        assert ExperimentAttachment.query.count() == 0


def test_unsafe_paths_and_oversized_files_are_rejected(client, auth, app):
    auth.register()
    _experiment_id, record_id = create_record(client, app)
    response = client.post(f"/records/{record_id}/attachments", data={
        "files": (io.BytesIO(b"bad"), "../outside.txt")
    }, content_type="multipart/form-data", follow_redirects=True)
    assert "上级目录".encode() in response.data

    app.config["MAX_ATTACHMENT_BYTES"] = 4
    response = client.post(f"/records/{record_id}/attachments", data={
        "files": (io.BytesIO(b"12345"), "too-large.bin")
    }, content_type="multipart/form-data", follow_redirects=True)
    assert "超过大小限制".encode() in response.data
    with app.app_context():
        assert ExperimentAttachment.query.count() == 0
