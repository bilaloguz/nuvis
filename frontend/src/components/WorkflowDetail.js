import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'react-toastify';

const WorkflowDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [wf, setWf] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const pollRef = useRef(null);

  const load = async () => {
    try {
      setLoading(true);
      const [a, b] = await Promise.all([
        axios.get(`/api/workflows/${id}`),
        axios.get(`/api/workflows/${id}/runs`)
      ]);
      setWf(a.data);
      setRuns(b.data.runs || []);
    } catch (e) {
      toast.error('Failed to load workflow');
    } finally {
      setLoading(false);
    }
  };

  const loadRun = async (runId) => {
    try {
      const res = await axios.get(`/api/workflows/runs/${runId}`);
      setRuns(prev => prev.map(r => r.id === runId ? { ...r, detail: res.data } : r));
      return res.data;
    } catch (e) {
      return null;
    }
  };

  useEffect(() => { load(); return () => { if (pollRef.current) clearInterval(pollRef.current); }; }, [id]);

  const run = async () => {
    try {
      const res = await axios.post(`/api/workflows/${id}/run`, {});
      toast.success(`Run started (#${res.data.run_id})`);
      await load();
      // start polling latest run until completed
      setPolling(true);
      const latestId = res.data.run_id;
      pollRef.current = setInterval(async () => {
        const dr = await loadRun(latestId);
        if (dr && (dr.status === 'completed' || dr.status === 'failed' || dr.status === 'cancelled')) {
          clearInterval(pollRef.current);
          setPolling(false);
          toast.info(`Run #${latestId} ${dr.status}`);
          await load();
        }
      }, 1500);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to start run');
    }
  };

  return (
    <div className="container-fluid">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div>
          <button className="btn btn-link" onClick={() => navigate('/workflows')}><i className="bi bi-arrow-left"></i></button>
          <h3 className="d-inline ms-2">Workflow</h3>
        </div>
        <div className="d-flex gap-2">
          <button className="btn btn-success" onClick={run} disabled={polling}><i className="bi bi-play-fill me-1"></i>{polling ? 'Running...' : 'Run'}</button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-5"><div className="spinner-border text-primary" role="status"><span className="visually-hidden">Loading...</span></div></div>
      ) : !wf ? (
        <div className="alert alert-danger">Workflow not found</div>
      ) : (
        <>
          <div className="card mb-3 shadow-sm">
            <div className="card-body">
              <h5 className="mb-1">{wf.name}</h5>
              <div className="text-muted mb-2">{wf.description || 'No description'}</div>
              <div className="row g-3">
                <div className="col-md-6">
                  <h6>Nodes</h6>
                  <ul className="list-group">
                    {(wf.nodes || []).map(n => (
                      <li key={n.id} className="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                          <strong>{n.name}</strong>
                          <div className="small text-muted">script: {n.script_id || '-'} | target: {n.target_type || '-'} {n.target_id || ''}</div>
                        </div>
                        <span className="badge bg-secondary">{n.key}</span>
                      </li>
                    ))}
                  </ul>
                </div>
                <div className="col-md-6">
                  <h6>Edges</h6>
                  <ul className="list-group">
                    {(wf.edges || []).map(e => (
                      <li key={e.id} className="list-group-item">
                        {e.source_node_id} -- <span className="badge bg-info text-dark">{e.condition}</span> --> {e.target_node_id}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          </div>

          <div className="card shadow-sm">
            <div className="card-body">
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h5 className="mb-0">Recent Runs</h5>
                <button className="btn btn-outline-secondary btn-sm" onClick={load}><i className="bi bi-arrow-clockwise"></i></button>
              </div>
              {(runs || []).length === 0 ? (
                <div className="text-muted">No runs yet.</div>
              ) : (
                <div className="table-responsive">
                  <table className="table table-sm table-hover">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Status</th>
                        <th>Started</th>
                        <th>Completed</th>
                        <th>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map(r => (
                        <tr key={r.id}>
                          <td>{r.id}</td>
                          <td>
                            <span className={`badge ${r.status === 'completed' ? 'bg-success' : r.status === 'failed' ? 'bg-danger' : 'bg-secondary'}`}>{r.status}</span>
                          </td>
                          <td>{r.started_at ? new Date(r.started_at).toLocaleString() : '-'}</td>
                          <td>{r.completed_at ? new Date(r.completed_at).toLocaleString() : '-'}</td>
                          <td>
                            <div className="btn-group" role="group">
                              <button className="btn btn-outline-primary btn-sm" onClick={async ()=>{ const d = await loadRun(r.id); if(!d) toast.error('Failed to load run'); }}>
                                <i className="bi bi-eye"></i>
                              </button>
                              {r.status === 'running' && (
                                <button 
                                  className="btn btn-outline-success btn-sm" 
                                  onClick={() => navigate(`/workflow-run/${r.id}/monitor`)}
                                  title="Monitor Live Execution"
                                >
                                  <i className="bi bi-broadcast"></i>
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {(runs || []).filter(x=>x.detail).map(d => (
                <div key={`detail-${d.id}`} className="mt-3">
                  <div className="alert alert-secondary d-flex justify-content-between align-items-center">
                    <div className="fw-bold mb-0">Run #{d.id} Detail</div>
                    <span className={`badge ${d.detail.status === 'completed' ? 'bg-success' : d.detail.status === 'failed' ? 'bg-danger' : 'bg-secondary'}`}>{d.detail.status}</span>
                  </div>
                  <div className="list-group">
                    {(d.detail.nodes || []).map(nr => (
                      <div key={nr.id} className="list-group-item">
                        <div className="d-flex justify-content-between">
                          <div>
                            <strong>Node #{nr.node_id}</strong>
                            <div className="small text-muted">{nr.started_at ? new Date(nr.started_at).toLocaleString() : '-'} → {nr.completed_at ? new Date(nr.completed_at).toLocaleString() : '-'}</div>
                          </div>
                          <span className={`badge ${nr.status === 'completed' ? 'bg-success' : nr.status === 'failed' ? 'bg-danger' : 'bg-secondary'}`}>{nr.status}</span>
                        </div>
                        {nr.output && (
                          <pre className="mt-2" style={{whiteSpace:'pre-wrap'}}>{nr.output}</pre>
                        )}
                        {nr.error && (
                          <pre className="mt-2 text-danger" style={{whiteSpace:'pre-wrap'}}>{nr.error}</pre>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default WorkflowDetail;


