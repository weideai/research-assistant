import hashlib
import json
import sqlite3
import uuid
import zipfile
from pathlib import Path

import pytest

from app import db
from app.desktop.bridge import DesktopBridge
from app.models import ApiPreset, LabRecord, LabRecordRevision, LibraryItem, User, utcnow
from app.services.desktop_workspace import DesktopApplicationService
from app.services.errors import ConflictError, ValidationError


def record_fixture(app):
    service = DesktopApplicationService(app)
    project = service.create_project({'title': 'Synthetic project'})
    record = service.create_record({'project_id': project['id'], 'title': 'Synthetic record'})
    return service, project, record


def mark_finalized(app, record):
    with app.app_context():
        item = db.session.get(LabRecord, record['id'])
        item.is_finalized, item.finalized_at = True, utcnow()
        db.session.commit()


def test_finalized_record_rejects_ordinary_and_bulk_edits(app):
    service, project, record = record_fixture(app)
    mark_finalized(app, record)
    with pytest.raises(ValidationError):
        service.update_record({'id': record['id'], 'actual_result': 'overwrite'}, record['row_version'])
    with pytest.raises(ValidationError):
        service.record_bulk({'ids': [record['id']], 'action': 'status', 'value': 'draft'})
    assert service.get_record({'id': record['id']})['actual_result'] == ''


def test_finalize_and_explicit_revision_are_versioned_bridge_commands(app):
    service, project, record = record_fixture(app)
    bridge = DesktopBridge(service, object(), {})
    def invoke(command, payload, version):
        return bridge.invoke({'request_id': str(uuid.uuid4()), 'command': command,
                              'payload': payload, 'expected_row_version': version})
    locked = invoke('record.finalize', {'id': record['id']}, record['row_version'])
    assert locked['ok'], locked
    assert locked['data']['is_finalized']
    version = locked['data']['row_version']
    rejected = invoke('record.update', {'id': record['id'], 'title': 'overwrite'}, version)
    assert rejected['error']['code'] == 'validation_error'
    revised = invoke('record.revise', {'id': record['id'], 'actual_result': 'corrected', 'reason': 'Correction'}, version)
    assert revised['ok'], revised
    assert revised['data']['is_finalized']
    assert revised['data']['row_version'] == version + 1
    with app.app_context():
        changes = LabRecordRevision.query.filter_by(record_id=record['id']).all()
        assert len(changes) == 2
        assert json.loads(changes[-1].before_json)['actual_result'] == ''
        assert json.loads(changes[-1].after_json)['actual_result'] == 'corrected'
        assert changes[-1].reason == 'Correction'
    stale = invoke('record.revise', {'id': record['id'], 'title': 'stale'}, version)
    assert stale['error']['code'] == 'row_version_conflict'


@pytest.mark.parametrize('failure', ['metadata', 'index', 'copy'])
def test_failed_import_leaves_no_unregistered_copy(app, tmp_path, monkeypatch, failure):
    service, project, record = record_fixture(app)
    # Only this test's isolated directory is eligible for file compensation.
    monkeypatch.setattr(app, 'instance_path', str(tmp_path / 'workspace'))
    source = tmp_path / 'source.txt'
    source.write_text('synthetic evidence', encoding='utf-8')
    if failure == 'index':
        def fail(*args):
            raise RuntimeError('synthetic index failure')
        monkeypatch.setattr(service, '_index_entity', fail)
    if failure == 'copy':
        def partial_copy(source, target):
            Path(target).write_bytes(b'partial')
            raise OSError('synthetic full disk')
        monkeypatch.setattr('app.services.desktop_modules.shutil.copy2', partial_copy)
    payload = {'path': str(source), 'storage_mode': 'managed',
               'display_name': 'x' * 256 if failure == 'metadata' else 'evidence'}
    with pytest.raises((ValidationError, RuntimeError, OSError)):
        service.import_library_item(payload)
    assert source.read_text(encoding='utf-8') == 'synthetic evidence'
    assert not [p for p in (tmp_path / 'workspace' / 'library').rglob('*') if p.is_file()]
    with app.app_context():
        assert LibraryItem.query.count() == 0


def test_project_counts_exclude_trashed_records(app):
    service, project, record = record_fixture(app)
    service.record_bulk({'ids': [record['id']], 'action': 'trash'})
    assert service.list_projects()[0]['record_count'] == 0
    assert service.dashboard()['projects'][0]['record_count'] == 0


def test_workspace_backup_contains_database_files_and_hash_manifest(app, tmp_path, monkeypatch):
    service = DesktopApplicationService(app)
    monkeypatch.setattr(app, 'instance_path', str(tmp_path))
    app.config['BACKUP_DIR'] = str(tmp_path / 'backups')
    with sqlite3.connect(tmp_path / 'research.db') as conn:
        conn.execute('CREATE TABLE synthetic (value TEXT)')
        conn.execute("INSERT INTO synthetic VALUES ('preserved')")
    managed = tmp_path / 'library' / 'test.txt'
    managed.parent.mkdir()
    managed.write_text('evidence', encoding='utf-8')
    (tmp_path / 'credential_key').write_text('must not export credentials', encoding='utf-8')
    result = service.create_backup({'scope': 'workspace'})
    assert result['scope'] == 'workspace'
    assert zipfile.is_zipfile(result['path'])
    with zipfile.ZipFile(result['path']) as archive:
        assert archive.read('library/test.txt') == b'evidence'
        assert 'credential_key' not in archive.namelist()
        manifest = json.loads(archive.read('manifest.json'))
        for item in manifest['files']:
            assert hashlib.sha256(archive.read(item['path'])).hexdigest() == item['sha256']
        assert 'external_files' in manifest['excluded']
        restored = tmp_path / 'restored.db'
        restored.write_bytes(archive.read('research.db'))
    with sqlite3.connect(restored) as conn:
        assert conn.execute('SELECT value FROM synthetic').fetchone()[0] == 'preserved'


def test_ai_continuation_sends_history_and_rejects_wrong_target_before_provider(app, monkeypatch):
    service, project, record = record_fixture(app)
    with app.app_context():
        preset = ApiPreset(user_id=User.query.first().id, name='Synthetic',
                           api_url='https://example.test/v1', text_model='test', is_enabled=True, is_default=True)
        preset.set_api_key('synthetic-test-key')
        db.session.add(preset)
        db.session.commit()
    calls = []
    def provider(messages, system_prompt, **kwargs):
        calls.append(messages)
        return {'reply': 'Previous answer', 'proposal': {}}
    monkeypatch.setattr('app.ai_service.chat_with_assistant', provider)
    payload = {'target_type': 'project', 'target_id': project['id'], 'prompt': 'First question'}
    first = service.ai_propose(payload)
    service.ai_propose({**payload, 'conversation_id': first['conversation_id'], 'prompt': 'Continue'})
    assert any(m['role'] == 'assistant' and m['content'] == 'Previous answer' for m in calls[-1])
    other = service.create_project({'title': 'Other project'})
    before = len(calls)
    with pytest.raises(ValidationError):
        service.ai_propose({**payload, 'target_id': other['id'], 'conversation_id': first['conversation_id']})
    assert len(calls) == before
