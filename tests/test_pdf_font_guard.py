"""PDF export must never silently fall back to a font without CJK glyphs.

Helvetica renders every Chinese character as blank, so a silent fallback produces a
PDF that looks fine in a file listing and is empty when opened. These tests pin the
loud-failure behaviour and the packaging that prevents the failure in the first place.
"""

import os
from pathlib import Path
from unittest import mock

import pytest

from app import export_service


@pytest.fixture()
def no_system_fonts():
    """Simulate a clean container: no bundled font, no configured font."""
    from reportlab.pdfbase import pdfmetrics

    registered = pdfmetrics.getFont("ResearchAssistantCJK") if (
        "ResearchAssistantCJK" in pdfmetrics.getRegisteredFontNames()
    ) else None
    pdfmetrics._fonts.pop("ResearchAssistantCJK", None)
    with mock.patch.object(export_service, "PDF_FONT_CANDIDATES", ()), \
            mock.patch.dict(os.environ, {"RESEARCH_ASSISTANT_PDF_FONT": ""}):
        yield
    if registered is not None:
        pdfmetrics._fonts["ResearchAssistantCJK"] = registered


def test_missing_cjk_font_raises_instead_of_returning_helvetica(no_system_fonts):
    assert export_service.find_pdf_font_path() is None
    with pytest.raises(export_service.PdfFontMissingError) as excinfo:
        export_service._pdf_font_name()
    message = str(excinfo.value)
    assert "fonts-noto-cjk" in message, "错误信息应给出可执行的安装命令"
    assert "RESEARCH_ASSISTANT_PDF_FONT" in message, "错误信息应说明如何指定字体"
    assert "Word" in message, "错误信息应说明 Word 导出不受影响"


def test_configured_font_path_wins_over_system_candidates(tmp_path):
    configured = tmp_path / "custom-font.ttf"
    configured.write_bytes(b"not-a-real-font")
    with mock.patch.dict(os.environ, {"RESEARCH_ASSISTANT_PDF_FONT": str(configured)}):
        assert export_service.find_pdf_font_path() == str(configured)


def test_unusable_configured_font_is_reported_with_its_path(tmp_path, no_system_fonts):
    broken = tmp_path / "broken.ttf"
    broken.write_bytes(b"not-a-real-font")
    with mock.patch.dict(os.environ, {"RESEARCH_ASSISTANT_PDF_FONT": str(broken)}):
        with pytest.raises(export_service.PdfFontMissingError) as excinfo:
            export_service._pdf_font_name()
    assert "broken.ttf" in str(excinfo.value), "无法加载的字体应在错误里点名"


def test_pdf_export_reports_missing_font_without_a_server_error(client, auth, app, no_system_fonts):
    from datetime import date

    from app import db
    from app.models import Experiment, ExperimentBatch, ExperimentRecord

    auth.register()
    with app.app_context():
        from app.models import User

        user = User.query.first()
        experiment = Experiment(user_id=user.id, title="字体缺失导出", code="EXP-FONT-01")
        db.session.add(experiment)
        db.session.commit()
        batch = ExperimentBatch(experiment_id=experiment.id, batch_code="BATCH-FONT")
        db.session.add(batch)
        db.session.commit()
        record = ExperimentRecord(
            experiment_id=experiment.id, batch_id=batch.id, record_date=date.today(),
            content="过程内容", result="成功",
        )
        db.session.add(record)
        db.session.commit()
        experiment_id, record_id = experiment.id, record.id

    experiment_pdf = client.get(f"/experiments/{experiment_id}/export?format=pdf")
    assert experiment_pdf.status_code == 302, "缺字体时应重定向并提示，而不是 500"

    record_pdf = client.get(f"/records/{record_id}/export?format=pdf")
    assert record_pdf.status_code == 302

    page = client.get(f"/experiments/{experiment_id}", follow_redirects=True)
    assert "fonts-noto-cjk" in page.get_data(as_text=True)

    word = client.get(f"/experiments/{experiment_id}/export?format=docx")
    assert word.status_code == 200, "Word 导出不依赖 CJK 字体，必须仍然可用"


def test_healthz_reports_pdf_font_availability(client):
    payload = client.get("/healthz").get_json()
    assert payload["pdf_export"] in {"ok", "font-missing"}


def test_container_and_package_declare_a_cjk_font():
    """The runtime images must ship a CJK font, or every PDF export is blank."""
    root = Path(__file__).resolve().parent.parent
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    assert "fonts-noto-cjk" in dockerfile, "Dockerfile 必须安装 CJK 字体"

    control = (root / "packaging" / "linux" / "control").read_text(encoding="utf-8")
    assert "fonts-noto-cjk" in control, "deb 包必须声明 CJK 字体依赖"
