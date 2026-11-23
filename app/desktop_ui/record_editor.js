/* Session-local drafts and serialized saves. No DOM or storage dependencies. */
(function (root) {
  "use strict";
  function createRecordEditor({save, onChange = () => {}}) {
    let current = null;
    const clone = value => JSON.parse(JSON.stringify(value));
    function snapshot() {
      if (!current) return {record: null, draft: null, dirty: false, status: "idle", error: null};
      return {record: clone(current.record), draft: clone(current.draft),
        dirty: current.edited !== current.saved, status: current.status, error: current.error};
    }
    function notify(session) { if (session === current) onChange(snapshot()); }
    function open(record) {
      current = {record: clone(record), draft: clone(record), edited: 0, saved: 0,
        status: "saved", error: null, pending: null};
      notify(current);
    }
    function edit(payload) {
      if (!current || Number(payload.id) !== Number(current.record.id)) return;
      current.draft = clone(payload);
      current.edited += 1;
      current.status = current.pending ? "saving" : "dirty";
      current.error = null;
      notify(current);
    }
    function flush() {
      const session = current;
      if (!session) return Promise.resolve(true);
      if (session.pending) return session.pending;
      if (session.edited === session.saved) return Promise.resolve(true);
      session.pending = (async () => {
        while (session === current && session.edited !== session.saved) {
          const generation = session.edited, payload = clone(session.draft);
          session.status = "saving";
          notify(session);
          try {
            const result = await save(payload, session.record.row_version);
            if (session !== current) return false;
            session.record = clone(result);
            session.saved = generation;
            session.error = null;
            if (session.saved === session.edited) session.draft = clone(result);
          } catch (error) {
            if (session === current) {
              session.status = "error";
              session.error = error;
              notify(session);
            }
            return false;
          }
        }
        session.status = "saved";
        notify(session);
        return true;
      })().finally(() => { session.pending = null; });
      return session.pending;
    }
    function detach() { current = null; onChange(snapshot()); }
    return {open, edit, flush, detach, snapshot};
  }
  if (typeof module !== "undefined" && module.exports) module.exports = {createRecordEditor};
  else root.RLabRecordEditor = {createRecordEditor};
})(typeof window !== "undefined" ? window : globalThis);
