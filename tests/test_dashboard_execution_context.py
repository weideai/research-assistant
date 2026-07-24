from datetime import date

from app import db
from app.models import Experiment, ExperimentBatch, ExperimentRecord


def test_recent_process_record_shows_its_execution(client, auth, app):
    auth.register()
    client.post("/experiments", data={"title": "重复实验计划"})

    with app.app_context():
        experiment = Experiment.query.filter_by(title="重复实验计划").one()
        batch = ExperimentBatch(
            experiment_id=experiment.id,
            batch_code="RUN-DASHBOARD",
            status="进行中",
            start_date=date.today(),
        )
        db.session.add(batch)
        db.session.flush()
        db.session.add(ExperimentRecord(
            experiment_id=experiment.id,
            batch_id=batch.id,
            record_date=date.today(),
            content="本次执行的过程记录",
        ))
        db.session.commit()
        batch_id = batch.id

    page = client.get("/").get_data(as_text=True)
    assert "实验执行" in page
    assert "RUN-DASHBOARD" in page
    assert f'href="/batches/{batch_id}"' in page

