import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell, BarChart, Bar, Legend } from 'recharts';

const Dashboard = () => {
  const { user } = useAuth();
  const [error, setError] = useState('');
  const [showErrorToast, setShowErrorToast] = useState(false);
  const [stats, setStats] = useState({ servers: 0, groups: 0, scripts: 0, schedules: 0 });
  const [prevStats, setPrevStats] = useState(null);
  const [recentExecs, setRecentExecs] = useState([]);
  const [failingExecs, setFailingExecs] = useState([]);
  const [upcomingSchedules, setUpcomingSchedules] = useState([]);
  const [rangeDays, setRangeDays] = useState(30); // fixed range
  const [scriptNameById, setScriptNameById] = useState({});
  const [serverNameById, setServerNameById] = useState({});
  const [serverHealth, setServerHealth] = useState([]);
  const [showHealthDetails, setShowHealthDetails] = useState(false);
  const [checkingAllHealth, setCheckingAllHealth] = useState(false);
  const [systemHealth, setSystemHealth] = useState(null);
  const [showSystemHealth, setShowSystemHealth] = useState(false);

  useEffect(() => {
    const init = async () => {
      setError('');
      const results = await Promise.allSettled([
        axios.get('/api/servers/'),
        axios.get('/api/server-groups/'),
        axios.get('/api/scripts/'),
        axios.get('/api/schedules/'),
        axios.get('/api/scripts/executions/'),
        axios.get('/api/health/summary'),
        axios.get('/api/health')
      ]);
      const getData = (res) => (res.status === 'fulfilled' ? res.value.data : null);
      const srv = getData(results[0]);
      const grp = getData(results[1]);
      const scr = getData(results[2]);
      const sch = getData(results[3]);
      const ex = getData(results[4]);
      const health = getData(results[5]);
      const sysHealth = getData(results[6]);
      const newStats = {
        servers: (srv?.servers || []).length,
        groups: (grp?.groups || []).length,
        scripts: (scr?.scripts || []).length,
        schedules: (sch?.schedules || []).length
      };
      setPrevStats(prev => (prev ? prev : null));
      setStats(newStats);
      const executions = ex?.executions || [];
      setRecentExecs(executions);
      setFailingExecs(executions.filter(e => e.status === 'failed'));
      // Build name lookup maps for fallbacks
      const scriptMap = Object.fromEntries(((scr?.scripts) || []).map(s => [s.id, s.name]));
      const serverMap = Object.fromEntries(((srv?.servers) || []).map(s => [s.id, s.name]));
      setScriptNameById(scriptMap);
      setServerNameById(serverMap);
      setServerHealth(health || []);
      setSystemHealth(sysHealth);
      const schItems = (sch?.schedules || [])
        .filter(s => s.enabled)
        .sort((a,b)=> new Date(a.next_run_at||0) - new Date(b.next_run_at||0))
        .slice(0, 5);
      setUpcomingSchedules(schItems);
      const hadFailures = results.some(r => r.status === 'rejected');
      if (hadFailures) {
        setError('Some dashboard data failed to load.');
        setShowErrorToast(true);
        // eslint-disable-next-line no-console
        console.error('Dashboard fetch failures:', results);
      }
    };
    init();
  }, [user]);

  // Auto refresh every 60s
  useEffect(() => {
    const t = setInterval(() => {
      // re-run the same init logic in a lightweight way
      (async () => {
        const res = await Promise.allSettled([
          axios.get('/api/scripts/executions/'),
          axios.get('/api/schedules/'),
          axios.get('/api/health')
        ]);
        const getData = r => (r.status === 'fulfilled' ? r.value.data : null);
        const ex = getData(res[0]);
        const sch = getData(res[1]);
        const sysHealth = getData(res[2]);
        if (ex?.executions) {
          setRecentExecs(ex.executions);
          setFailingExecs(ex.executions.filter(e => e.status === 'failed'));
        }
        if (sch?.schedules) {
          const schItems = (sch.schedules || [])
            .filter(s => s.enabled)
            .sort((a,b)=> new Date(a.next_run_at||0) - new Date(b.next_run_at||0))
            .slice(0, 5);
          setUpcomingSchedules(schItems);
        }
        if (sysHealth) {
          setSystemHealth(sysHealth);
        }
      })();
    }, 60000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    if (error) {
      setShowErrorToast(true);
      const t = setTimeout(() => setShowErrorToast(false), 5000);
      return () => clearTimeout(t);
    }
  }, [error]);

  const checkAllServersHealth = async () => {
    if (user.role !== 'admin') {
      alert('Only admins can trigger health checks');
      return;
    }

    try {
      setCheckingAllHealth(true);
      const response = await axios.post('/api/health/check-all');
      // Refresh health data
      const healthResponse = await axios.get('/api/health/summary');
      setServerHealth(healthResponse.data);
    } catch (error) {
      console.error('Failed to check all servers health:', error);
      alert('Failed to check all servers health');
    } finally {
      setCheckingAllHealth(false);
    }
  };

  const checkSingleServerHealth = async (serverId) => {
    try {
      await axios.post(`/api/servers/${serverId}/health/check`);
      // Refresh health data
      const healthResponse = await axios.get('/api/health/summary');
      setServerHealth(healthResponse.data);
    } catch (error) {
      console.error('Failed to check server health:', error);
      alert('Failed to check server health');
    }
  };

  const getHealthStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'warning': return 'warning';
      case 'critical': return 'danger';
      default: return 'secondary';
    }
  };

  const getHealthStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return 'bi-check-circle-fill';
      case 'warning': return 'bi-exclamation-triangle-fill';
      case 'critical': return 'bi-x-circle-fill';
      default: return 'bi-question-circle-fill';
    }
  };

  const getSystemHealthStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'success';
      case 'warning': return 'warning';
      case 'unhealthy': return 'danger';
      default: return 'secondary';
    }
  };

  const getSystemHealthStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return 'bi-check-circle-fill';
      case 'warning': return 'bi-exclamation-triangle-fill';
      case 'unhealthy': return 'bi-x-circle-fill';
      default: return 'bi-question-circle-fill';
    }
  };

  const formatUptime = (seconds) => {
    if (!seconds) return 'Unknown';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  const formatLocal = (v) => {
    if (!v) return '—';
    try {
      const s = typeof v === 'string' ? v : String(v);
      const hasOffset = /[\+\-]\d{2}:?\d{2}$/.test(s) || s.endsWith('Z');
      let normalized = s;
      if (!hasOffset) {
        if (s.includes('T')) normalized = s + 'Z';
        else normalized = s.replace(' ', 'T') + 'Z';
      }
      const d = new Date(normalized);
      if (isNaN(d.getTime())) return s;
      return new Intl.DateTimeFormat(undefined, {
        timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
      }).format(d);
    } catch (e) {
      return String(v);
    }
  };

  // Chart data
  const executionsByDay = useMemo(() => {
    const map = new Map();
    const cutoff = new Date(Date.now() - rangeDays * 24 * 3600 * 1000);
    (recentExecs || []).forEach(ex => {
      if (!ex.started_at) return;
      const d = new Date(ex.started_at);
      if (d < cutoff) return;
      const key = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
      map.set(key, (map.get(key) || 0) + 1);
    });
    return Array.from(map.entries()).sort((a,b)=> a[0].localeCompare(b[0])).map(([date, count]) => ({ date, count }));
  }, [recentExecs, rangeDays]);

  const statusDistribution = useMemo(() => {
    const counts = { completed: 0, running: 0, failed: 0 };
    const cutoff = new Date(Date.now() - rangeDays * 24 * 3600 * 1000);
    (recentExecs || []).forEach(ex => {
      if (!ex.started_at) return;
      if (new Date(ex.started_at) < cutoff) return;
      if (counts[ex.status] !== undefined) counts[ex.status]++;
    });
    return [
      { name: 'Completed', value: counts.completed, key: 'completed' },
      { name: 'Running', value: counts.running, key: 'running' },
      { name: 'Failed', value: counts.failed, key: 'failed' }
    ];
  }, [recentExecs, rangeDays]);

  const topScripts = useMemo(() => {
    const map = new Map();
    const cutoff = new Date(Date.now() - rangeDays * 24 * 3600 * 1000);
    (recentExecs || []).forEach(ex => {
      const name = ex.script?.name || String(ex.script_id);
      if (!ex.started_at || new Date(ex.started_at) < cutoff) return;
      map.set(name, (map.get(name) || 0) + 1);
    });
    return Array.from(map.entries()).map(([name, count]) => ({ name, count }))
      .sort((a,b)=> b.count - a.count).slice(0, 7);
  }, [recentExecs, rangeDays]);

  const next24hBuckets = useMemo(() => {
    const now = new Date();
    const buckets = Array.from({ length: 24 }).map((_, i) => {
      const hour = new Date(now.getTime() + i * 3600 * 1000).getHours();
      return { hour: `${String(hour).padStart(2,'0')}:00`, count: 0 };
    });
    (upcomingSchedules || []).forEach(s => {
      if (!s.next_run_at) return;
      const t = new Date(s.next_run_at);
      const diffH = Math.floor((t.getTime() - now.getTime()) / 3600000);
      if (diffH >= 0 && diffH < 24) buckets[diffH].count += 1;
    });
    return buckets;
  }, [upcomingSchedules]);

  return (
    <div className="main-content">
      <div className="container-fluid">
        <div className="row">
          <div className="col-12">
            <div className="card shadow-lg">
              <div className="card-body">
                <h1 className="h3 mb-4">
                  <i className="bi bi-terminal me-3"></i>
                  Welcome to biRun
                </h1>
                {/* Error toast */}
                {showErrorToast && (
                  <div style={{position:'fixed', top:'1rem', right:'1rem', zIndex:1055}}>
                    <div className="toast show" role="alert" aria-live="assertive" aria-atomic="true" style={{minWidth:'280px'}}>
                      <div className="toast-header">
                        <i className="bi bi-exclamation-triangle-fill text-warning me-2"></i>
                        <strong className="me-auto">Dashboard</strong>
                        <small className="text-muted">now</small>
                        <button type="button" className="btn-close btn-close-white ms-2 mb-1" aria-label="Close" onClick={()=> setShowErrorToast(false)}></button>
                      </div>
                      <div className="toast-body">
                        {error}
                      </div>
                    </div>
                  </div>
                )}

                <div className="d-flex justify-content-between align-items-center mb-3">
                  <div className="row g-3 g-lg-4 flex-grow-1">
                    {[{k:'servers',label:'Servers',icon:'server',to:'/servers'},{k:'groups',label:'Groups',icon:'collection',to:'/server-groups'},{k:'scripts',label:'Scripts',icon:'code-square',to:'/scripts'},{k:'schedules',label:'Schedules',icon:'alarm',to:'/schedules'}].map(tile => (
                      <div className="col-6 col-md-3" key={tile.k}>
                        <Link to={tile.to} className="text-decoration-none">
                          <div className="card h-100 border-0">
                            <div className="card-body d-flex align-items-center justify-content-between">
                              <div>
                                <div className="text-muted small">{tile.label}</div>
                                <div className="h3 mb-0" style={{color:'var(--text-primary)'}}>{stats[tile.k]}</div>
                                <div className="small mt-1">
                                  {(() => {
                                    const current = stats[tile.k] || 0;
                                    const prev = prevStats ? (prevStats[tile.k] || 0) : null;
                                    if (prev === null) {
                                      return <span className="text-muted">—</span>;
                                    }
                                    const diff = current - prev;
                                    const isUp = diff > 0;
                                    const isDown = diff < 0;
                                    const cls = isUp ? 'text-success' : (isDown ? 'text-danger' : 'text-secondary');
                                    const icon = isUp ? 'bi-arrow-up-right' : (isDown ? 'bi-arrow-down-right' : 'bi-dash');
                                    return (
                                      <span className={cls}>
                                        <i className={`bi ${icon} me-1`}></i>
                                        {diff === 0 ? '0' : (diff > 0 ? `+${diff}` : `${diff}`)}
                                      </span>
                                    );
                                  })()}
                                </div>
                              </div>
                              <i className={`bi bi-${tile.icon}`} style={{fontSize:'1.75rem', color:'var(--text-secondary)'}}></i>
                            </div>
                          </div>
                        </Link>
                      </div>
                    ))}
                  </div>
                  {/* removed range selector (7d | 30d | 90d) */}
                </div>

                {/* System Health Section */}
                {user?.role === 'admin' && systemHealth && (
                  <div className="row mt-4">
                    <div className="col-12">
                      <div className="card border-0">
                        <div className="card-body">
                          <div className="d-flex justify-content-between align-items-center mb-3">
                            <h5 className="card-title mb-0">
                              <i className="bi bi-gear me-2"></i>System Health
                            </h5>
                            <div>
                              <button 
                                className="btn btn-sm btn-outline-primary me-2" 
                                onClick={() => setShowSystemHealth(!showSystemHealth)}
                              >
                                <i className={`bi bi-chevron-${showSystemHealth ? 'up' : 'down'} me-1`}></i>
                                {showSystemHealth ? 'Hide Details' : 'Show Details'}
                              </button>
                              <span className={`badge bg-${getSystemHealthStatusColor(systemHealth.overall_status)} fs-6`}>
                                <i className={`bi ${getSystemHealthStatusIcon(systemHealth.overall_status)} me-1`}></i>
                                {systemHealth.overall_status?.toUpperCase()}
                              </span>
                            </div>
                          </div>

                          {showSystemHealth ? (
                            <div className="row g-3">
                              <div className="col-md-4">
                                <div className="card bg-dark border-secondary h-100">
                                  <div className="card-header d-flex justify-content-between align-items-center">
                                    <h6 className="mb-0">Database</h6>
                                    <span className={`badge bg-${getSystemHealthStatusColor(systemHealth.components?.database?.status)}`}>
                                      <i className={`bi ${getSystemHealthStatusIcon(systemHealth.components?.database?.status)} me-1`}></i>
                                      {systemHealth.components?.database?.status}
                                    </span>
                                  </div>
                                  <div className="card-body">
                                    <div className="mb-2">
                                      <small className="text-muted">Response Time</small>
                                      <div className="fw-bold">{systemHealth.components?.database?.response_time_ms || 0}ms</div>
                                    </div>
                                    <div className="mb-2">
                                      <small className="text-muted">Status</small>
                                      <div className="fw-bold">{systemHealth.components?.database?.message || 'Unknown'}</div>
                                    </div>
                                    {systemHealth.components?.database?.error && (
                                      <div className="text-danger small">
                                        <i className="bi bi-exclamation-triangle me-1"></i>
                                        {systemHealth.components.database.error}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>

                              <div className="col-md-4">
                                <div className="card bg-dark border-secondary h-100">
                                  <div className="card-header d-flex justify-content-between align-items-center">
                                    <h6 className="mb-0">Redis</h6>
                                    <span className={`badge bg-${getSystemHealthStatusColor(systemHealth.components?.redis?.status)}`}>
                                      <i className={`bi ${getSystemHealthStatusIcon(systemHealth.components?.redis?.status)} me-1`}></i>
                                      {systemHealth.components?.redis?.status}
                                    </span>
                                  </div>
                                  <div className="card-body">
                                    <div className="mb-2">
                                      <small className="text-muted">Response Time</small>
                                      <div className="fw-bold">{systemHealth.components?.redis?.response_time_ms || 0}ms</div>
                                    </div>
                                    <div className="mb-2">
                                      <small className="text-muted">Version</small>
                                      <div className="fw-bold">{systemHealth.components?.redis?.redis_version || 'Unknown'}</div>
                                    </div>
                                    <div className="mb-2">
                                      <small className="text-muted">Memory</small>
                                      <div className="fw-bold">{systemHealth.components?.redis?.used_memory_human || 'Unknown'}</div>
                                    </div>
                                    <div className="mb-2">
                                      <small className="text-muted">Clients</small>
                                      <div className="fw-bold">{systemHealth.components?.redis?.connected_clients || 0}</div>
                                    </div>
                                    {systemHealth.components?.redis?.error && (
                                      <div className="text-danger small">
                                        <i className="bi bi-exclamation-triangle me-1"></i>
                                        {systemHealth.components.redis.error}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>

                              <div className="col-md-4">
                                <div className="card bg-dark border-secondary h-100">
                                  <div className="card-header d-flex justify-content-between align-items-center">
                                    <h6 className="mb-0">Worker Queue</h6>
                                    <span className={`badge bg-${getSystemHealthStatusColor(systemHealth.components?.worker_queue?.status)}`}>
                                      <i className={`bi ${getSystemHealthStatusIcon(systemHealth.components?.worker_queue?.status)} me-1`}></i>
                                      {systemHealth.components?.worker_queue?.status}
                                    </span>
                                  </div>
                                  <div className="card-body">
                                    <div className="mb-2">
                                      <small className="text-muted">Active Workers</small>
                                      <div className="fw-bold">{systemHealth.components?.worker_queue?.active_workers || 0}</div>
                                    </div>
                                    <div className="mb-2">
                                      <small className="text-muted">Queue Length</small>
                                      <div className="fw-bold">{systemHealth.components?.worker_queue?.queue_stats?.queue_length || 0}</div>
                                    </div>
                                    <div className="mb-2">
                                      <small className="text-muted">Failed Jobs</small>
                                      <div className="fw-bold">{systemHealth.components?.worker_queue?.queue_stats?.failed_jobs || 0}</div>
                                    </div>
                                    <div className="mb-2">
                                      <small className="text-muted">Response Time</small>
                                      <div className="fw-bold">{systemHealth.components?.worker_queue?.response_time_ms || 0}ms</div>
                                    </div>
                                    {systemHealth.components?.worker_queue?.error && (
                                      <div className="text-danger small">
                                        <i className="bi bi-exclamation-triangle me-1"></i>
                                        {systemHealth.components.worker_queue.error}
                                      </div>
                                    )}
                                  </div>
                                </div>
                              </div>

                              {systemHealth.system_metrics && (
                                <div className="col-12">
                                  <div className="card bg-dark border-secondary">
                                    <div className="card-header">
                                      <h6 className="mb-0">System Metrics</h6>
                                    </div>
                                    <div className="card-body">
                                      <div className="row g-3">
                                        <div className="col-md-3">
                                          <small className="text-muted">Max Concurrent Executions</small>
                                          <div className="fw-bold">{systemHealth.system_metrics.max_concurrent_executions || 0}</div>
                                        </div>
                                        <div className="col-md-3">
                                          <small className="text-muted">Current Running</small>
                                          <div className="fw-bold">{systemHealth.system_metrics.current_running_executions || 0}</div>
                                        </div>
                                        <div className="col-md-6">
                                          <small className="text-muted">Recent Executions (1h)</small>
                                          <div className="fw-bold">
                                            {systemHealth.system_metrics.recent_executions_1h ? 
                                              Object.entries(systemHealth.system_metrics.recent_executions_1h)
                                                .map(([status, count]) => `${status}: ${count}`)
                                                .join(', ') : 'None'
                                            }
                                          </div>
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="row g-2">
                              <div className="col-md-3">
                                <div className="d-flex align-items-center p-2 bg-dark rounded border border-secondary">
                                  <span className={`badge bg-${getSystemHealthStatusColor(systemHealth.components?.database?.status)} me-2`}>
                                    <i className={`bi ${getSystemHealthStatusIcon(systemHealth.components?.database?.status)}`}></i>
                                  </span>
                                  <div className="flex-grow-1">
                                    <div className="fw-bold">Database</div>
                                    <small className="text-muted">{systemHealth.components?.database?.response_time_ms || 0}ms</small>
                                  </div>
                                </div>
                              </div>
                              <div className="col-md-3">
                                <div className="d-flex align-items-center p-2 bg-dark rounded border border-secondary">
                                  <span className={`badge bg-${getSystemHealthStatusColor(systemHealth.components?.redis?.status)} me-2`}>
                                    <i className={`bi ${getSystemHealthStatusIcon(systemHealth.components?.redis?.status)}`}></i>
                                  </span>
                                  <div className="flex-grow-1">
                                    <div className="fw-bold">Redis</div>
                                    <small className="text-muted">{systemHealth.components?.redis?.response_time_ms || 0}ms</small>
                                  </div>
                                </div>
                              </div>
                              <div className="col-md-3">
                                <div className="d-flex align-items-center p-2 bg-dark rounded border border-secondary">
                                  <span className={`badge bg-${getSystemHealthStatusColor(systemHealth.components?.worker_queue?.status)} me-2`}>
                                    <i className={`bi ${getSystemHealthStatusIcon(systemHealth.components?.worker_queue?.status)}`}></i>
                                  </span>
                                  <div className="flex-grow-1">
                                    <div className="fw-bold">Workers</div>
                                    <small className="text-muted">{systemHealth.components?.worker_queue?.active_workers || 0} active</small>
                                  </div>
                                </div>
                              </div>
                              <div className="col-md-3">
                                <div className="d-flex align-items-center p-2 bg-dark rounded border border-secondary">
                                  <span className="text-muted">
                                    <i className="bi bi-clock me-1"></i>
                                    {systemHealth.total_response_time_ms || 0}ms total
                                  </span>
                                </div>
                              </div>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Server Health Section */}
                {user?.role === 'admin' && (
                  <div className="row mt-4">
                    <div className="col-12">
                      <div className="card border-0">
                        <div className="card-body">
                          <div className="d-flex justify-content-between align-items-center mb-3">
                            <h5 className="card-title mb-0">
                              <i className="bi bi-heart-pulse me-2"></i>Server Health
                            </h5>
                            <div>
                              <button 
                                className="btn btn-sm btn-outline-primary me-2" 
                                onClick={() => setShowHealthDetails(!showHealthDetails)}
                              >
                                <i className={`bi bi-chevron-${showHealthDetails ? 'up' : 'down'} me-1`}></i>
                                {showHealthDetails ? 'Hide Details' : 'Show Details'}
                              </button>
                              <button 
                                className="btn btn-sm btn-primary" 
                                onClick={checkAllServersHealth}
                                disabled={checkingAllHealth}
                              >
                                {checkingAllHealth ? (
                                  <>
                                    <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                    Checking...
                                  </>
                                ) : (
                                  <>
                                    <i className="bi bi-heart-pulse me-2"></i>Check All
                                  </>
                                )}
                              </button>
                            </div>
                          </div>

                          {showHealthDetails ? (
                            <div className="row g-3">
                              {serverHealth.length > 0 ? (
                                serverHealth.map((server) => (
                                  <div key={server.server_id} className="col-md-6 col-lg-4">
                                    <div className="card bg-dark border-secondary h-100">
                                      <div className="card-header d-flex justify-content-between align-items-center">
                                        <h6 className="mb-0">{server.server_name}</h6>
                                        <span className={`badge bg-${getHealthStatusColor(server.status)}`}>
                                          <i className={`bi ${getHealthStatusIcon(server.status)} me-1`}></i>
                                          {server.status}
                                        </span>
                                      </div>
                                      <div className="card-body">
                                        <div className="row g-2">
                                          <div className="col-6">
                                            <small className="text-muted">Uptime</small>
                                            <div className="fw-bold">{formatUptime(server.uptime_seconds)}</div>
                                          </div>
                                          <div className="col-6">
                                            <small className="text-muted">Load (1m)</small>
                                            <div className="fw-bold">{server.load_1min ? server.load_1min.toFixed(2) : 'N/A'}</div>
                                          </div>
                                          <div className="col-6">
                                            <small className="text-muted">Disk Usage</small>
                                            <div className="fw-bold">
                                              {server.disk_usage ? `${server.disk_usage.toFixed(1)}%` : 'N/A'}
                                            </div>
                                          </div>
                                          <div className="col-6">
                                            <small className="text-muted">Memory</small>
                                            <div className="fw-bold">
                                              {server.memory_usage ? `${server.memory_usage.toFixed(1)}%` : 'N/A'}
                                            </div>
                                          </div>
                                        </div>
                                        {server.last_checked && (
                                          <div className="mt-2">
                                            <small className="text-muted">
                                              Last checked: {formatLocal(server.last_checked)}
                                            </small>
                                          </div>
                                        )}
                                      </div>
                                      <div className="card-footer">
                                        <button 
                                          className="btn btn-sm btn-outline-primary w-100"
                                          onClick={() => checkSingleServerHealth(server.server_id)}
                                        >
                                          <i className="bi bi-arrow-clockwise me-1"></i>Check Now
                                        </button>
                                      </div>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <div className="col-12 text-center py-4">
                                  <i className="bi bi-heart-pulse display-4 text-muted"></i>
                                  <h5 className="mt-3 text-muted">No Health Data Available</h5>
                                  <p className="text-muted">Run health checks on your servers to see their status here.</p>
                                  <button className="btn btn-primary" onClick={checkAllServersHealth}>
                                    <i className="bi bi-heart-pulse me-2"></i>Check All Servers
                                  </button>
                                </div>
                              )}
                            </div>
                          ) : (
                            <div className="row g-2">
                              {serverHealth.length > 0 ? (
                                serverHealth.map((server) => (
                                  <div key={server.server_id} className="col-md-3 col-sm-6">
                                    <div className="d-flex align-items-center p-2 bg-dark rounded border border-secondary">
                                      <span className={`badge bg-${getHealthStatusColor(server.status)} me-2`}>
                                        <i className={`bi ${getHealthStatusIcon(server.status)}`}></i>
                                      </span>
                                      <div className="flex-grow-1">
                                        <div className="fw-bold">{server.server_name}</div>
                                        <small className="text-muted">{server.status}</small>
                                      </div>
                                    </div>
                                  </div>
                                ))
                              ) : (
                                <div className="col-12 text-center py-3">
                                  <span className="text-muted">No health data available</span>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                
                {/* Script Statistics Section */}
                <div className="row mt-4">
                  <div className="col-12">
                    <div className="card border-0">
                      <div className="card-body">
                        <h5 className="card-title mb-4">
                          <i className="bi bi-graph-up me-2"></i>Script Statistics
                        </h5>
                        
                        <div className="row g-3">
                          <div className="col-12 col-lg-8">
                            <div className="card bg-dark border-secondary">
                              <div className="card-body">
                                <div className="d-flex justify-content-between align-items-center mb-3">
                                  <h6 className="card-title mb-0"><i className="bi bi-clock-history me-2"></i>Recent Executions</h6>
                                  <Link to="/executions" className="btn btn-sm btn-outline-secondary">View all</Link>
                                </div>
                                <div className="mb-3" style={{height: 220}}>
                                  <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={executionsByDay} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                                      <CartesianGrid stroke="var(--border-primary)" strokeDasharray="3 3" />
                                      <XAxis dataKey="date" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} />
                                      <YAxis stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} allowDecimals={false} />
                                      <Tooltip />
                                      <Line type="monotone" dataKey="count" stroke="var(--info)" strokeWidth={2} dot={{ r: 2 }} />
                                    </LineChart>
                                  </ResponsiveContainer>
                                </div>
                                <div className="table-responsive">
                                  <table className="table table-sm table-hover table-striped">
                                    <thead>
                                      <tr>
                                        <th>Script</th><th>Server</th><th>Status</th><th>Started</th>
                                      </tr>
                                    </thead>
                                    <tbody>
                                      {(recentExecs || []).map(ex => {
                                        return (
                                        <tr key={ex.id}>
                                          <td>{ex.script?.name || scriptNameById[ex.script_id] || ex.script_id}</td>
                                          <td>{ex.server?.name || serverNameById[ex.server_id] || ex.server_id}</td>
                                          <td><span className={`badge ${ex.status==='completed'?'bg-success':ex.status==='running'?'bg-warning':'bg-danger'}`}>{ex.status}</span></td>
                                          <td>{ex.started_at ? formatLocal(ex.started_at) : '—'}</td>
                                        </tr>
                                        );
                                      })}
                                      {(recentExecs || []).length===0 && (
                                        <tr><td colSpan="4" className="text-center text-muted">No recent executions</td></tr>
                                      )}
                                    </tbody>
                                  </table>
                                </div>
                              </div>
                            </div>
                          </div>
                          
                          <div className="col-12 col-lg-4">
                            <div className="card bg-dark border-secondary mb-3">
                              <div className="card-body">
                                <h6 className="card-title"><i className="bi bi-exclamation-triangle me-2 text-warning"></i>Failing Executions</h6>
                                <ul className="list-group list-group-flush">
                                  {(failingExecs || []).slice(0,5).map(ex => {
                                    return (
                                    <li key={ex.id} className="list-group-item bg-transparent text-light d-flex justify-content-between align-items-center" style={{borderColor:'#333'}}>
                                      <span>{ex.script?.name || scriptNameById[ex.script_id] || ex.script_id} <span className="text-muted">on</span> {ex.server?.name || serverNameById[ex.server_id] || ex.server_id}</span>
                                      <span className="badge bg-danger">failed</span>
                                    </li>
                                    );
                                  })}
                                  {(failingExecs || []).length===0 && (
                                    <li className="list-group-item bg-transparent text-light text-muted" style={{borderColor:'#333'}}>No failures</li>
                                  )}
                                </ul>
                              </div>
                            </div>
                            
                            <div className="card bg-dark border-secondary">
                              <div className="card-body">
                                <h6 className="card-title"><i className="bi bi-alarm me-2"></i>Upcoming Schedules</h6>
                                <div className="mb-3" style={{height: 160}}>
                                  <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={next24hBuckets} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                                      <CartesianGrid stroke="var(--border-primary)" strokeDasharray="3 3" />
                                      <XAxis dataKey="hour" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} interval={3} />
                                      <YAxis stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 10 }} allowDecimals={false} />
                                      <Tooltip />
                                      <Bar dataKey="count" fill="var(--success)" />
                                    </BarChart>
                                  </ResponsiveContainer>
                                </div>
                                <ul className="list-group list-group-flush">
                                  {(upcomingSchedules || []).map(s => (
                                    <li key={s.id} className="list-group-item bg-transparent text-light d-flex justify-content-between align-items-center" style={{borderColor:'#333'}}>
                                      <span>{s.name}</span>
                                      <span className="text-muted small">{s.next_run_at ? formatLocal(s.next_run_at) : '—'}</span>
                                    </li>
                                  ))}
                                  {(upcomingSchedules || []).length===0 && (
                                    <li className="list-group-item bg-transparent text-light text-muted" style={{borderColor:'#333'}}>No upcoming runs</li>
                                  )}
                                </ul>
                              </div>
                            </div>
                          </div>
                        </div>

                        <div className="row g-3 mt-3">
                          <div className="col-12 col-lg-6">
                            <div className="card bg-dark border-secondary">
                              <div className="card-body">
                                <h6 className="card-title"><i className="bi bi-pie-chart me-2"></i>Status Distribution</h6>
                                <div style={{height: 260}}>
                                  <ResponsiveContainer width="100%" height="100%">
                                    <PieChart>
                                      <Pie data={statusDistribution} dataKey="value" nameKey="name" outerRadius={90} label>
                                        {statusDistribution.map((e, idx) => (
                                          <Cell key={`c-${idx}`} fill={e.key==='completed'?"var(--success)":e.key==='running'?"var(--warning)":"var(--danger)"} />
                                        ))}
                                      </Pie>
                                      <Legend />
                                      <Tooltip />
                                    </PieChart>
                                  </ResponsiveContainer>
                                </div>
                              </div>
                            </div>
                          </div>
                          <div className="col-12 col-lg-6">
                            <div className="card bg-dark border-secondary">
                              <div className="card-body">
                                <h6 className="card-title"><i className="bi bi-bar-chart me-2"></i>Top Scripts by Runs</h6>
                                <div style={{height: 260}}>
                                  <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={topScripts} layout="vertical" margin={{ top: 10, right: 20, left: 30, bottom: 0 }}>
                                      <CartesianGrid stroke="var(--border-primary)" strokeDasharray="3 3" />
                                      <XAxis type="number" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} allowDecimals={false} />
                                      <YAxis type="category" dataKey="name" stroke="var(--text-secondary)" tick={{ fill: 'var(--text-secondary)', fontSize: 12 }} width={120} />
                                      <Tooltip />
                                      <Bar dataKey="count" fill="var(--primary)" />
                                    </BarChart>
                                  </ResponsiveContainer>
                                </div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;