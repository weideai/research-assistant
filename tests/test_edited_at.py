"""Last-edited times must be visible and consistently formatted.

The data was always there (`TimestampMixin.updated_at`); only one page showed it.
These tests pin both the formatting rule and the pages that surface it.
"""

from datetime import date, datetime, timedelta

import pytest

from app import db
from app.main import RELATIVE_TIME_CUTOFF_DAYS, edited_at_filter, edited_at_title_filter
from app.models import Experiment, ExperimentBatch, ExperimentRecord, User, utcnow


@pytest.mark.parametrize("delta,expected", [
    (timedelta(seconds=5), "刚刚"),
    (timedelta(seconds=59), "刚刚"),
    (timedelta(minutes=1), "1 分钟前"),
    (timedelta(minutes=45), "45 分钟前"),
    (timedelta(hours=1), "1 小时前"),
    (timedelta(hours=23), "23 小时前"),
    (timedelta(days=1), "1 天前"),
    (timedelta(days=6, hours=23), "6 天前"),
])
def test_recent_edits_read_as_relative_time(delta, expected):
    assert edited_at_filter(utcnow() - delta) == expected


@pytest.mark.parametrize("days", [RELATIVE_TIME_CUTOFF_DAYS, RELATIVE_TIME_CUTOFF_DAYS + 1, 400])
def test_older_edits_switch_to_an_absolute_date(days):
    moment = utcnow() - timedelta(days=days)
    assert edited_at_filter(moment) == moment.strftime("%Y-%m-%d")


def test_missing_and_future_timestamps_do_not_raise():
    assert edited_at_filter(None) == "未记录"
    assert edited_at_title_filter(None) == "没有修改记录"
    ahead = utcnow() + timedelta(hours=3)
    assert edited_at_filter(ahead) == ahead.strftime("%Y-%m-%d %H:%M")


def test_plain_dates_are_accepted():
    """Some columns are date, not datetime; the filter must not crash on them."""
    assert edited_at_filter(date(2026, 7, 18)) == "2026-07-18"
    assert edited_at_title_filter(date(2026, 7, 18)) == "2026-07-18"


def test_tooltip_always_carries_the_exact_timestamp():
    """Relative wording is friendly but lossy, so the precise value stays reachable."""
    moment = utcnow() - timedelta(minutes=10)
    assert edited_at_filter(moment) == "10 分钟前"
    assert edited_at_title_filter(moment) == moment.strftime("%Y-%m-%d %H:%M:%S")


def _seed(app):
    with app.app_context():
        user = User.query.first()
        experiment = Experiment(user_id=user.id, title="编辑时间实验", code="EXP-EDIT-01")
        db.session.add(experiment)
        db.session.commit()
        batch = ExperimentBatch(experiment_id=experiment.id, batch_code="BATCH-EDIT")
        db.session.add(batch)
        db.session.commit()
        record = ExperimentRecord(
            experiment_id=experiment.id, batch_id=batch.id, record_date=date.today(),
            content="过程内容", result="成功",
        )
        db.session.add(record)
        db.session.commit()
        return experiment.id, batch.id, record.id


def test_detail_pages_show_a_last_edited_marker(client, auth, app):
    auth.register()
    experiment_id, batch_id, record_id = _seed(app)

    pages = {
        f"/experiments/{experiment_id}": "实验计划详情",
        f"/batches/{batch_id}": "实验批次详情",
        f"/records/{record_id}": "过程记录详情",
    }
    for url, label in pages.items():
        body = client.get(url).get_data(as_text=True)
        assert 'class="edited-at"' in body, f"{label} 缺少最后编辑标记"
        assert "编辑" in body


def test_record_and_sample_lists_show_a_last_edited_marker(client, auth, app):
    """These rows carry the marker as soon as there is one row to show."""
    auth.register()
    _seed(app)
    client.post("/samples", data={
        "sample_code": "S-EDIT-01", "sample_type": "组织", "location": "-80 冰箱",
        "quantity": "5 管", "status": "可用",
    })
    for url, label in (
        ("/experiment-reports", "实验报告卡片流"),
        ("/samples", "物品管理"),
    ):
        body = client.get(url).get_data(as_text=True)
        assert "edited-at" in body, f"{label} 缺少最后编辑标记"


def test_file_centre_shows_a_last_edited_marker_per_attachment(client, auth, app):
    auth.register()
    experiment_id, batch_id, _ = _seed(app)
    import io as _io

    client.post(f"/batches/{batch_id}/records", data={
        "batch_id": str(batch_id), "record_date": str(date.today()),
        "content": "带附件的记录", "result": "成功",
        "attachment_category": "原始数据",
        "files": (_io.BytesIO(b"col-a,col-b\n1,2\n"), "result.csv"),
    }, content_type="multipart/form-data")

    body = client.get("/file-center").get_data(as_text=True)
    assert "result.csv" in body, "附件未出现在文件中心，测试前置条件不成立"
    assert "edited-at" in body, "文件中心缺少最后编辑标记"


def test_edit_advances_the_displayed_timestamp(client, auth, app):
    """A save must move updated_at, otherwise the marker is decoration."""
    auth.register()
    _, _, record_id = _seed(app)
    with app.app_context():
        before = db.session.get(ExperimentRecord, record_id).updated_at

    client.post(f"/records/{record_id}", data={
        "record_date": str(date.today()), "operator": "研究员",
        "conditions": "37C", "content": "修改后的过程内容", "result": "成功",
        "remark": "补充说明",
    })
    with app.app_context():
        after = db.session.get(ExperimentRecord, record_id).updated_at
    assert after >= before
