import io
import json
import zipfile
from datetime import date

from openpyxl import load_workbook

from app import db
from app.models import (
    Experiment,
    ExperimentAttachment,
    ExperimentBatch,
    ExperimentParameter,
    ExperimentRecord,
    RecordParameter,
)


ACTIVE_ATTACHMENT = "raw/result-a.csv"
DELETED_ATTACHMENT = "discarded/deleted-attachment.txt"
DELETED_RECORD_ATTACHMENT = "discarded/deleted-record.csv"
DELETED_RECORD_CONTENT = "SOFT-DELETED-RECORD"
UNASSIGNED_RECORD_CONTENT = "ORPHAN-LEGACY-RECORD"


def _post_record(client, experiment_id, batch_id, *, record_date, content, result, filename, file_data):
    response = client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": str(batch_id),
        "record_date": record_date,
        "operator": "研究员",
        "conditions": "37°C，5% CO2",
        "content": content,
        "result": result,
        "remark": "建议增加一次独立重复。",
        "record_parameter_name": ["曝光时间"],
        "record_parameter_value": ["30"],
        "record_parameter_unit": ["s"],
        "record_parameter_notes": ["未饱和"],
        "attachment_category": "原始数据",
        "files": (io.BytesIO(file_data), filename),
    }, content_type="multipart/form-data")
    assert response.status_code == 302


def _create_complete_experiment(client, auth, app):
    auth.register()
    client.post("/experiments", data={
        "title": "药物处理后 WB 验证",
        "code": "EXP-EXPORT-01",
        "owner": "研究员",
        "status": "进行中",
        "start_date": "2026-07-20",
        "end_date": "2026-07-24",
        "objective": "验证目标蛋白表达变化。",
    })
    with app.app_context():
        experiment = Experiment.query.one()
        experiment_id = experiment.id
        db.session.add(ExperimentParameter(
            experiment_id=experiment_id,
            position=1,
            name="药物浓度",
            value="5",
            unit="μM",
            notes="终浓度",
        ))
        db.session.commit()

    for batch_data in (
        {
            "batch_code": "BATCH-A",
            "repeat_kind": "生物学重复",
            "repeat_number": "1",
            "group_name": "对照组",
            "operator": "研究员 A",
            "start_date": "2026-07-20",
        },
        {
            "batch_code": "BATCH-B",
            "repeat_kind": "生物学重复",
            "repeat_number": "2",
            "group_name": "处理组",
            "operator": "研究员 B",
            "start_date": "2026-07-22",
        },
    ):
        response = client.post(f"/experiments/{experiment_id}/batches", data=batch_data)
        assert response.status_code == 302

    with app.app_context():
        batch_ids = {
            batch.batch_code: batch.id
            for batch in ExperimentBatch.query.filter_by(experiment_id=experiment_id).all()
        }

    response = client.post(f"/experiments/{experiment_id}/steps", data={
        "title": "药物处理",
        "operator": "研究员",
        "planned_date": "2026-07-20",
        "description": "处理 24h",
    })
    assert response.status_code == 302

    _post_record(
        client,
        experiment_id,
        batch_ids["BATCH-A"],
        record_date="2026-07-21",
        content="完成第一批处理并采集原始数据。",
        result="BATCH-A-RESULT",
        filename=ACTIVE_ATTACHMENT,
        file_data=b"sample,value\nA,1\n",
    )
    _post_record(
        client,
        experiment_id,
        batch_ids["BATCH-B"],
        record_date="2026-07-23",
        content="完成第二批处理并采集图像。",
        result="BATCH-B-RESULT",
        filename="images/result-b.png",
        file_data=b"not-a-preview-but-valid-test-data",
    )
    _post_record(
        client,
        experiment_id,
        batch_ids["BATCH-B"],
        record_date="2026-07-24",
        content=DELETED_RECORD_CONTENT,
        result="DELETED-RESULT",
        filename=DELETED_RECORD_ATTACHMENT,
        file_data=b"deleted,record\n",
    )

    with app.app_context():
        first_record = ExperimentRecord.query.filter_by(result="BATCH-A-RESULT").one()
        first_record_id = first_record.id
    response = client.post(f"/records/{first_record_id}/attachments", data={
        "attachment_category": "实验文档",
        "attachment_folder": "discarded",
        "files": (io.BytesIO(b"deleted attachment"), "deleted-attachment.txt"),
    }, content_type="multipart/form-data")
    assert response.status_code == 302

    with app.app_context():
        deleted_record = ExperimentRecord.query.filter_by(content=DELETED_RECORD_CONTENT).one()
        deleted_record.is_deleted = True
        deleted_attachment = ExperimentAttachment.query.filter_by(
            record_id=first_record_id,
            relative_path=DELETED_ATTACHMENT,
        ).one()
        deleted_attachment.is_deleted = True
        experiment = db.session.get(Experiment, experiment_id)
        wrong_experiment = Experiment(
            user_id=experiment.user_id,
            project_id=experiment.project_id,
            title="错误执行归属",
        )
        db.session.add(wrong_experiment)
        db.session.flush()
        wrong_batch = ExperimentBatch(
            experiment_id=wrong_experiment.id,
            batch_code="WRONG-OWNER",
        )
        db.session.add(wrong_batch)
        db.session.flush()
        db.session.add(ExperimentRecord(
            experiment_id=experiment_id,
            batch_id=wrong_batch.id,
            record_date=date(2026, 7, 19),
            operator="历史研究员",
            conditions="旧系统导入",
            content=UNASSIGNED_RECORD_CONTENT,
            result="待归档",
            remark="迁移后应归入历史执行。",
        ))
        db.session.commit()
        assert ExperimentAttachment.query.count() == 4
        assert RecordParameter.query.count() == 3
    return experiment_id


def _docx_xml(data):
    with zipfile.ZipFile(io.BytesIO(data)) as document:
        assert "word/document.xml" in document.namelist()
        return document.read("word/document.xml").decode("utf-8")


def _workbook_rows(data):
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    try:
        return {
            sheet.title: list(sheet.iter_rows(values_only=True))
            for sheet in workbook.worksheets
        }
    finally:
        workbook.close()


def _workbook_text(data):
    rows = _workbook_rows(data)
    return "\n".join(
        str(value)
        for sheet_rows in rows.values()
        for row in sheet_rows
        for value in row
        if value is not None
    )


def test_experiment_export_picker_lists_supported_formats(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    response = client.get(f"/experiments/{experiment_id}")
    assert response.status_code == 200
    for label in ("Markdown 报告", "Word 文档", "Excel 工作簿", "JSON 结构化数据", "ZIP 完整归档"):
        assert label.encode() in response.data


def test_json_export_groups_records_by_execution_and_keeps_flat_compatibility_view(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    response = client.get(f"/experiments/{experiment_id}/export?format=json")
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    payload = json.loads(response.data)

    assert payload["schema_version"] == 3
    assert payload["experiment"]["code"] == "EXP-EXPORT-01"
    assert payload["plan_parameters"][0]["name"] == "药物浓度"
    assert payload["steps"][0]["title"] == "药物处理"

    batches = {batch["batch_code"]: batch for batch in payload["batches"]}
    assert set(batches) == {"BATCH-A", "BATCH-B"}
    assert [record["result"] for record in batches["BATCH-A"]["records"]] == ["BATCH-A-RESULT"]
    assert [record["result"] for record in batches["BATCH-B"]["records"]] == ["BATCH-B-RESULT"]

    flat_records = {record["content"]: record for record in payload["records"]}
    assert flat_records["完成第一批处理并采集原始数据。"]["batch_code"] == "BATCH-A"
    assert flat_records["完成第二批处理并采集图像。"]["batch_code"] == "BATCH-B"
    assert flat_records["完成第一批处理并采集原始数据。"]["parameters"][0]["name"] == "曝光时间"
    assert flat_records["完成第一批处理并采集原始数据。"]["attachments"][0]["relative_path"] == ACTIVE_ATTACHMENT


def test_unassigned_active_record_is_exported_once_in_explicit_history_group(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    payload = client.get(f"/experiments/{experiment_id}/export?format=json").get_json()

    assert len(payload["unassigned_records"]) == 1
    orphan = payload["unassigned_records"][0]
    assert orphan["content"] == UNASSIGNED_RECORD_CONTENT
    assert orphan["batch_id"] is None
    assert orphan["batch_code"] == "HISTORY-UNASSIGNED"
    assert sum(record["id"] == orphan["id"] for record in payload["records"]) == 1
    assert all(
        record["id"] != orphan["id"]
        for batch in payload["batches"]
        for record in batch["records"]
    )


def test_markdown_and_word_exports_show_each_execution_as_a_section(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)

    markdown = client.get(f"/experiments/{experiment_id}/export?format=markdown")
    assert markdown.status_code == 200
    report = markdown.data.decode("utf-8-sig")
    assert "## 目录" in report
    assert "## 实验概览" in report
    assert "| 字段 | 内容 |" in report
    assert "| 分类 | 文件夹 / 文件 | 版本 | 大小 | SHA-256 | 标签 | 说明 |" in report
    assert "BATCH-A" in report
    assert "BATCH-B" in report
    assert "HISTORY-UNASSIGNED" in report
    assert "过程记录" in report
    assert "人工核验" in report

    word = client.get(f"/experiments/{experiment_id}/export?format=docx")
    assert word.status_code == 200
    assert word.mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    document_xml = _docx_xml(word.data)
    assert "EXP-EXPORT-01" in document_xml
    assert "BATCH-A" in document_xml
    assert "BATCH-B" in document_xml
    assert "HISTORY-UNASSIGNED" in document_xml
    assert "过程记录" in document_xml


def test_excel_export_has_execution_sheet_and_execution_code_on_record_rows(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    response = client.get(f"/experiments/{experiment_id}/export?format=xlsx")
    assert response.status_code == 200
    assert response.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    sheets = _workbook_rows(response.data)
    assert "实验执行" in sheets
    assert "过程记录" in sheets
    assert len(sheets) == 9
    assert "执行步骤" in sheets
    assert "执行编号" in sheets["过程记录"][0]
    execution_code_column = sheets["过程记录"][0].index("执行编号")
    execution_codes = {row[execution_code_column] for row in sheets["过程记录"][1:]}
    assert execution_codes == {"BATCH-A", "BATCH-B", "HISTORY-UNASSIGNED"}
    assert {row[1] for row in sheets["实验执行"][1:]} == {
        "BATCH-A",
        "BATCH-B",
        "HISTORY-UNASSIGNED",
    }


def test_soft_deleted_records_and_attachments_are_excluded_from_every_format(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)

    json_response = client.get(f"/experiments/{experiment_id}/export?format=json")
    markdown_response = client.get(f"/experiments/{experiment_id}/export?format=markdown")
    word_response = client.get(f"/experiments/{experiment_id}/export?format=docx")
    excel_response = client.get(f"/experiments/{experiment_id}/export?format=xlsx")
    zip_response = client.get(f"/experiments/{experiment_id}/export?format=zip")
    assert all(response.status_code == 200 for response in (
        json_response,
        markdown_response,
        word_response,
        excel_response,
        zip_response,
    ))

    visible_text = "\n".join((
        json_response.data.decode("utf-8"),
        markdown_response.data.decode("utf-8-sig"),
        _docx_xml(word_response.data),
        _workbook_text(excel_response.data),
    ))
    assert DELETED_RECORD_CONTENT not in visible_text
    assert DELETED_ATTACHMENT not in visible_text
    assert DELETED_RECORD_ATTACHMENT not in visible_text

    with zipfile.ZipFile(io.BytesIO(zip_response.data)) as archive:
        archive_text = "\n".join((
            "\n".join(archive.namelist()),
            archive.read("report.md").decode("utf-8-sig"),
            archive.read("experiment.json").decode("utf-8"),
            archive.read("file-manifest.csv").decode("utf-8-sig"),
        ))
    assert DELETED_RECORD_CONTENT not in archive_text
    assert DELETED_ATTACHMENT not in archive_text
    assert DELETED_RECORD_ATTACHMENT not in archive_text


def test_zip_export_uses_execution_folders_and_shared_schema(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    response = client.get(f"/experiments/{experiment_id}/export?format=zip")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        names = archive.namelist()
        assert "report.md" in names
        assert "experiment.json" in names
        assert "file-manifest.csv" in names
        assert any(name.startswith("files/BATCH-A/") and name.endswith(ACTIVE_ATTACHMENT) for name in names)
        assert any(name.startswith("files/BATCH-B/") and name.endswith("images/result-b.png") for name in names)
        payload = json.loads(archive.read("experiment.json"))
        manifest = archive.read("file-manifest.csv").decode("utf-8-sig")

    assert payload["schema_version"] == 3
    assert {batch["batch_code"] for batch in payload["batches"]} == {"BATCH-A", "BATCH-B"}
    assert "execution_code" in manifest.splitlines()[0]
    assert "BATCH-A" in manifest
    assert "BATCH-B" in manifest
    assert DELETED_ATTACHMENT not in manifest
    assert DELETED_RECORD_ATTACHMENT not in manifest


def test_experiment_export_rejects_unknown_format_and_other_users(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    assert client.get(f"/experiments/{experiment_id}/export?format=pdf").status_code == 400

    auth.logout()
    auth.register(email="other@example.com")
    for export_format in ("markdown", "json", "docx", "xlsx", "zip"):
        assert client.get(f"/experiments/{experiment_id}/export?format={export_format}").status_code == 404
