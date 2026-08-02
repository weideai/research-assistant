import base64
import io
import zipfile

from app.models import Experiment, ExperimentAttachment, ExperimentBatch, ExperimentRecord


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _setup_experiment(client, auth, app):
    auth.register()
    client.post("/experiments", data={
        "title": "药物处理实验",
        "code": "EXP-REPORT-01",
        "owner": "研究员",
        "status": "进行中",
        "start_date": "2026-07-01",
        "objective": "验证处理后的表达变化。",
    })
    with app.app_context():
        experiment = Experiment.query.one()
        experiment_id = experiment.id
    client.post(f"/experiments/{experiment_id}/batches", data={
        "batch_code": "RUN-01",
        "repeat_kind": "独立实验",
        "repeat_number": "1",
        "operator": "研究员",
        "start_date": "2026-07-01",
    })
    with app.app_context():
        batch = ExperimentBatch.query.filter_by(experiment_id=experiment_id).one()
        return experiment_id, batch.id


def _add_record(client, experiment_id, batch_id, record_date, content, result):
    response = client.post(f"/experiments/{experiment_id}/records", data={
        "batch_id": str(batch_id),
        "record_date": record_date,
        "operator": "研究员",
        "conditions": "37°C，5% CO2",
        "content": content,
        "result": result,
        "remark": "需要复核原始数据。",
    })
    assert response.status_code == 302


def test_report_reader_supports_search_pagination_and_single_record_exports(client, auth, app):
    experiment_id, batch_id = _setup_experiment(client, auth, app)
    _add_record(client, experiment_id, batch_id, "2026-07-02", "first observation", "待确认")
    _add_record(client, experiment_id, batch_id, "2026-07-03", "second observation", "成功")

    with app.app_context():
        records = ExperimentRecord.query.order_by(ExperimentRecord.record_date).all()
        first_id, second_id = records[0].id, records[1].id

    page = client.get(f"/experiments/{experiment_id}/reports?record_id={first_id}")
    assert page.status_code == 200
    page_body = page.get_data(as_text=True)
    assert "实验报告" in page_body
    assert "导出 PDF" in page_body
    assert "导出 Word" in page_body
    assert "导入 Word" not in page_body
    assert f"record_id={second_id}" in page_body

    search = client.get(f"/experiments/{experiment_id}/reports?q=second")
    assert search.status_code == 200
    body = search.get_data(as_text=True)
    assert "second observation" in body
    assert "first observation" not in body

    pdf = client.get(f"/records/{second_id}/export?format=pdf")
    assert pdf.status_code == 200
    assert pdf.mimetype == "application/pdf"
    assert pdf.data.startswith(b"%PDF")

    word = client.get(f"/records/{second_id}/export?format=docx")
    assert word.status_code == 200
    assert word.mimetype == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    with zipfile.ZipFile(io.BytesIO(word.data)) as archive:
        assert "word/document.xml" in archive.namelist()


def test_report_reader_summarizes_attachments_with_two_thumbnails_and_folder_link(
    client, auth, app, monkeypatch,
):
    experiment_id, batch_id = _setup_experiment(client, auth, app)
    _add_record(client, experiment_id, batch_id, "2026-07-02", "attachment summary", "成功")
    with app.app_context():
        record_id = ExperimentRecord.query.one().id

    attachment_names = ("figure-1.png", "figure-2.png", "figure-3.png", "raw-data.bin")
    response = client.post(
        f"/records/{record_id}/attachments",
        data={"files": [
            (io.BytesIO(ONE_PIXEL_PNG), "figure-1.png"),
            (io.BytesIO(ONE_PIXEL_PNG), "figure-2.png"),
            (io.BytesIO(ONE_PIXEL_PNG), "figure-3.png"),
            (io.BytesIO(b"raw-binary"), "raw-data.bin"),
        ]},
        content_type="multipart/form-data",
    )
    assert response.status_code == 302

    with app.app_context():
        attachments = ExperimentAttachment.query.order_by(ExperimentAttachment.id).all()
        assert len(attachments) == 4

    page = client.get(f"/experiments/{experiment_id}/reports?record_id={record_id}")
    body = page.get_data(as_text=True)
    assert page.status_code == 200
    assert body.count('class="report-attachment-thumb"') == 2
    assert sum(name in body for name in attachment_names[:3]) == 2
    assert "raw-data.bin" not in body
    assert f"/experiments/{experiment_id}/files?record_id={record_id}" in body
    assert "打开完整文件夹" in body

    folder = client.get(f"/experiments/{experiment_id}/files?record_id={record_id}")
    folder_body = folder.get_data(as_text=True)
    assert folder.status_code == 200
    assert all(name in folder_body for name in attachment_names)

    word = client.get(f"/records/{record_id}/export?format=docx")
    assert word.status_code == 200
    with zipfile.ZipFile(io.BytesIO(word.data)) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        preview_files = [name for name in archive.namelist() if name.startswith("word/media/")]
        word_markup = {
            name: archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if name.endswith((".xml", ".rels"))
        }
    assert document_xml.count("<w:drawing>") == 2
    assert len(preview_files) <= 2
    assert 'w:fill="2166F3"' in document_xml
    assert 'w:val="FFFFFF"' in document_xml
    assert 'w:val="74838A"' not in document_xml
    word_name_leaks = [
        (attachment_name, part_name)
        for attachment_name in attachment_names
        for part_name, markup in word_markup.items()
        if attachment_name in markup
    ]
    assert not word_name_leaks
    assert f"record-{record_id}" in document_xml
    assert "共 4 个文件" in document_xml

    full_word = client.get(f"/experiments/{experiment_id}/export?format=docx")
    assert full_word.status_code == 200
    with zipfile.ZipFile(io.BytesIO(full_word.data)) as archive:
        full_word_markup = {
            name: archive.read(name).decode("utf-8", errors="ignore")
            for name in archive.namelist()
            if name.endswith((".xml", ".rels"))
        }
    full_word_name_leaks = [
        (attachment_name, part_name)
        for attachment_name in attachment_names
        for part_name, markup in full_word_markup.items()
        if attachment_name in markup
    ]
    assert not full_word_name_leaks
    assert any(f"record-{record_id}" in markup for markup in full_word_markup.values())

    from reportlab import platypus

    rendered_pdf_text = []
    paragraph_class = platypus.Paragraph

    class TrackingParagraph(paragraph_class):
        def __init__(self, text, *args, **kwargs):
            rendered_pdf_text.append(str(text))
            super().__init__(text, *args, **kwargs)

    monkeypatch.setattr(platypus, "Paragraph", TrackingParagraph)
    pdf = client.get(f"/records/{record_id}/export?format=pdf")
    assert pdf.status_code == 200
    assert pdf.data.startswith(b"%PDF")
    assert pdf.data.count(b"/Subtype /Image") == 2
    assert all(name.encode() not in pdf.data for name in attachment_names)
    assert all(name not in "\n".join(rendered_pdf_text) for name in attachment_names)
    assert f"record-{record_id}" in "\n".join(rendered_pdf_text)

    rendered_pdf_text.clear()
    full_pdf = client.get(f"/experiments/{experiment_id}/export?format=pdf")
    assert full_pdf.status_code == 200
    assert full_pdf.data.startswith(b"%PDF")
    assert full_pdf.data.count(b"/Subtype /Image") == 2
    assert all(name.encode() not in full_pdf.data for name in attachment_names)
    assert all(name not in "\n".join(rendered_pdf_text) for name in attachment_names)
    assert f"record-{record_id}" in "\n".join(rendered_pdf_text)
