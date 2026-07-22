import io
import json
import zipfile

from app import db
from app.models import Experiment, ExperimentAttachment, ExperimentParameter, ExperimentRecord, RecordParameter


def _create_complete_experiment(client, auth, app):
    auth.register()
    client.post("/experiments", data={
        "title": "药物处理后 WB 验证",
        "code": "EXP-EXPORT-01",
        "batch_code": "BATCH-A",
        "repeat_kind": "生物学重复",
        "repeat_number": "2",
        "group_name": "对照组 / 处理组",
        "owner": "研究员",
        "status": "进行中",
        "start_date": "2026-07-20",
        "end_date": "2026-07-22",
        "objective": "验证目标蛋白表达变化。",
    })
    with app.app_context():
        experiment = Experiment.query.one()
        experiment_id = experiment.id
        db.session.add(ExperimentParameter(
            experiment_id=experiment_id, position=1, name="药物浓度", value="5", unit="μM", notes="终浓度",
        ))
        db.session.commit()
    client.post(f"/experiments/{experiment_id}/steps", data={
        "title": "药物处理", "operator": "研究员", "planned_date": "2026-07-20", "description": "处理 24h",
    })
    client.post(f"/experiments/{experiment_id}/records", data={
        "record_date": "2026-07-21",
        "operator": "研究员",
        "conditions": "37°C，5% CO2",
        "content": "完成处理并采集原始数据。",
        "result": "成功",
        "remark": "建议增加一次独立重复。",
        "record_parameter_name": ["曝光时间"],
        "record_parameter_value": ["30"],
        "record_parameter_unit": ["s"],
        "record_parameter_notes": ["未饱和"],
        "attachment_category": "原始数据",
        "files": (io.BytesIO(b"sample,value\nA,1\n"), "raw/result.csv"),
    }, content_type="multipart/form-data")
    with app.app_context():
        assert ExperimentAttachment.query.count() == 1
        assert RecordParameter.query.count() == 1
    return experiment_id


def test_experiment_export_picker_lists_supported_formats(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    response = client.get(f"/experiments/{experiment_id}")
    assert response.status_code == 200
    for label in ("Markdown 报告", "Word 文档", "Excel 工作簿", "JSON 结构化数据", "ZIP 完整归档"):
        assert label.encode() in response.data


def test_experiment_json_export_contains_complete_structure(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    response = client.get(f"/experiments/{experiment_id}/export?format=json")
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    payload = json.loads(response.data)
    assert payload["schema_version"] == 1
    assert payload["experiment"]["code"] == "EXP-EXPORT-01"
    assert payload["plan_parameters"][0]["name"] == "药物浓度"
    assert payload["steps"][0]["title"] == "药物处理"
    assert payload["records"][0]["parameters"][0]["name"] == "曝光时间"
    assert payload["records"][0]["attachments"][0]["relative_path"] == "raw/result.csv"


def test_markdown_export_has_readable_sections_tables_and_review_notice(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    response = client.get(f"/experiments/{experiment_id}/export?format=markdown")
    assert response.status_code == 200
    report = response.data.decode("utf-8-sig")
    assert "## 目录" in report
    assert "## 实验概览" in report
    assert "| 字段 | 内容 |" in report
    assert "| 分类 | 文件夹 / 文件 | 版本 | 大小 | SHA-256 | 标签 | 说明 |" in report
    assert "人工核验" in report


def test_experiment_word_and_excel_exports_are_valid_office_files(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)

    word = client.get(f"/experiments/{experiment_id}/export?format=docx")
    assert word.status_code == 200
    assert word.mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    with zipfile.ZipFile(io.BytesIO(word.data)) as document:
        assert "word/document.xml" in document.namelist()
        assert "EXP-EXPORT-01".encode("utf-8") in document.read("word/document.xml")

    excel = client.get(f"/experiments/{experiment_id}/export?format=xlsx")
    assert excel.status_code == 200
    assert excel.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    with zipfile.ZipFile(io.BytesIO(excel.data)) as workbook:
        names = workbook.namelist()
        assert "xl/workbook.xml" in names
        assert len([name for name in names if name.startswith("xl/worksheets/sheet")]) == 7


def test_unified_zip_export_contains_report_json_manifest_and_files(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    response = client.get(f"/experiments/{experiment_id}/export?format=zip")
    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
        names = archive.namelist()
        assert "report.md" in names
        assert "experiment.json" in names
        assert "file-manifest.csv" in names
        assert any(name.endswith("raw/result.csv") for name in names)


def test_experiment_export_rejects_unknown_format_and_other_users(client, auth, app):
    experiment_id = _create_complete_experiment(client, auth, app)
    assert client.get(f"/experiments/{experiment_id}/export?format=pdf").status_code == 400

    auth.logout()
    auth.register(email="other@example.com")
    for export_format in ("markdown", "json", "docx", "xlsx", "zip"):
        assert client.get(f"/experiments/{experiment_id}/export?format={export_format}").status_code == 404
