import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

// Helper function to format UTC datetime in specific timezone
const formatInTimezone = (isoString, timezone) => {
  if (!isoString) return '-';
  try {
    // Do NOT append 'Z'. Assume backend sends ISO with correct offset or Z.
    const dt = new Date(isoString);
    return dt.toLocaleString(undefined, {
      timeZone: timezone || 'UTC',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });
  } catch (e) {
    return new Date(isoString).toLocaleString();
  }
};

const Schedules = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [schedules, setSchedules] = useState([]);
  const [scripts, setScripts] = useState([]);
  const [servers, setServers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({
    name: '',
    script_id: '',
    target_type: 'server',
    target_id: '',
    cron_expression: '',
    interval_seconds: '',
    timezone: (Intl && Intl.DateTimeFormat().resolvedOptions().timeZone) || 'UTC'
  });
  const [cronPreview, setCronPreview] = useState([]);
  const [cronError, setCronError] = useState('');
  const [cronBuilder, setCronBuilder] = useState({ minute: '*', hour: '*', dom: '*', month: '*', dow: '*' });
  // Edit-side cron builder to mirror create flow
  const [editCronBuilder, setEditCronBuilder] = useState({ minute: '*', hour: '*', dom: '*', month: '*', dow: '*' });
  const [editCronPreview, setEditCronPreview] = useState([]);
  const [editCronError, setEditCronError] = useState('');
  const [rowPreview, setRowPreview] = useState({}); // { [scheduleId]: { loading, error, next: [] } }
  const [showEdit, setShowEdit] = useState(false);
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState({
    id: null,
    name: '',
    script_id: '',
    target_type: 'server',
    target_id: '',
    cron_expression: '',
    interval_seconds: '',
    timezone: (Intl && Intl.DateTimeFormat().resolvedOptions().timeZone) || 'UTC',
    enabled: true,
  });
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [scheduleToDelete, setScheduleToDelete] = useState(null);

  useEffect(() => {
    if (user?.role !== 'admin') return;
    const init = async () => {
      try {
        setLoading(true);
        const [sc, se, sg, ss] = await Promise.all([
          axios.get('/api/schedules/'),
          axios.get('/api/servers/'),
          axios.get('/api/server-groups/'),
          axios.get('/api/scripts/')
        ]);
        setSchedules(sc.data.schedules || []);
        setServers(se.data.servers || []);
        setGroups(sg.data.groups || []);
        setScripts(ss.data.scripts || []);
      } catch (e) {
        console.error(e);
        setError('Failed to load schedules');
      } finally {
        setLoading(false);
      }
    };
    init();
  }, [user]);

  const refresh = async () => {
    try {
      const sc = await axios.get('/api/schedules/');
      setSchedules(sc.data.schedules || []);
    } catch (e) { /* noop */ }
  };

  const openEdit = (s) => {
    setEditForm({
      id: s.id,
      name: s.name || '',
      script_id: s.script_id || '',
      target_type: s.target_type || 'server',
      target_id: s.target_id || '',
      cron_expression: s.cron_expression || '',
      interval_seconds: s.interval_seconds || '',
      timezone: s.timezone || ((Intl && Intl.DateTimeFormat().resolvedOptions().timeZone) || 'UTC'),
      enabled: !!s.enabled,
    });
    // Initialize edit cron builder from existing expression if present
    if (s.cron_expression) {
      try {
        const parts = String(s.cron_expression).trim().split(/\s+/);
        if (parts.length === 5) {
          setEditCronBuilder({ minute: parts[0], hour: parts[1], dom: parts[2], month: parts[3], dow: parts[4] });
        } else {
          setEditCronBuilder({ minute: '*', hour: '*', dom: '*', month: '*', dow: '*' });
        }
      } catch {
        setEditCronBuilder({ minute: '*', hour: '*', dom: '*', month: '*', dow: '*' });
      }
      previewCronEdit(s.cron_expression, s.timezone);
    } else {
      setEditCronBuilder({ minute: '*', hour: '*', dom: '*', month: '*', dow: '*' });
      setEditCronPreview([]);
      setEditCronError('');
    }
    setShowEdit(true);
  };

  const updateSchedule = async (e) => {
    e.preventDefault();
    if (!editForm.id) return;
    setEditing(true);
    try {
      const payload = {
        name: editForm.name?.trim(),
        script_id: editForm.script_id ? Number(editForm.script_id) : undefined,
        target_type: editForm.target_type,
        target_id: editForm.target_id ? Number(editForm.target_id) : undefined,
        cron_expression: editForm.cron_expression?.trim() || null,
        interval_seconds: editForm.interval_seconds ? Number(editForm.interval_seconds) : null,
        timezone: editForm.timezone || 'UTC',
        enabled: !!editForm.enabled,
      };
      await axios.put(`/api/schedules/${editForm.id}`, payload);
      setShowEdit(false);
      await refresh();
    } catch (e) {
      console.error(e);
      alert(e.response?.data?.detail || 'Failed to update schedule');
    } finally {
      setEditing(false);
    }
  };

  const createSchedule = async (e) => {
    e.preventDefault();
    if (!form.name || !form.script_id || !form.target_id) return;
    setCreating(true);
    try {
      const payload = {
        name: form.name.trim(),
        script_id: Number(form.script_id),
        target_type: form.target_type,
        target_id: Number(form.target_id),
        cron_expression: form.cron_expression?.trim() || null,
        interval_seconds: form.interval_seconds ? Number(form.interval_seconds) : null,
        timezone: form.timezone || 'UTC',
        enabled: true
      };
      await axios.post('/api/schedules/', payload);
      setShowCreate(false);
      setForm({ name: '', script_id: '', target_type: 'server', target_id: '', cron_expression: '', interval_seconds: '' });
      await refresh();
    } catch (e) {
      console.error(e);
      alert(e.response?.data?.detail || 'Failed to create schedule');
    } finally {
      setCreating(false);
    }
  };

  const updateCronFromBuilder = (field, value) => {
    const next = { ...cronBuilder, [field]: value };
    setCronBuilder(next);
    const expr = `${next.minute} ${next.hour} ${next.dom} ${next.month} ${next.dow}`;
    setForm({ ...form, cron_expression: expr });
    previewCron(expr);
  };

  const previewCron = async (expr) => {
    if (!expr || !expr.trim()) { setCronPreview([]); setCronError(''); return; }
    try {
      setCronError('');
      const resp = await axios.get('/api/schedules/cron/preview', { params: { expr, tz: form.timezone || 'UTC', count: 5 } });
      setCronPreview(resp.data.next || []);
    } catch (e) {
      setCronPreview([]);
      setCronError(e.response?.data?.detail || 'Invalid cron');
    }
  };

  const updateEditCronFromBuilder = (field, value) => {
    const next = { ...editCronBuilder, [field]: value };
    setEditCronBuilder(next);
    const expr = `${next.minute} ${next.hour} ${next.dom} ${next.month} ${next.dow}`;
    setEditForm(({ ...rest }) => ({ ...rest, cron_expression: expr }));
    previewCronEdit(expr);
  };

  const previewCronEdit = async (expr, tzOverride) => {
    if (!expr || !expr.trim()) { setEditCronPreview([]); setEditCronError(''); return; }
    try {
      setEditCronError('');
      const resp = await axios.get('/api/schedules/cron/preview', { params: { expr, tz: (tzOverride || editForm.timezone || 'UTC'), count: 5 } });
      setEditCronPreview(resp.data.next || []);
    } catch (e) {
      setEditCronPreview([]);
      setEditCronError(e.response?.data?.detail || 'Invalid cron');
    }
  };

  const cronToText = (expr) => {
    if (!expr) return '';
    const parts = expr.trim().split(/\s+/);
    if (parts.length !== 5) return expr;
    const [m,h,dom,mon,dow] = parts;
    if (m.startsWith('*/') && h==='*' && dom==='*' && mon==='*' && dow==='*') {
      return `Every ${m.replace('*/','')} minutes`;
    }
    if (m==='0' && h==='*' && dom==='*' && mon==='*' && dow==='*') return 'Every hour at minute 0';
    if (m==='0' && h==='0' && dom==='*' && mon==='*' && dow==='*') return 'Every day at 00:00';
    if (m==='0' && h==='0' && dom==='*' && mon==='*' && (dow==='0' || dow==='7')) return 'Every week on Sunday at 00:00';
    if (m==='0' && h==='0' && dom==='1' && mon==='*' && dow==='*') return 'Every month on the 1st at 00:00';
    return expr;
  };

  const toggleRowPreview = async (sch) => {
    // if no cron, clear
    if (!sch.cron_expression) {
      setRowPreview(prev=>({ ...prev, [sch.id]: { loading:false, error:'No cron', next:[] } }));
      return;
    }
    const current = rowPreview[sch.id];
    if (current && current.next && current.next.length>0) {
      // collapse
      setRowPreview(prev=>({ ...prev, [sch.id]: { ...prev[sch.id], next: [] } }));
      return;
    }
    setRowPreview(prev=>({ ...prev, [sch.id]: { loading:true, error:'', next:[] } }));
    try {
      const resp = await axios.get('/api/schedules/cron/preview', { params: { expr: sch.cron_expression, tz: sch.timezone || 'UTC', count: 5 } });
      setRowPreview(prev=>({ ...prev, [sch.id]: { loading:false, error:'', next: resp.data.next || [] } }));
    } catch (e) {
      setRowPreview(prev=>({ ...prev, [sch.id]: { loading:false, error: (e.response?.data?.detail || 'Preview failed'), next: [] } }));
    }
  };

  // Removed inline enable/disable toggle; handled via Edit dialog

  const deleteSchedule = (sch) => {
    setScheduleToDelete(sch);
    setShowDeleteModal(true);
  };

  const confirmDelete = async () => {
    if (!scheduleToDelete) return;
    try {
      await axios.delete(`/api/schedules/${scheduleToDelete.id}`);
      await refresh();
    } catch (e) {
      console.error(e);
    } finally {
      setShowDeleteModal(false);
      setScheduleToDelete(null);
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="main-content"><div className="container-fluid"><div className="alert alert-warning border-0" role="alert" style={{backgroundColor: 'rgba(245, 158, 11, 0.1)'}}><i className="bi bi-exclamation-triangle me-2"></i>Access Denied</div></div></div>
    );
  }

  if (loading) {
    return (
      <div className="main-content"><div className="container-fluid"><div className="text-center"><div className="spinner-border text-primary" role="status"><span className="visually-hidden">Loading...</span></div></div></div></div>
    );
  }

  return (
    <div className="main-content">
      <div className="container-fluid">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h1><i className="bi bi-alarm me-3"></i>Schedules</h1>
        </div>

        {error && (
          <div className="alert alert-danger border-0" role="alert" style={{backgroundColor: 'rgba(239, 68, 68, 0.1)'}}>
            <i className="bi bi-exclamation-circle me-2"></i>{error}
          </div>
        )}

        <div className="card shadow-lg">
          <div className="card-body">
            <div className="table-responsive">
              <table className="table table-sm table-hover table-striped">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Script</th>
                    <th>Target</th>
                    <th>Schedule</th>
                    <th>Enabled</th>
                    <th>Next Run</th>
                    <th>Last Run</th>
                    <th className="text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {schedules.map(s => {
                    const script = scripts.find(x => x.id === s.script_id);
                    const targetName = s.target_type === 'server'
                      ? (servers.find(x => x.id === s.target_id)?.name || `Server #${s.target_id}`)
                      : (groups.find(x => x.id === s.target_id)?.name || `Group #${s.target_id}`);
                    return (
                      <tr key={s.id}>
                        <td><strong>{s.name}</strong></td>
                        <td>{script?.name || `#${s.script_id}`}</td>
                        <td>
                          <span className="badge bg-secondary me-2">{s.target_type}</span>
                          {targetName}
                        </td>
                        <td>
                          {s.cron_expression ? (
                            <div>
                              <code title={s.cron_expression}>{cronToText(s.cron_expression)}</code>
                              <div className="mt-1">
                                <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> toggleRowPreview(s)}>
                                  {rowPreview[s.id]?.next?.length ? 'Hide next runs' : 'Show next runs'}
                                </button>
                              </div>
                              {rowPreview[s.id]?.loading && (<div className="small text-muted">Loading…</div>)}
                              {rowPreview[s.id]?.error && (<div className="small text-danger">{rowPreview[s.id].error}</div>)}
                              {rowPreview[s.id]?.next?.length>0 && (
                                <ul className="small mb-0 mt-1">
                                  {rowPreview[s.id].next.map((t,i)=>(<li key={i}>{new Date(t).toLocaleString()}</li>))}
                                </ul>
                              )}
                            </div>
                          ) : s.interval_seconds ? (
                            <span>{s.interval_seconds}s</span>
                          ) : (
                            <span className="text-muted">—</span>
                          )}
                        </td>
                        <td>
                          <span className={`badge ${s.enabled ? 'bg-success' : 'bg-secondary'}`}>{s.enabled ? 'Enabled' : 'Disabled'}</span>
                        </td>
                        <td>
                          {s.next_run_at ? (
                            <div>
                              <div>{formatInTimezone(s.next_run_at, s.timezone)}</div>
                              <small className="text-muted">({s.timezone || 'UTC'})</small>
                            </div>
                          ) : '—'}
                        </td>
                        <td>
                          {s.last_run_at ? (
                            <div>
                              <div>{formatInTimezone(s.last_run_at, s.timezone)}</div>
                              <small className="text-muted">({s.timezone || 'UTC'})</small>
                            </div>
                          ) : '—'}
                        </td>
                        <td>
                          <div className="d-flex gap-2 justify-content-center">
                            <button className="btn btn-outline-primary" onClick={()=> openEdit(s)}>
                              Edit
                            </button>
                            <button className="btn btn-outline-danger" onClick={()=> deleteSchedule(s)}>
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {schedules.length === 0 && (
                    <tr>
                      <td colSpan="8" className="text-center text-muted">No schedules yet</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="mt-3 text-center">
              <button className="btn btn-success" onClick={()=> setShowCreate(true)}>
                <i className="bi bi-plus-circle me-2"></i>
                Create
              </button>
            </div>
          </div>
        </div>

        {showCreate && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title"><i className="bi bi-plus-circle me-2"></i>Create Schedule</h5>
                  <button type="button" className="btn-close btn-close-white" onClick={()=> setShowCreate(false)}></button>
                </div>
                <form onSubmit={createSchedule}>
                  <div className="modal-body">
                    <div className="mb-3">
                      <label className="form-label">Name</label>
                      <input className="form-control" value={form.name} onChange={(e)=> setForm({...form, name: e.target.value})} required />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Script</label>
                      <select className="form-select" value={form.script_id} onChange={(e)=> setForm({...form, script_id: e.target.value})} required>
                        <option value="">Select script</option>
                        {scripts.map(sc => (<option key={sc.id} value={sc.id}>{sc.name}</option>))}
                      </select>
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Target Type</label>
                      <select className="form-select" value={form.target_type} onChange={(e)=> setForm({...form, target_type: e.target.value, target_id: ''})}>
                        <option value="server">Server</option>
                        <option value="group">Group</option>
                      </select>
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Target</label>
                      {form.target_type === 'server' ? (
                        <select className="form-select" value={form.target_id} onChange={(e)=> setForm({...form, target_id: e.target.value})} required>
                          <option value="">Select server</option>
                          {servers.map(s => (<option key={s.id} value={s.id}>{s.name}</option>))}
                        </select>
                      ) : (
                        <select className="form-select" value={form.target_id} onChange={(e)=> setForm({...form, target_id: e.target.value})} required>
                          <option value="">Select group</option>
                          {groups.map(g => (<option key={g.id} value={g.id}>{g.name}</option>))}
                        </select>
                      )}
                    </div>
                    <div className="mb-2">
                      <label className="form-label">Cron Expression (optional)</label>
                      <input className="form-control" placeholder="e.g. */5 * * * *" value={form.cron_expression} onChange={(e)=> { setForm({...form, cron_expression: e.target.value}); previewCron(e.target.value); }} />
                      <div className="form-text">Use either cron or interval. Cron takes precedence.</div>
                    </div>
                    <div className="mb-3 border rounded p-2">
                      <div className="d-flex flex-wrap gap-2 align-items-end">
                        <div>
                          <label className="form-label">Minute</label>
                          <input className="form-control form-control-sm" value={cronBuilder.minute} onChange={(e)=> updateCronFromBuilder('minute', e.target.value)} placeholder="* or 0-59 or */5" />
                        </div>
                        <div>
                          <label className="form-label">Hour</label>
                          <input className="form-control form-control-sm" value={cronBuilder.hour} onChange={(e)=> updateCronFromBuilder('hour', e.target.value)} placeholder="* or 0-23" />
                        </div>
                        <div>
                          <label className="form-label">Day of Month</label>
                          <input className="form-control form-control-sm" value={cronBuilder.dom} onChange={(e)=> updateCronFromBuilder('dom', e.target.value)} placeholder="* or 1-31" />
                        </div>
                        <div>
                          <label className="form-label">Month</label>
                          <input className="form-control form-control-sm" value={cronBuilder.month} onChange={(e)=> updateCronFromBuilder('month', e.target.value)} placeholder="* or 1-12" />
                        </div>
                        <div>
                          <label className="form-label">Day of Week</label>
                          <input className="form-control form-control-sm" value={cronBuilder.dow} onChange={(e)=> updateCronFromBuilder('dow', e.target.value)} placeholder="* or 0-6" />
                        </div>
                        <div className="ms-auto">
                          <div className="btn-group">
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> updateCronFromBuilder('minute', '*/5') && updateCronFromBuilder('hour','*')}>Every 5m</button>
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> { setCronBuilder({ minute: '0', hour: '*', dom: '*', month: '*', dow: '*' }); const expr='0 * * * *'; setForm({...form, cron_expression: expr}); previewCron(expr); }}>Hourly</button>
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> { setCronBuilder({ minute: '0', hour: '0', dom: '*', month: '*', dow: '*' }); const expr='0 0 * * *'; setForm({...form, cron_expression: expr}); previewCron(expr); }}>Daily</button>
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> { setCronBuilder({ minute: '0', hour: '0', dom: '*', month: '*', dow: '0' }); const expr='0 0 * * 0'; setForm({...form, cron_expression: expr}); previewCron(expr); }}>Weekly</button>
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> { setCronBuilder({ minute: '0', hour: '0', dom: '1', month: '*', dow: '*' }); const expr='0 0 1 * *'; setForm({...form, cron_expression: expr}); previewCron(expr); }}>Monthly</button>
                          </div>
                        </div>
                      </div>
                      <div className="row g-2 mt-2">
                        <div className="col-auto">
                          <label className="form-label">Timezone</label>
                          <input className="form-control form-control-sm" value={form.timezone} onChange={(e)=> { setForm({...form, timezone: e.target.value}); if (form.cron_expression) previewCron(form.cron_expression); }} placeholder="e.g. UTC or Europe/Berlin" />
                          <div className="form-text">Applies to preview and schedule execution times.</div>
                        </div>
                      </div>
                      <div className="mt-2">
                        <small className="text-muted">Preview (UTC):</small>
                        {cronError ? (
                          <div className="text-danger small">{cronError}</div>
                        ) : (
                          <ul className="small mb-0">
                            {cronPreview.map((t, i)=>(<li key={i}>{new Date(t).toLocaleString()}</li>))}
                            {cronPreview.length===0 && (<li className="text-muted">—</li>)}
                          </ul>
                        )}
                      </div>
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Interval Seconds (optional)</label>
                      <input type="number" min="1" className="form-control" placeholder="e.g. 60" value={form.interval_seconds} onChange={(e)=> setForm({...form, interval_seconds: e.target.value})} />
                      <div className="form-text">Provide either cron or interval. If both set, cron takes precedence.</div>
                    </div>
                  </div>
                  <div className="modal-footer">
                    <button type="button" className="btn btn-secondary" onClick={()=> setShowCreate(false)}>Cancel</button>
                    <button type="submit" className="btn btn-primary" disabled={creating}>
                      {creating ? 'Creating...' : 'Create'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}

        {showDeleteModal && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-exclamation-triangle me-2 text-warning"></i>
                    Confirm Delete
                  </h5>
                  <button type="button" className="btn-close btn-close-white" onClick={()=> { setShowDeleteModal(false); setScheduleToDelete(null); }}></button>
                </div>
                <div className="modal-body">
                  <p>Are you sure you want to delete schedule <strong>{scheduleToDelete?.name}</strong>?</p>
                  <p className="text-danger"><i className="bi bi-exclamation-circle me-2"></i>This action cannot be undone.</p>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={()=> { setShowDeleteModal(false); setScheduleToDelete(null); }}>Cancel</button>
                  <button type="button" className="btn btn-danger" onClick={confirmDelete}>
                    <i className="bi bi-trash me-2"></i>
                    Delete
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {showEdit && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title"><i className="bi bi-pencil-square me-2"></i>Edit Schedule</h5>
                  <button type="button" className="btn-close btn-close-white" onClick={()=> setShowEdit(false)}></button>
                </div>
                <form onSubmit={updateSchedule}>
                  <div className="modal-body">
                    <div className="mb-3">
                      <label className="form-label">Name</label>
                      <input className="form-control" value={editForm.name} onChange={(e)=> setEditForm({...editForm, name: e.target.value})} required />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Script</label>
                      <select className="form-select" value={editForm.script_id} onChange={(e)=> setEditForm({...editForm, script_id: e.target.value})} required>
                        <option value="">Select script</option>
                        {scripts.map(sc => (<option key={sc.id} value={sc.id}>{sc.name}</option>))}
                      </select>
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Target Type</label>
                      <select className="form-select" value={editForm.target_type} onChange={(e)=> setEditForm({...editForm, target_type: e.target.value, target_id: ''})}>
                        <option value="server">Server</option>
                        <option value="group">Group</option>
                      </select>
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Target</label>
                      {editForm.target_type === 'server' ? (
                        <select className="form-select" value={editForm.target_id} onChange={(e)=> setEditForm({...editForm, target_id: e.target.value})} required>
                          <option value="">Select server</option>
                          {servers.map(s => (<option key={s.id} value={s.id}>{s.name}</option>))}
                        </select>
                      ) : (
                        <select className="form-select" value={editForm.target_id} onChange={(e)=> setEditForm({...editForm, target_id: e.target.value})} required>
                          <option value="">Select group</option>
                          {groups.map(g => (<option key={g.id} value={g.id}>{g.name}</option>))}
                        </select>
                      )}
                    </div>
                    <div className="mb-2">
                      <label className="form-label">Cron Expression (optional)</label>
                      <input className="form-control" placeholder="e.g. */5 * * * *" value={editForm.cron_expression} onChange={(e)=> { setEditForm({...editForm, cron_expression: e.target.value}); previewCronEdit(e.target.value); }} />
                      <div className="form-text">Use either cron or interval. Cron takes precedence.</div>
                    </div>
                    <div className="mb-3 border rounded p-2">
                      <div className="d-flex flex-wrap gap-2 align-items-end">
                        <div>
                          <label className="form-label">Minute</label>
                          <input className="form-control form-control-sm" value={editCronBuilder.minute} onChange={(e)=> updateEditCronFromBuilder('minute', e.target.value)} placeholder="* or 0-59 or */5" />
                        </div>
                        <div>
                          <label className="form-label">Hour</label>
                          <input className="form-control form-control-sm" value={editCronBuilder.hour} onChange={(e)=> updateEditCronFromBuilder('hour', e.target.value)} placeholder="* or 0-23" />
                        </div>
                        <div>
                          <label className="form-label">Day of Month</label>
                          <input className="form-control form-control-sm" value={editCronBuilder.dom} onChange={(e)=> updateEditCronFromBuilder('dom', e.target.value)} placeholder="* or 1-31" />
                        </div>
                        <div>
                          <label className="form-label">Month</label>
                          <input className="form-control form-control-sm" value={editCronBuilder.month} onChange={(e)=> updateEditCronFromBuilder('month', e.target.value)} placeholder="* or 1-12" />
                        </div>
                        <div>
                          <label className="form-label">Day of Week</label>
                          <input className="form-control form-control-sm" value={editCronBuilder.dow} onChange={(e)=> updateEditCronFromBuilder('dow', e.target.value)} placeholder="* or 0-6" />
                        </div>
                        <div className="ms-auto">
                          <div className="btn-group">
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> updateEditCronFromBuilder('minute', '*/5') && updateEditCronFromBuilder('hour','*')}>Every 5m</button>
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> { setEditCronBuilder({ minute: '0', hour: '*', dom: '*', month: '*', dow: '*' }); const expr='0 * * * *'; setEditForm({...editForm, cron_expression: expr}); previewCronEdit(expr); }}>Hourly</button>
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> { setEditCronBuilder({ minute: '0', hour: '0', dom: '*', month: '*', dow: '*' }); const expr='0 0 * * *'; setEditForm({...editForm, cron_expression: expr}); previewCronEdit(expr); }}>Daily</button>
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> { setEditCronBuilder({ minute: '0', hour: '0', dom: '*', month: '*', dow: '0' }); const expr='0 0 * * 0'; setEditForm({...editForm, cron_expression: expr}); previewCronEdit(expr); }}>Weekly</button>
                            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={()=> { setEditCronBuilder({ minute: '0', hour: '0', dom: '1', month: '*', dow: '*' }); const expr='0 0 1 * *'; setEditForm({...editForm, cron_expression: expr}); previewCronEdit(expr); }}>Monthly</button>
                          </div>
                        </div>
                      </div>
                      <div className="row g-2 mt-2">
                        <div className="col-auto">
                          <label className="form-label">Timezone</label>
                          <input className="form-control form-control-sm" value={editForm.timezone} onChange={(e)=> { setEditForm({...editForm, timezone: e.target.value}); if (editForm.cron_expression) previewCronEdit(editForm.cron_expression, e.target.value); }} placeholder="e.g. UTC or Europe/Berlin" />
                          <div className="form-text">Applies to preview and schedule execution times.</div>
                        </div>
                      </div>
                      <div className="mt-2">
                        <small className="text-muted">Preview (UTC):</small>
                        {editCronError ? (
                          <div className="text-danger small">{editCronError}</div>
                        ) : (
                          <ul className="small mb-0">
                            {editCronPreview.map((t, i)=>(<li key={i}>{new Date(t).toLocaleString()}</li>))}
                            {editCronPreview.length===0 && (<li className="text-muted">—</li>)}
                          </ul>
                        )}
                      </div>
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Interval Seconds (optional)</label>
                      <input type="number" min="1" className="form-control" placeholder="e.g. 60" value={editForm.interval_seconds} onChange={(e)=> setEditForm({...editForm, interval_seconds: e.target.value})} />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Timezone</label>
                      <input className="form-control" value={editForm.timezone} onChange={(e)=> setEditForm({...editForm, timezone: e.target.value})} placeholder="UTC or Europe/Istanbul" />
                    </div>
                    <div className="form-check form-switch">
                      <input className="form-check-input" type="checkbox" id="editEnabled" checked={!!editForm.enabled} onChange={(e)=> setEditForm({...editForm, enabled: e.target.checked})} />
                      <label className="form-check-label" htmlFor="editEnabled">Enabled</label>
                    </div>
                  </div>
                  <div className="modal-footer">
                    <button type="button" className="btn btn-secondary" onClick={()=> setShowEdit(false)}>Cancel</button>
                    <button type="submit" className="btn btn-primary" disabled={editing}>
                      {editing ? 'Saving...' : 'Save'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Schedules;


