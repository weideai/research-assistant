const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createRecordEditor } = require('../../app/desktop_ui/record_editor.js');

function harness() {
  const calls = [], states = [];
  const editor = createRecordEditor({
    save: (payload, version) => new Promise((resolve, reject) => calls.push({payload, version, resolve, reject})),
    onChange: state => states.push(state),
  });
  editor.open({id: 1, row_version: 1, title: 'A'});
  return {editor, calls, states};
}

test('edits during an in-flight save are persisted with the new server version', async () => {
  const {editor, calls} = harness();
  editor.edit({id: 1, title: 'first'});
  const saving = editor.flush();
  editor.edit({id: 1, title: 'second'});
  calls[0].resolve({id: 1, title: 'first', row_version: 2});
  await new Promise(setImmediate);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].version, 2);
  assert.equal(calls[1].payload.title, 'second');
  calls[1].resolve({id: 1, title: 'second', row_version: 3});
  assert.equal(await saving, true);
  assert.equal(editor.snapshot().dirty, false);
});

test('late response cannot change a newly opened record', async () => {
  const {editor, calls} = harness();
  editor.edit({id: 1, title: 'changed'});
  const saving = editor.flush();
  editor.open({id: 2, row_version: 1, title: 'B'});
  calls[0].resolve({id: 1, row_version: 2, title: 'changed'});
  await saving;
  assert.equal(editor.snapshot().record.id, 2);
  assert.equal(editor.snapshot().record.title, 'B');
});

test('failed save retains the local draft and an explicit retry can succeed', async () => {
  const {editor, calls} = harness();
  editor.edit({id: 1, title: 'unsaved'});
  const saving = editor.flush();
  calls[0].reject(new Error('disk full'));
  assert.equal(await saving, false);
  assert.equal(editor.snapshot().dirty, true);
  assert.equal(editor.snapshot().draft.title, 'unsaved');
  assert.equal(editor.snapshot().status, 'error');
  const retry = editor.flush();
  calls[1].resolve({id: 1, row_version: 2, title: 'unsaved'});
  assert.equal(await retry, true);
});

test('repeated flush does not start duplicate writes', async () => {
  const {editor, calls} = harness();
  editor.edit({id: 1, title: 'changed'});
  const first = editor.flush(), second = editor.flush();
  assert.equal(calls.length, 1);
  calls[0].resolve({id: 1, row_version: 2, title: 'changed'});
  await Promise.all([first, second]);
});
