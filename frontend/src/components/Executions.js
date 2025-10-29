import React, { useEffect, useMemo, useState } from 'react';
import axios from 'axios';

const MultiSelectDropdown = ({ label, options, selectedIds, onChange }) => {
  const [open, setOpen] = useState(false);
  const toggle = () => setOpen(!open);
  const handleToggleId = (id) => {
    const sid = String(id);
    if (selectedIds.includes(sid)) {
      onChange(selectedIds.filter(x => x !== sid));
    } else {
      onChange([...selectedIds, sid]);
    }
  };
  const summary = selectedIds.length === 0 ? 'All' : `${selectedIds.length} selected`;
  return (
    <div className="dropdown" style={{position:'relative'}}>
      <button type="button" className="btn btn-sm w-100 text-start bg-dark text-light border border-secondary" onClick={toggle}>
        {label}: {summary}
        <i className="bi bi-caret-down-fill float-end"></i>
      </button>
      {open && (
        <div className="dropdown-menu dropdown-menu-dark show w-100" style={{maxHeight:'240px', overflow:'auto'}}>
          <button type="button" className="dropdown-item" onClick={() => { onChange([]); setOpen(false); }}>All</button>
          <div className="dropdown-divider"></div>
          {options.map(opt => (
            <label key={opt.id} className="dropdown-item d-flex align-items-center" style={{cursor:'pointer'}}>
              <input
                type="checkbox"
                className="form-check-input me-2"
                checked={selectedIds.includes(String(opt.id))}
                onChange={() => handleToggleId(opt.id)}
              />
              <span>{opt.name}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  );
};

const Executions = () => {
  const formatInTimezone = (utcDateString, tz) => {
    if (!utcDateString) return '—';
    try {
      // Treat backend timestamps as UTC if they lack timezone info
      const needsZ = typeof utcDateString === 'string' && !/Z|[\+\-]\d{2}:?\d{2}$/.test(utcDateString);
      const iso = needsZ ? `${utcDateString}Z` : utcDateString;
      const d = new Date(iso);
      const targetTz = tz || (Intl && Intl.DateTimeFormat().resolvedOptions().timeZone) || undefined;
      return d.toLocaleString(undefined, {
        timeZone: targetTz,
        year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit'
      });
    } catch (e) {
      try { return new Date(utcDateString).toLocaleString(); } catch { return String(utcDateString); }
    }
  };
  const [executions, setExecutions] = useState([]);
  const [scripts, setScripts] = useState([]);
  const [servers, setServers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadingExec, setLoadingExec] = useState(false);
  const [error, setError] = useState('');
  // Auto-refresh controls
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [refreshSeconds, setRefreshSeconds] = useState(5);
  // Expanded rows (accordion-style)
  const [expandedExecIds, setExpandedExecIds] = useState([]);
  const isExpanded = (id) => expandedExecIds.includes(String(id));
  const toggleExpanded = (id) => {
    const sid = String(id);
    setExpandedExecIds(prev => prev.includes(sid) ? prev.filter(x => x !== sid) : [...prev, sid]);
  };

  // Live streaming state per execution
  const [liveStreams, setLiveStreams] = useState({}); // { [execId]: { ws, lines: [], status } }
  const startLiveStream = (ex) => {
    const key = String(ex.id || `${ex.script_id}-${ex.server_id}`);
    if (liveStreams[key]?.ws && liveStreams[key].ws.readyState === WebSocket.OPEN) return;
    const getApiBaseUrl = () => {
      if (process.env.REACT_APP_API_URL) {
        return process.env.REACT_APP_API_URL;
      }
      const hostname = window.location.hostname;
      if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:8000';
      } else {
        return `http://${hostname}:8000`;
      }
    };
    const API_BASE_URL = getApiBaseUrl();
    const wsUrl = `ws://${API_BASE_URL.replace('http://', '')}/api/ws/execute/${ex.script?.id || ex.script_id}/${ex.server?.id || ex.server_id}`;
    const ws = new WebSocket(wsUrl);
    setLiveStreams(prev => ({ ...prev, [key]: { ws, lines: [], status: 'connecting' } }));
    ws.onopen = () => {
      setLiveStreams(prev => ({ ...prev, [key]: { ...prev[key], status: 'streaming' } }));
    };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'output' || msg.type === 'error_output') {
          setLiveStreams(prev => {
            const cur = prev[key] || { ws: null, lines: [], status: 'streaming' };
            return { ...prev, [key]: { ...cur, lines: [...cur.lines, msg.data] } };
          });
        } else if (msg.type === 'finished') {
          setLiveStreams(prev => ({ ...prev, [key]: { ...prev[key], status: msg.status || 'finished' } }));
          ws.close();
          // refresh executions to pick up final output
          refresh();
        } else if (msg.type === 'error') {
          setLiveStreams(prev => ({ ...prev, [key]: { ...prev[key], status: 'error' } }));
        }
      } catch (e) { /* ignore */ }
    };
    ws.onerror = () => {
      setLiveStreams(prev => ({ ...prev, [key]: { ...prev[key], status: 'error' } }));
    };
    ws.onclose = () => {
      setLiveStreams(prev => ({ ...prev, [key]: { ...prev[key], ws: null } }));
    };
  };
  const stopLiveStream = (ex) => {
    const key = String(ex.id || `${ex.script_id}-${ex.server_id}`);
    const ws = liveStreams[key]?.ws;
    if (ws) {
      try { ws.close(); } catch {}
    }
  };

  const stopExecution = async (executionId) => {
    try {
      setLoadingExec(true);
      await axios.post(`/api/scripts/executions/${executionId}/stop`);
      // Refresh executions to show updated status
      await refresh();
    } catch (error) {
      setError(error.response?.data?.detail || error.message);
    } finally {
      setLoadingExec(false);
    }
  };

  const exportExecutions = async (format) => {
    try {
      const params = {};
      // Export API supports a single status_filter; if multiple selected, omit to export all
      if (filterStatuses && filterStatuses.length === 1) params.status_filter = filterStatuses[0];
      if (filterScriptIds.length>0) params.script_ids = filterScriptIds.join(',');
      if (filterServerIds.length>0) params.server_ids = filterServerIds.join(',');
      if (filterGroupIds.length>0) params.group_ids = filterGroupIds.join(',');
      if (filterFromDate) params.from_date = filterFromDate;
      if (filterToDate) params.to_date = filterToDate;
      params.format = format;

      const res = await axios.get('/api/scripts/executions/export', {
        params,
        responseType: 'blob'
      });
      const blob = new Blob([res.data], { type: format === 'csv' ? 'text/csv' : 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = format === 'csv' ? 'executions.csv' : 'executions.json';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Export failed', e);
      alert('Export failed');
    }
  };

  // Multi-select filter state
  const [filterScriptIds, setFilterScriptIds] = useState([]);
  const [filterServerIds, setFilterServerIds] = useState([]);
  const [filterGroupIds, setFilterGroupIds] = useState([]);

  // Merge API groups with any groups observed in executions
  const mergedGroups = useMemo(() => {
    const map = new Map();
    (groups || []).forEach(g => { if (g) map.set(String(g.id ?? g.name), { id: g.id ?? g.name, name: g.name }); });
    (servers || []).forEach(s => (s?.groups || []).forEach(g => { if (g) map.set(String(g.id ?? g.name), { id: g.id ?? g.name, name: g.name }); }));
    (executions || []).forEach(ex => {
      (ex.server_groups || []).forEach(g => { if (g) map.set(String(g.id ?? g.name), { id: g.id ?? g.name, name: g.name }); });
      (ex.server?.groups || []).forEach(g => { if (g) map.set(String(g.id ?? g.name), { id: g.id ?? g.name, name: g.name }); });
    });
    return Array.from(map.values()).sort((a,b)=> String(a.name).localeCompare(String(b.name)));
  }, [groups, servers, executions]);
  // Multi status filter
  const statusOptions = useMemo(() => (
    [
      { id: 'completed', name: 'Completed' },
      { id: 'running', name: 'Running' },
      { id: 'long_running', name: 'Long Running' },
      { id: 'cancelled', name: 'Cancelled' },
      { id: 'failed', name: 'Failed' },
    ]
  ), []);
  const [filterStatuses, setFilterStatuses] = useState([]); // array of status ids
  const [filterFromDate, setFilterFromDate] = useState('');
  const [filterToDate, setFilterToDate] = useState('');

  useEffect(() => {
    const init = async () => {
      try {
        setLoading(true);
        const [scr, srv, grp, ex] = await Promise.all([
          axios.get('/api/scripts/'),
          axios.get('/api/servers/'),
          axios.get('/api/server-groups/'),
          axios.get('/api/scripts/executions/latest')
        ]);
        setScripts(scr.data.scripts || []);
        setServers(srv.data.servers || []);
        setGroups(grp.data.groups || []);
        const combined = (ex.data.executions || []).sort((a,b)=> (b?.id||0) - (a?.id||0));
        setExecutions(combined);
      } catch (e) {
        setError('Failed to load executions');
        console.error(e);
      } finally {
        setLoading(false);
      }
    };
    init();
  }, []);

  const refresh = async () => {
    try {
      setLoadingExec(true);
      const ex = await axios.get('/api/scripts/executions/latest');
      const finalItems = (ex.data.executions || []).sort((a,b)=> (b?.id||0) - (a?.id||0));
      // debug: surface count
      try { console.debug('[Executions] fetched', finalItems.length, 'rows'); } catch {}
      setExecutions(finalItems);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingExec(false);
    }
  };

  // Polling effect
  useEffect(() => {
    if (!autoRefresh) return;
    const intervalMs = Math.max(2, Number(refreshSeconds) || 5) * 1000;
    const id = setInterval(() => { refresh(); }, intervalMs);
    return () => clearInterval(id);
  }, [autoRefresh, refreshSeconds]);

  if (loading) {
    return (
      <div className="main-content"><div className="container-fluid"><div className="text-center"><div className="spinner-border text-primary" role="status"><span className="visually-hidden">Loading...</span></div></div></div></div>
    );
  }

  return (
    <div className="main-content">
      <div className="container-fluid">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h1><i className="bi bi-clock-history me-3"></i>Executions <span className="badge bg-secondary ms-2" title="Loaded rows">{executions.length}</span></h1>
          <div className="d-flex align-items-center gap-2">
            <div className="form-check form-switch">
              <input className="form-check-input" type="checkbox" id="autoRefreshSwitch" checked={autoRefresh} onChange={(e)=> setAutoRefresh(e.target.checked)} />
              <label className="form-check-label" htmlFor="autoRefreshSwitch">Auto-refresh</label>
            </div>
            <div className="input-group input-group-sm" style={{width:'120px'}}>
              <span className="input-group-text">Every</span>
              <input type="number" min="2" max="60" className="form-control bg-dark text-light border border-secondary" value={refreshSeconds} onChange={(e)=> setRefreshSeconds(e.target.value)} />
              <span className="input-group-text">s</span>
            </div>
            <button type="button" className="btn btn-sm btn-outline-light" onClick={refresh} title="Refresh now">
              <i className="bi bi-arrow-clockwise"></i>
            </button>
          </div>
        </div>

        {error && (
          <div className="alert alert-danger border-0" role="alert" style={{backgroundColor: 'rgba(239, 68, 68, 0.1)'}}>
            <i className="bi bi-exclamation-circle me-2"></i>{error}
          </div>
        )}

        <div className="card shadow-lg">
          <div className="card-header d-flex flex-wrap gap-2 align-items-center">
            <label className="form-label mb-0 me-2">Date range:</label>
            <input type="date" className="form-control form-control-sm bg-dark text-light border border-secondary" style={{maxWidth:'180px'}} value={filterFromDate} onChange={(e)=>setFilterFromDate(e.target.value)} />
            <span className="text-muted">to</span>
            <input type="date" className="form-control form-control-sm bg-dark text-light border border-secondary" style={{maxWidth:'180px'}} value={filterToDate} onChange={(e)=>setFilterToDate(e.target.value)} />
          </div>
          <div className="card-body">
            <div className="table-responsive" style={{overflow: 'visible'}}>
              <table className="table table-sm table-hover table-striped">
                <thead>
                  <tr>
                    <th>Script</th>
                    <th>Server</th>
                    <th>Groups</th>
                    <th>Status</th>
                    <th>Started</th>
                    <th>Completed</th>
                    <th className="text-center">Details</th>
                  </tr>
                  <tr>
                    <th>
                      <MultiSelectDropdown label="Scripts" options={scripts} selectedIds={filterScriptIds} onChange={setFilterScriptIds} />
                    </th>
                    <th>
                      <MultiSelectDropdown label="Servers" options={servers} selectedIds={filterServerIds} onChange={setFilterServerIds} />
                    </th>
                    <th>
                      <MultiSelectDropdown label="Groups" options={mergedGroups} selectedIds={filterGroupIds} onChange={setFilterGroupIds} />
                    </th>
                    <th>
                      <MultiSelectDropdown label="Status" options={statusOptions} selectedIds={filterStatuses} onChange={setFilterStatuses} />
                    </th>
                    <th></th>
                    <th></th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {[...executions]
                    .sort((a,b) => (b?.id || 0) - (a?.id || 0))
                    .filter(ex => filterStatuses.length === 0 || filterStatuses.includes(String(ex.status)))
                    .filter(ex => filterScriptIds.length === 0 || filterScriptIds.includes(String(ex.script_id)) || (ex.script && filterScriptIds.includes(String(ex.script.id))))
                    .filter(ex => filterServerIds.length === 0 || filterServerIds.includes(String(ex.server_id)) || (ex.server && filterServerIds.includes(String(ex.server.id))))
                    .filter(ex => {
                      if (filterGroupIds.length === 0) return true;
                      const fallbackServer = servers.find(s => s.id === ex.server_id);
                      const gs = (ex.server_groups && ex.server_groups.length>0)
                        ? ex.server_groups
                        : ((ex.server?.groups && ex.server.groups.length>0)
                            ? ex.server.groups
                            : (fallbackServer?.groups || []));
                      const ids = gs.map(g => String(g.id ?? g.group_id ?? g.name));
                      return filterGroupIds.some(id => ids.includes(id));
                    })
                    .filter(ex => {
                      if (!filterFromDate && !filterToDate) return true;
                      const ts = ex.started_at ? new Date(ex.started_at) : null;
                      if (!ts) return false;
                      const fromOk = filterFromDate ? ts >= new Date(filterFromDate) : true;
                      const toOk = filterToDate ? ts <= new Date(filterToDate + 'T23:59:59') : true;
                      return fromOk && toOk;
                    })
                    .map(ex => (
                    <React.Fragment key={ex.id}>
                      <tr>
                        <td>{ex.script?.name || (scripts.find(s=> s.id === ex.script_id)?.name) || '—'}</td>
                        <td>{ex.server?.name || (servers.find(s=> s.id === ex.server_id)?.name) || '—'}</td>
                        <td>
                          {(() => {
                            const fallbackServer = servers.find(s => s.id === ex.server_id);
                            const gs = (ex.server_groups && ex.server_groups.length>0)
                              ? ex.server_groups
                              : ((ex.server?.groups && ex.server.groups.length>0)
                                  ? ex.server.groups
                                  : (fallbackServer?.groups || []));
                            return (gs && gs.length>0) ? (
                              <div className="d-flex flex-wrap gap-1">
                                {gs.map(g => {
                                  const key = g.id ?? g.group_id ?? g.name;
                                  const name = g.name ?? String(key);
                                  const color = g.color ?? '#6c757d';
                                  return (
                                    <span
                                      key={key}
                                      className="badge"
                                      style={{
                                        backgroundColor: color,
                                        color: '#fff'
                                      }}
                                    >
                                      {name}
                                    </span>
                                  );
                                })}
                              </div>
                            ) : (<span className="text-muted">—</span>);
                          })()}
                        </td>
                        <td>
                          <span className={`badge ${ex.status === 'completed' ? 'bg-success' : ex.status === 'running' ? 'bg-warning' : ex.status === 'long_running' ? 'bg-warning' : ex.status === 'cancelled' ? 'bg-secondary' : 'bg-danger'}`}>{ex.status}</span>
                        </td>
                        <td title={ex.server?.timezone ? `Server TZ: ${ex.server.timezone}` : ''}>{formatInTimezone(ex.started_at, ex.server?.timezone)}</td>
                        <td title={ex.server?.timezone ? `Server TZ: ${ex.server.timezone}` : ''}>{formatInTimezone(ex.completed_at, ex.server?.timezone)}</td>
                        <td className="text-center">
                          <div className="d-flex gap-1 justify-content-center">
                            <button
                              type="button"
                              className="btn btn-outline-info btn-sm"
                              onClick={() => toggleExpanded(ex.id)}
                              title="View stdout/stderr"
                            >
                              <i className="bi bi-chevron-down me-1" style={{transform: isExpanded(ex.id) ? 'rotate(180deg)' : 'none', transition:'transform .2s'}}></i>
                              Details
                            </button>
                            {(ex.status === 'running' || ex.status === 'long_running') && (
                              <button
                                type="button"
                                className="btn btn-outline-danger btn-sm"
                                onClick={() => stopExecution(ex.id)}
                                title="Stop execution"
                              >
                                <i className="bi bi-stop-fill me-1"></i>
                                Stop
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {isExpanded(ex.id) && (
                        <tr>
                          <td colSpan="7" style={{background:'var(--bg-card)'}}>
                            <div className="p-3" style={{border:'1px solid #333', borderRadius:'4px'}}>
                              <div className="mb-2 small text-muted d-flex flex-wrap gap-3">
                                <div><strong>Script:</strong> {ex.script?.name || (scripts.find(s=> s.id === ex.script_id)?.name) || '—'}</div>
                                <div><strong>Server:</strong> {ex.server?.name || (servers.find(s=> s.id === ex.server_id)?.name) || '—'}</div>
                                <div><strong>Status:</strong> {ex.status}</div>
                                <div><strong>Started:</strong> {formatInTimezone(ex.started_at, ex.server?.timezone)} {ex.server?.timezone ? `(${ex.server.timezone})` : ''}</div>
                                <div><strong>Completed:</strong> {formatInTimezone(ex.completed_at, ex.server?.timezone)} {ex.server?.timezone ? `(${ex.server.timezone})` : ''}</div>
                              </div>
                              <div className="row g-3">
                                <div className="col-12 col-lg-6">
                                  <h6 className="mb-2">Stdout</h6>
                                  <pre className="p-2" style={{minHeight:'140px', background:'var(--bg-tertiary)', color:'var(--text-primary)', border:'1px solid var(--border-primary)', borderRadius:'4px', whiteSpace:'pre-wrap'}}>
                                    {ex.output ? String(ex.output) : '—'}
                                  </pre>
                                </div>
                                <div className="col-12 col-lg-6">
                                  <h6 className="mb-2">Stderr</h6>
                                  <pre className="p-2" style={{minHeight:'140px', background:'var(--bg-tertiary)', color:'var(--text-primary)', border:'1px solid var(--border-primary)', borderRadius:'4px', whiteSpace:'pre-wrap'}}>
                                    {ex.error ? String(ex.error) : '—'}
                                  </pre>
                                </div>
                              </div>
                              <div className="mt-3">
                                <div className="d-flex align-items-center gap-2">
                                  <button className="btn btn-outline-success" onClick={()=> startLiveStream(ex)}>
                                    <i className="bi bi-broadcast me-1"></i>
                                    Run Live
                                  </button>
                                  <button className="btn btn-outline-secondary" onClick={()=> stopLiveStream(ex)}>
                                    Stop
                                  </button>
                                </div>
                                {(() => {
                                  const key = String(ex.id || `${ex.script_id}-${ex.server_id}`);
                                  const stream = liveStreams[key];
                                  if (!stream) return null;
                                  return (
                                    <div className="mt-2" style={{border:'1px dashed #555', borderRadius:'4px'}}>
                                      <div className="px-2 py-1 small text-muted">Live output ({stream.status || '...'})</div>
                                      <pre className="p-2 mb-0" style={{minHeight:'120px', maxHeight:'260px', overflowY:'auto', background:'var(--bg-primary)', color:'var(--text-primary)', whiteSpace:'pre-wrap'}}>
                                        {(stream.lines || []).join('')}
                                      </pre>
                                    </div>
                                  );
                                })()}
                              </div>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                  {executions
                    .filter(ex => filterStatuses.length === 0 || filterStatuses.includes(String(ex.status)))
                    .filter(ex => filterScriptIds.length === 0 || filterScriptIds.includes(String(ex.script_id)) || (ex.script && filterScriptIds.includes(String(ex.script.id))))
                    .filter(ex => filterServerIds.length === 0 || filterServerIds.includes(String(ex.server_id)) || (ex.server && filterServerIds.includes(String(ex.server.id))))
                    .filter(ex => {
                      if (filterGroupIds.length === 0) return true;
                      const fallbackServer = servers.find(s => s.id === ex.server_id);
                      const gs = (ex.server_groups && ex.server_groups.length>0)
                        ? ex.server_groups
                        : ((ex.server?.groups && ex.server.groups.length>0)
                            ? ex.server.groups
                            : (fallbackServer?.groups || []));
                      const ids = gs.map(g => String(g.id ?? g.group_id ?? g.name));
                      return filterGroupIds.some(id => ids.includes(id));
                    })
                    .filter(ex => {
                      if (!filterFromDate && !filterToDate) return true;
                      const ts = ex.started_at ? new Date(ex.started_at) : null;
                      if (!ts) return false;
                      const fromOk = filterFromDate ? ts >= new Date(filterFromDate) : true;
                      const toOk = filterToDate ? ts <= new Date(filterToDate + 'T23:59:59') : true;
                      return fromOk && toOk;
                    }).length === 0 && (
                    <tr>
                      <td colSpan="7" className="text-center text-muted">No executions match filters</td>
                    </tr>
                  )}
                </tbody>
              </table>
              <div className="d-flex justify-content-end mt-2">
                <div className="btn-group" role="group">
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-light"
                    onClick={() => exportExecutions('csv')}
                    title="Export CSV"
                  >
                    <i className="bi bi-download me-1"></i>CSV
                  </button>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-light"
                    onClick={() => exportExecutions('json')}
                    title="Export JSON"
                  >
                    <i className="bi bi-filetype-json me-1"></i>JSON
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Executions;


