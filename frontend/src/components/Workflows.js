import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'react-toastify';
import { useAuth } from '../contexts/AuthContext';

const Workflows = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [workflows, setWorkflows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [showDelete, setShowDelete] = useState(false);
  const [workflowToDelete, setWorkflowToDelete] = useState(null);
  const [form, setForm] = useState({ name: '', description: '' });
  const [runningWorkflows, setRunningWorkflows] = useState({});
  const [editSched, setEditSched] = useState({}); // { [id]: { enabled, cron, timezone, saving } }

  // Poll a specific workflow until next_run_at is available/updated
  const pollWorkflowNextRun = async (id, { attempts = 8, delayMs = 500 } = {}) => {
    const sleep = (ms) => new Promise(r => setTimeout(r, ms));
    let last;
    for (let i = 0; i < attempts; i++) {
      try {
        const res = await axios.get(`/api/workflows/${id}`);
        const wf = res.data;
        if (wf && (wf.next_run_at || i === attempts - 1)) {
          last = wf;
          break;
        }
      } catch (_) {}
      await sleep(delayMs);
    }
    return last;
  };

  const checkRunningWorkflows = async () => {
    try {
      const runningMap = {};
      for (const workflow of workflows) {
        try {
          const runsRes = await axios.get(`/api/workflows/${workflow.id}/runs`);
          const runs = runsRes.data.runs || [];
          const runningRun = runs.find(r => r.status === 'running');
          if (runningRun) {
            runningMap[workflow.id] = runningRun.id;
          }
        } catch (e) {
          // Ignore errors for individual workflow runs
        }
      }
      setRunningWorkflows(runningMap);
    } catch (e) {
      console.error('Failed to check running workflows:', e);
    }
  };

  const load = async () => {
    try {
      setLoading(true);
      const res = await axios.get('/api/workflows/');
      setWorkflows(res.data.workflows || []);
    } catch (e) {
      setError('Failed to load workflows');
      toast.error('Failed to load workflows');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { 
    load(); 
  }, []);

  useEffect(() => {
    if (workflows.length > 0) {
      checkRunningWorkflows();
    }
  }, [workflows]);

  // Light auto-refresh to keep runs_24h/last_result and next_run fresh
  useEffect(() => {
    const t = setInterval(() => {
      load();
    }, 30000);
    return () => clearInterval(t);
  }, []);

  const createQuick = async () => {
    try {
      // Generate a unique default name to avoid unique constraint conflicts
      const base = 'New Workflow';
      const existing = new Set((workflows||[]).map(w=>String(w.name)));
      let name = base;
      let i = 2;
      while (existing.has(name)) { name = `${base} ${i++}`; }
      const payload = { name, description: '', nodes: [], edges: [] };
      const res = await axios.post('/api/workflows/', payload);
      toast.success('Workflow created');
      const newId = res.data?.id;
      if (newId) {
        setTimeout(() => { window.location.href = `/workflows/${newId}/builder`; }, 30);
        return;
      }
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create workflow');
    }
  };

  const createWorkflow = async () => {
    if (!form.name.trim()) { toast.warn('Name is required'); return; }
    try {
      const payload = { name: form.name.trim(), description: form.description || '', nodes: [], edges: [] };
      const res = await axios.post('/api/workflows/', payload);
      toast.success('Workflow created');
      setShowCreate(false);
      setForm({ name: '', description: '' });
      // Navigate directly to builder of the new workflow
      const newId = res.data?.id;
      if (newId) {
        // Use hard redirect to ensure landing on builder reliably
        setTimeout(() => { window.location.href = `/workflows/${newId}/builder`; }, 50);
        return;
      }
      await load();
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to create workflow');
    }
  };

  const runWorkflow = async (id) => {
    // Mark as running optimistically
    setRunningWorkflows(prev => ({ ...prev, [id]: true }));
    try {
      const res = await axios.post(`/api/workflows/${id}/run`, {});
      const rid = res.data?.run_id;
      toast.success(`Run started (#${rid})`);
      // Re-check running status shortly after kick-off
      setTimeout(checkRunningWorkflows, 800);
      setTimeout(checkRunningWorkflows, 3000);
      return;
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to start run');
      // Revert running flag on failure
      setRunningWorkflows(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
  };

  const beginScheduleEdit = (w) => {
    setEditSched(prev => ({
      ...prev,
      [w.id]: {
        enabled: String(w.trigger_type || '').toLowerCase() === 'schedule',
        cron: w.schedule_cron || w.cron_expression || '',
        timezone: w.schedule_timezone || w.timezone || (Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'),
        saving: false,
      }
    }));
  };

  const cancelScheduleEdit = (id) => {
    setEditSched(prev => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  };

  const saveSchedule = async (id) => {
    const es = editSched[id];
    if (!es) return;
    try {
      setEditSched(prev => ({ ...prev, [id]: { ...prev[id], saving: true } }));
      const payload = {};
      if (es.enabled) {
        payload.trigger_type = 'schedule';
        payload.schedule_cron = (es.cron || '').trim();
        payload.schedule_timezone = (es.timezone || 'UTC').trim();
        if (!payload.schedule_cron) { toast.warn('Cron expression is required'); return; }
      } else {
        // disable scheduling
        payload.trigger_type = null;
        payload.schedule_cron = null;
        payload.schedule_timezone = null;
      }
      await axios.put(`/api/workflows/${id}`, payload);
      // After saving, poll a few times so APScheduler sync can populate next_run_at
      const refreshed = await pollWorkflowNextRun(id, { attempts: 8, delayMs: 400 });
      if (refreshed) {
        // Merge into current list without full reload for snappier UX
        setWorkflows(prev => (prev || []).map(w => w.id === id ? {
          ...w,
          trigger_type: refreshed.trigger_type,
          schedule_cron: refreshed.schedule_cron,
          schedule_timezone: refreshed.schedule_timezone,
          last_run_at: refreshed.last_run_at,
          next_run_at: refreshed.next_run_at,
          runs_24h: refreshed.runs_24h,
          last_result: refreshed.last_result,
        } : w));
      } else {
        await load();
      }
      toast.success('Workflow schedule saved');
      cancelScheduleEdit(id);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to save schedule');
      setEditSched(prev => ({ ...prev, [id]: { ...prev[id], saving: false } }));
    }
  };

  const deleteWorkflow = async (id) => {
    try {
      await axios.delete(`/api/workflows/${id}`);
      toast.success('Workflow deleted');
      setWorkflows(prev => prev.filter(w => w.id !== id));
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete workflow');
    }
  };

  const formatLocal = (v) => {
    if (!v) return '—';
    try {
      // Coerce to string, handle UTC Z suffix and naive values as UTC
      const s = typeof v === 'string' ? v : String(v);
      const normalized = s.endsWith('Z') || s.match(/[\+\-]\d{2}:?\d{2}$/) ? s : (s + (s.includes('T') ? 'Z' : ''));
      const d = new Date(normalized);
      if (isNaN(d.getTime())) return s;
      return (
        <div>
          <div>{d.toLocaleString()}</div>
          <small className="text-muted">({Intl.DateTimeFormat().resolvedOptions().timeZone})</small>
        </div>
      );
    } catch (e) {
      return String(v);
    }
  };

  const formatInTz = (v, tz) => {
    if (!v) return '—';
    try {
      const s = typeof v === 'string' ? v : String(v);
      // Do NOT append 'Z' automatically to avoid double-shifting
      // Try direct parse; if it fails, normalize spacing only
      let d = new Date(s);
      if (isNaN(d.getTime())) {
        const spaced = s.includes('T') ? s : s.replace(' ', 'T');
        d = new Date(spaced);
      }
      if (isNaN(d.getTime())) return s;
      const zone = (tz && typeof tz === 'string' && tz.trim()) ? tz : Intl.DateTimeFormat().resolvedOptions().timeZone;
      const fmt = new Intl.DateTimeFormat(undefined, {
        timeZone: zone,
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      });
      return (
        <div>
          <div>{fmt.format(d)}</div>
          <small className="text-muted">({zone})</small>
        </div>
      );
    } catch (e) {
      return String(v);
    }
  };

  const nextRunBadge = (v) => {
    if (!v) return null;
    try {
      const s = typeof v === 'string' ? v : String(v);
      let d = new Date(s);
      if (isNaN(d.getTime())) {
        const spaced = s.includes('T') ? s : s.replace(' ', 'T');
        d = new Date(spaced);
      }
      if (isNaN(d.getTime())) return null;
      const now = new Date();
      const diffMs = d.getTime() - now.getTime();
      const past = diffMs < 0;
      const mins = Math.abs(Math.round(diffMs / 60000));
      const label = mins < 1 ? (past ? '<1 min ago' : 'in <1 min') : (past ? `${mins} min ago` : `in ${mins} min`);
      const cls = past ? 'bg-secondary text-white' : 'bg-primary text-white';
      return <span className={`badge ${cls} ms-2`}>{label}</span>;
    } catch { return null; }
  };

  return (
    <div className="container-fluid">
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2><i className="bi bi-diagram-3 me-2"></i>Workflows</h2>
      </div>

      <div className="card shadow-lg">
        <div className="card-body">
          {loading ? (
            <div className="text-center py-5">
              <div className="spinner-border text-primary" role="status"><span className="visually-hidden">Loading...</span></div>
            </div>
          ) : (
            <div className="table-responsive">
              <table className="table table-sm table-hover table-striped">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Description</th>
                    <th>Created</th>
                    <th>Trigger Type</th>
                    <th>Last Run</th>
                    <th>Next Run</th>
                    <th className="text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {workflows.length === 0 ? (
                    <tr><td colSpan={7} className="text-center text-muted">No workflows</td></tr>
                  ) : workflows.map(w => (
                    <tr key={w.id}>
                      <td><strong>{w.name}</strong></td>
                      <td>{w.description || '-'}</td>
                      <td>{formatInTz(w.created_at, null)}</td>
                      <td className="text-capitalize">{w.trigger_type || 'user'}</td>
                      <td>
                        {formatInTz(w.last_run_at, null)}
                      </td>
                      <td>
                        {formatInTz(w.next_run_at, w.schedule_timezone)}
                        {nextRunBadge(w.next_run_at)}
                      </td>
                      <td className="d-flex gap-2 justify-content-center align-items-center">
                        <div className="btn-group" role="group">
                          <button className="btn btn-outline-primary btn-sm" onClick={()=>window.location.href=`/workflows/${w.id}/builder`}>
                            <i className="bi bi-pencil me-1"></i>Edit
                          </button>
                          <button className="btn btn-outline-danger btn-sm" onClick={() => { setWorkflowToDelete(w); setShowDelete(true); }}>
                            <i className="bi bi-trash me-1"></i>Delete
                          </button>
                        </div>
                        <div className="vr mx-1 align-self-center" style={{height: '20px'}}></div>
                        <div className="btn-group" role="group">
                          <button className="btn btn-outline-success" onClick={() => runWorkflow(w.id)} disabled={!!runningWorkflows[w.id]}>
                            {runningWorkflows[w.id] ? (
                              <>
                                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                                Running…
                              </>
                            ) : (
                              <>
                                <i className="bi bi-play-fill me-1"></i>
                                Run
                              </>
                            )}
                          </button>
                        </div>
                        {/* Schedule controls removed as requested */}
                        {/* Monitoring removed */}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Centered Create button under table, consistent with other pages */}
      {!loading && (
        <div className="mt-3 text-center">
          <button className="btn btn-success" onClick={createQuick}>
            <i className="bi bi-plus-circle me-2"></i>
            Create
          </button>
        </div>
      )}

      {showCreate && (
        <div className="modal show d-block" style={{backgroundColor:'rgba(0,0,0,0.5)'}}>
          <div className="modal-dialog">
            <div className="modal-content">
              <div className="modal-header border-secondary">
                <h5 className="modal-title">Create Workflow</h5>
                <button type="button" className="btn-close btn-close-white" onClick={() => setShowCreate(false)}></button>
              </div>
              <div className="modal-body">
                <div className="mb-3">
                  <label className="form-label">Name</label>
                  <input className="form-control" value={form.name} onChange={(e)=>setForm({...form, name:e.target.value})} />
                </div>
                <div className="mb-3">
                  <label className="form-label">Description</label>
                  <textarea className="form-control" rows={3} value={form.description} onChange={(e)=>setForm({...form, description:e.target.value})}></textarea>
                </div>
                <div className="alert alert-info mb-0">
                  Nodes/edges can be added later in the builder (coming next).
                </div>
              </div>
              <div className="modal-footer border-secondary">
                <button className="btn btn-secondary" onClick={()=>setShowCreate(false)}>Cancel</button>
                <button className="btn btn-primary" onClick={createWorkflow}>Create</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showDelete && workflowToDelete && (
        <div className="modal show d-block" style={{backgroundColor:'rgba(0,0,0,0.5)'}}>
          <div className="modal-dialog">
            <div className="modal-content">
              <div className="modal-header border-secondary">
                <h5 className="modal-title">Delete Workflow</h5>
                <button type="button" className="btn-close btn-close-white" onClick={() => setShowDelete(false)}></button>
              </div>
              <div className="modal-body">
                <p>Are you sure you want to delete <strong>{workflowToDelete.name}</strong>?</p>
                <div className="alert alert-warning mb-0">
                  This will remove nodes, edges, and run history for this workflow.
                </div>
              </div>
              <div className="modal-footer border-secondary">
                <button className="btn btn-secondary" onClick={()=>setShowDelete(false)}>Cancel</button>
                <button className="btn btn-danger" onClick={async ()=>{ await deleteWorkflow(workflowToDelete.id); setShowDelete(false); setWorkflowToDelete(null); }}>
                  <i className="bi bi-trash me-1"></i>Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Workflows;


