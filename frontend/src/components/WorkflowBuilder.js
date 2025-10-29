import React, { useEffect, useState, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'react-toastify';

// MVP builder: simple table-based editor (nodes and edges) before full canvas
const WorkflowBuilder = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const [wf, setWf] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [loading, setLoading] = useState(true);
  // canvas state
  const [selectedIdx, setSelectedIdx] = useState(null);
  const [dragIdx, setDragIdx] = useState(null);
  const [dragOffset, setDragOffset] = useState({x:0,y:0});
  const [isDragging, setIsDragging] = useState(false);
  const GRID = 10;
  const [connectFromIdx, setConnectFromIdx] = useState(null);
  const [connectCondition, setConnectCondition] = useState('on_success');
  const canvasRef = useRef(null);
  // mouse connect states
  const [isConnecting, setIsConnecting] = useState(false);
  const [mousePos, setMousePos] = useState({x:0,y:0});
  const [hoverIdx, setHoverIdx] = useState(null);
  const [showNodeEdit, setShowNodeEdit] = useState(false);
  const [editIdx, setEditIdx] = useState(null);
  const [editNode, setEditNode] = useState({ key:'', name:'', script_id:null, script_name:'', target_type:'', target_id:null, target_name:'' });
  const [scripts, setScripts] = useState([]);
  const [servers, setServers] = useState([]);
  const [groups, setGroups] = useState([]);
  const [triggerType, setTriggerType] = useState('user');
  const [scheduleCron, setScheduleCron] = useState('');
  const [scheduleTimezone, setScheduleTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone);
  const [scheduleMode, setScheduleMode] = useState('daily'); // daily | weekly | monthly | every_x_minutes | hourly | advanced
  const [everyXMinutes, setEveryXMinutes] = useState(15);
  const [hourlyMinute, setHourlyMinute] = useState(0);
  const [dailyTime, setDailyTime] = useState('09:00');
  const [weeklyDay, setWeeklyDay] = useState('1'); // 0=Sun..6=Sat
  const [weeklyTime, setWeeklyTime] = useState('09:00');
  const [monthlyDay, setMonthlyDay] = useState(1);
  const [monthlyTime, setMonthlyTime] = useState('09:00');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [webhookMethod, setWebhookMethod] = useState('POST');
  const [webhookPayload, setWebhookPayload] = useState('');
  const [maxRetries, setMaxRetries] = useState(3);
  const [retryInterval, setRetryInterval] = useState(60);
  const [groupFailurePolicy, setGroupFailurePolicy] = useState('any'); // 'any' or 'all'
  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState(''); // '', 'saving', 'success', 'error'
  const [saveError, setSaveError] = useState('');

  const buildCronFromState = () => {
    if (scheduleMode === 'advanced') return scheduleCron || '';
    const pad = (n) => String(n).padStart(2, '0');
    if (scheduleMode === 'every_x_minutes') {
      const n = Math.max(1, Number(everyXMinutes)||1);
      return `*/${n} * * * *`;
    }
    if (scheduleMode === 'hourly') {
      const m = Math.max(0, Math.min(59, Number(hourlyMinute)||0));
      return `${m} * * * *`;
    }
    if (scheduleMode === 'daily') {
      const [hh, mm] = (dailyTime||'09:00').split(':');
      return `${pad(mm||'00')} ${pad(hh||'09')} * * *`;
    }
    if (scheduleMode === 'weekly') {
      const [hh, mm] = (weeklyTime||'09:00').split(':');
      return `${pad(mm||'00')} ${pad(hh||'09')} * * ${weeklyDay}`;
    }
    if (scheduleMode === 'monthly') {
      const [hh, mm] = (monthlyTime||'09:00').split(':');
      const d = Math.max(1, Math.min(31, Number(monthlyDay)||1));
      return `${pad(mm||'00')} ${pad(hh||'09')} ${d} * *`;
    }
    return scheduleCron || '';
  };

  useEffect(() => {
    if (triggerType !== 'schedule') return;
    if (scheduleMode === 'advanced') return;
    setScheduleCron(buildCronFromState());
  }, [triggerType, scheduleMode, everyXMinutes, hourlyMinute, dailyTime, weeklyDay, weeklyTime, monthlyDay, monthlyTime]);
  const NODE_W = 160;
  const NODE_H = 60;

  // color utilities for node cards
  const hashString = (s) => {
    let h = 0;
    for (let i = 0; i < String(s).length; i++) {
      h = (h << 5) - h + String(s).charCodeAt(i);
      h |= 0;
    }
    return Math.abs(h);
  };
  const hslFromHash = (key) => {
    const h = hashString(key) % 360;
    const s = 65; // saturation
    const l = 78; // lightness (pastel)
    return { h, s, l };
  };
  const hslStr = ({h,s,l}) => `hsl(${h} ${s}% ${l}%)`;
  const darken = ({h,s,l}, amt = 18) => ({ h, s, l: Math.max(0, l - amt) });

  const load = async () => {
    setLoading(true);
    let attempts = 0;
    const maxAttempts = 10;
    while (attempts < maxAttempts) {
      try {
        const res = await axios.get(`/api/workflows/${id}`);
        setWf(res.data);
        setNodes(res.data.nodes || []);
        setEdges(res.data.edges || []);
        setTriggerType(res.data.trigger_type || 'user');
        // If an explicit cron exists, load it and lock builder to advanced to avoid overwrite
        const apiCron = res.data.schedule_cron || '';
        setScheduleCron(apiCron);
        if ((res.data.trigger_type || '').toLowerCase() === 'schedule' && apiCron) {
          setScheduleMode('advanced');
        }
        setScheduleTimezone(res.data.schedule_timezone || Intl.DateTimeFormat().resolvedOptions().timeZone);
        setWebhookUrl(res.data.webhook_url || '');
        setWebhookMethod(res.data.webhook_method || 'POST');
        setWebhookPayload(res.data.webhook_payload || '');
        setMaxRetries(res.data.max_retries || 0);
        setRetryInterval(res.data.retry_interval_seconds || 0);
        setGroupFailurePolicy(res.data.group_failure_policy || 'any');
        setLoading(false);
        return;
      } catch (e) {
        // If we have preloaded state (just-created), use it to render immediately
        const pre = location.state?.pre;
        if (pre && String(pre.id) === String(id)) {
          setWf({ id: pre.id, name: pre.name, description: pre.description, nodes: [], edges: [] });
          setTriggerType('user');
          setScheduleCron('');
          setScheduleTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
          setWebhookUrl('');
          setWebhookMethod('POST');
          setWebhookPayload('');
          setMaxRetries(0);
          setRetryInterval(0);
          setGroupFailurePolicy('any');
          setNodes([]);
          setEdges([]);
          setLoading(false);
          return;
        }
        attempts += 1;
        if (attempts >= maxAttempts) {
          toast.error('Failed to load workflow');
          setLoading(false);
          return;
        }
        await new Promise(r => setTimeout(r, 500));
      }
    }
  };

  useEffect(() => { load(); }, [id]);

  useEffect(() => {
    const fetchAll = async () => {
      try {
        const [sRes, srvRes, grpRes] = await Promise.all([
          axios.get('/api/scripts?skip=0&limit=100'),
          axios.get('/api/servers?skip=0&limit=100'),
          axios.get('/api/server-groups?skip=0&limit=100'),
        ]);
        const scr = sRes.data?.scripts || [];
        const srv = srvRes.data?.servers || [];
        const grp = grpRes.data?.groups || [];
        setScripts(scr);
        setServers(srv);
        setGroups(grp);
        if ((scr?.length||0)===0) toast.warn('No scripts available for selection');
        if ((srv?.length||0)===0 && (grp?.length||0)===0) toast.warn('No servers or groups available');
      } catch (e) {
        const msg = e?.response?.data?.detail || 'Failed to load scripts/servers/groups';
        toast.error(msg);
      }
    };
    fetchAll();
  }, []);

  const addNode = () => {
    const key = `N${nodes.length + 1}`;
    setNodes([...nodes, { key, name: key, script_id: null, target_type: 'server', target_id: null }]);
  };

  // edges are edited via mouse on canvas; no manual table editor

  const save = async () => {
    try {
      setIsSaving(true);
      setSaveStatus('saving');
      setSaveError('');
      toast.dismiss();
      toast.info('Saving workflow...');
      // Validations before save
      if ((nodes?.length || 0) <= 1) {
        const msg = 'Add at least two nodes before saving';
        toast.error(msg);
        setSaveError(msg);
        setSaveStatus('error');
        setIsSaving(false);
        return;
      }
      const keySet = new Set((nodes||[]).map(n=>n.key));
      const byKey = new Map((nodes||[]).map(n=>[n.key, n]));
      const incoming = new Map();
      const outgoing = new Map();
      (edges||[]).forEach(e=>{
        if (!incoming.has(e.target)) incoming.set(e.target, 0);
        incoming.set(e.target, incoming.get(e.target)+1);
        if (!outgoing.has(e.source)) outgoing.set(e.source, 0);
        outgoing.set(e.source, outgoing.get(e.source)+1);
      });
      const unconnected = (nodes||[]).filter(n=>!(incoming.get(n.key)>0) && !(outgoing.get(n.key)>0));
      if (unconnected.length>0) {
        const msg = `Unconnected nodes: ${unconnected.map(n=>n.name||n.key).join(', ')}`;
        toast.error(msg);
        setSaveError(msg);
        setSaveStatus('error');
        setIsSaving(false);
        return;
      }
      const emptyNodes = (nodes||[]).filter(n=>!(n.script_id && n.target_type && n.target_id));
      if (emptyNodes.length>0) {
        const msg = `Nodes missing script/target: ${emptyNodes.map(n=>n.name||n.key).join(', ')}`;
        toast.error(msg);
        setSaveError(msg);
        setSaveStatus('error');
        setIsSaving(false);
        return;
      }
      const dangling = (edges||[]).filter(e=>!keySet.has(e.source) || !keySet.has(e.target));
      if (dangling.length>0) {
        const msg = 'There are edges referencing non-existent nodes';
        toast.error(msg);
        setSaveError(msg);
        setSaveStatus('error');
        setIsSaving(false);
        return;
      }

      await axios.put(`/api/workflows/${id}`, {
        name: wf.name,
        description: wf.description,
        trigger_type: triggerType,
        schedule_cron: triggerType==='schedule' ? scheduleCron : null,
        schedule_timezone: triggerType==='schedule' ? scheduleTimezone : null,
        webhook_url: triggerType==='webhook' ? webhookUrl : null,
        webhook_method: triggerType==='webhook' ? webhookMethod : null,
        webhook_payload: triggerType==='webhook' ? webhookPayload : null,
        max_retries: maxRetries,
        retry_interval_seconds: retryInterval,
        group_failure_policy: groupFailurePolicy,
        nodes: nodes.map(n => ({ key: n.key, name: n.name, script_id: n.script_id ? Number(n.script_id) : null, target_type: n.target_type || null, target_id: n.target_id ? Number(n.target_id) : null })),
        edges: edges.map(e => ({ source: e.source, target: e.target, condition: e.condition || 'on_success' })),
      }, { timeout: 15000 });
      toast.success('Workflow saved');
      setSaveStatus('success');
      // Navigate back to workflows table after a short delay
      setTimeout(() => {
        try { navigate('/workflows'); } catch(_) {}
      }, 400);
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail || e?.message || 'Unknown error';
      console.error('Workflow save failed:', {
        status,
        detail,
        data: e?.response?.data,
        url: e?.config?.url,
        method: e?.config?.method,
      });
      toast.error(`Save failed${status ? ` (${status})` : ''}: ${detail}`);
      setSaveError(`${status ? `(${status}) ` : ''}${detail}`);
      setSaveStatus('error');
    }
    finally {
      setIsSaving(false);
    }
  };

  // Global mouse handlers for smooth dragging & connection preview
  useEffect(() => {
    const onMove = (ev) => {
      if (!canvasRef.current) return;
      const rect = canvasRef.current.getBoundingClientRect();
      const x = ev.clientX - rect.left;
      const y = ev.clientY - rect.top;
      setMousePos({x, y});
      if (dragIdx !== null) {
        const nx = Math.max(0, x - dragOffset.x);
        const ny = Math.max(0, y - dragOffset.y);
        const snapX = Math.round(nx / GRID) * GRID;
        const snapY = Math.round(ny / GRID) * GRID;
        setNodes(prev => {
          const copy = [...prev];
          const n = copy[dragIdx];
          copy[dragIdx] = { ...n, position: { x: snapX, y: snapY } };
          return copy;
        });
      }
    };
    const onUp = () => {
      if (dragIdx !== null) {
        setDragIdx(null);
        setIsDragging(false);
      }
      if (isConnecting) {
        if (connectFromIdx !== null && hoverIdx !== null && hoverIdx !== connectFromIdx) {
          const srcKey = nodes[connectFromIdx]?.key;
          const dstKey = nodes[hoverIdx]?.key;
          if (srcKey && dstKey) {
            setEdges(prev => [...prev, { source: srcKey, target: dstKey, condition: connectCondition }]);
          }
        }
        setIsConnecting(false);
        setConnectFromIdx(null);
      }
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, [dragIdx, dragOffset, isConnecting, connectFromIdx, connectCondition, nodes, hoverIdx]);

  // Keyboard: Delete/Backspace removes selected node and its edges
  useEffect(() => {
    const onKeyDown = (ev) => {
      if (showNodeEdit) return; // avoid interfering with modal inputs
      if (selectedIdx === null) return;
      
      // Don't delete nodes if user is typing in any input field
      if (ev.target.tagName === 'INPUT' || ev.target.tagName === 'TEXTAREA' || ev.target.tagName === 'SELECT') {
        return;
      }
      
      if (ev.key === 'Delete' || ev.key === 'Backspace') {
        ev.preventDefault();
        const node = nodes[selectedIdx];
        if (!node) return;
        const nodeKey = node.key;
        setNodes(prev => prev.filter((_, i) => i !== selectedIdx));
        setEdges(prev => prev.filter(e => e.source !== nodeKey && e.target !== nodeKey));
        setSelectedIdx(null);
        toast.info(`Deleted node ${nodeKey}`);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedIdx, nodes, showNodeEdit]);

  return (
    <div className="container-fluid">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <div>
          <h3 className="d-inline">Workflow Builder</h3>
        </div>
        <div className="d-flex gap-2"></div>
      </div>

      {loading ? (
        <div className="text-center py-5"><div className="spinner-border text-primary" role="status"><span className="visually-hidden">Loading...</span></div></div>
      ) : !wf ? (
        <div className="alert alert-danger">Workflow not found</div>
      ) : (
        <>
        <div className="row g-3">
          <div className="col-12 col-md-2">
            <div className="card shadow-sm h-100">
              <div className="card-header"><h6 className="mb-0">Workflow</h6></div>
              <div className="card-body">
                <div className="mb-2">
                  <label className="form-label small">Name</label>
                  <input className="form-control form-control-sm" value={wf.name||''} onChange={(e)=>setWf({...wf, name: e.target.value})} />
                </div>
                <div className="mb-2">
                  <label className="form-label small">Description</label>
                  <textarea className="form-control form-control-sm" rows={3} value={wf.description||''} onChange={(e)=>setWf({...wf, description: e.target.value})} />
                </div>
                {triggerType==='webhook' && (
                  <div className="border rounded p-2 mb-2">
                    <div className="mb-2">
                      <label className="form-label small">HTTP Address (URL)</label>
                      <input className="form-control form-control-sm" placeholder="https://example.com/hook" value={webhookUrl} onChange={(e)=>setWebhookUrl(e.target.value)} />
                    </div>
                    <div className="mb-2">
                      <label className="form-label small">Method</label>
                      <select className="form-select form-select-sm" value={webhookMethod} onChange={(e)=>setWebhookMethod(e.target.value)}>
                        <option>POST</option>
                        <option>GET</option>
                        <option>PUT</option>
                        <option>PATCH</option>
                        <option>DELETE</option>
                      </select>
                    </div>
                    <div className="mb-2">
                      <label className="form-label small">Payload (JSON)</label>
                      <textarea className="form-control form-control-sm" rows={4} placeholder='{"key":"value"}' value={webhookPayload} onChange={(e)=>setWebhookPayload(e.target.value)} />
                    </div>
                  </div>
                )}
                <div className="mb-2">
                  <label className="form-label small">Trigger Type</label>
                  <select className="form-select form-select-sm" value={triggerType} onChange={(e)=>setTriggerType(e.target.value)}>
                    <option value="user">user</option>
                    <option value="schedule">schedule</option>
                    <option value="webhook">webhook</option>
                  </select>
                </div>
                {triggerType==='schedule' && (
                  <div className="border rounded p-2 mb-2">
                    <div className="mb-2">
                      <label className="form-label small">Frequency</label>
                      <select className="form-select form-select-sm" value={scheduleMode} onChange={(e)=>setScheduleMode(e.target.value)}>
                        <option value="every_x_minutes">Every N minutes</option>
                        <option value="hourly">Hourly at minute</option>
                        <option value="daily">Daily at time</option>
                        <option value="weekly">Weekly on day/time</option>
                        <option value="monthly">Monthly on day/time</option>
                        <option value="advanced">Advanced (cron)</option>
                      </select>
                    </div>
                    {scheduleMode==='every_x_minutes' && (
                      <div className="mb-2 d-flex align-items-center gap-2">
                        <label className="form-label small mb-0">Every</label>
                        <input type="number" min={1} className="form-control form-control-sm" style={{width:100}} value={everyXMinutes} onChange={(e)=>setEveryXMinutes(e.target.value)} />
                        <span className="small text-muted">minutes</span>
                      </div>
                    )}
                    {scheduleMode==='hourly' && (
                      <div className="mb-2 d-flex align-items-center gap-2">
                        <label className="form-label small mb-0">At minute</label>
                        <input type="number" min={0} max={59} className="form-control form-control-sm" style={{width:100}} value={hourlyMinute} onChange={(e)=>setHourlyMinute(e.target.value)} />
                      </div>
                    )}
                    {scheduleMode==='daily' && (
                      <div className="mb-2">
                        <label className="form-label small">Time</label>
                        <input type="time" className="form-control form-control-sm" value={dailyTime} onChange={(e)=>setDailyTime(e.target.value)} />
                      </div>
                    )}
                    {scheduleMode==='weekly' && (
                      <>
                        <div className="mb-2">
                          <label className="form-label small">Day</label>
                          <select className="form-select form-select-sm" value={weeklyDay} onChange={(e)=>setWeeklyDay(e.target.value)}>
                            <option value="0">Sunday</option>
                            <option value="1">Monday</option>
                            <option value="2">Tuesday</option>
                            <option value="3">Wednesday</option>
                            <option value="4">Thursday</option>
                            <option value="5">Friday</option>
                            <option value="6">Saturday</option>
                          </select>
                        </div>
                        <div className="mb-2">
                          <label className="form-label small">Time</label>
                          <input type="time" className="form-control form-control-sm" value={weeklyTime} onChange={(e)=>setWeeklyTime(e.target.value)} />
                        </div>
                      </>
                    )}
                    {scheduleMode==='monthly' && (
                      <>
                        <div className="mb-2 d-flex align-items-center gap-2">
                          <label className="form-label small mb-0">Day of month</label>
                          <input type="number" min={1} max={31} className="form-control form-control-sm" style={{width:100}} value={monthlyDay} onChange={(e)=>setMonthlyDay(e.target.value)} />
                        </div>
                        <div className="mb-2">
                          <label className="form-label small">Time</label>
                          <input type="time" className="form-control form-control-sm" value={monthlyTime} onChange={(e)=>setMonthlyTime(e.target.value)} />
                        </div>
                      </>
                    )}
                    {scheduleMode==='advanced' && (
                      <div className="mb-2">
                        <label className="form-label small">Cron (advanced)</label>
                        <input className="form-control form-control-sm" placeholder="*/5 * * * *" value={scheduleCron} onChange={(e)=>setScheduleCron(e.target.value)} />
                      </div>
                    )}
                    <div className="mb-2">
                      <label className="form-label small">Timezone</label>
                      <input className="form-control form-control-sm" placeholder={Intl.DateTimeFormat().resolvedOptions().timeZone} value={scheduleTimezone} onChange={(e)=>setScheduleTimezone(e.target.value)} />
                    </div>
                    <div className="small text-muted">Cron preview: {scheduleMode==='advanced' ? (scheduleCron||'-') : (buildCronFromState()||'-')}</div>
                  </div>
                )}
                <div className="mb-2">
                  <label className="form-label small">Max Retries (per node)</label>
                  <input type="number" min="0" max="10" className="form-control form-control-sm" value={maxRetries} onChange={(e)=>setMaxRetries(Number(e.target.value)||0)} />
                </div>
                <div className="mb-2">
                  <label className="form-label small">Retry Interval (seconds)</label>
                  <input type="number" min="0" max="3600" className="form-control form-control-sm" value={retryInterval} onChange={(e)=>setRetryInterval(Number(e.target.value)||0)} />
                </div>
                <div className="mb-2">
                  <label className="form-label small">Group Failure Policy</label>
                  <select className="form-select form-select-sm" value={groupFailurePolicy} onChange={(e)=>setGroupFailurePolicy(e.target.value)}>
                    <option value="any">Any member fails = group fails</option>
                    <option value="all">All members must fail = group fails</option>
                  </select>
                </div>
                <div className="text-end">
                  <button type="button" className="btn btn-sm btn-primary" onClick={save} disabled={isSaving}>
                    {isSaving ? (
                      <>
                        <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                        Saving...
                      </>
                    ) : (
                      <>
                        <i className="bi bi-save me-1"></i>Save
                      </>
                    )}
                  </button>
                  {saveStatus==='saving' && <div className="small text-muted mt-2">Saving...</div>}
                  {saveStatus==='success' && <div className="small text-success mt-2">Saved.</div>}
                  {saveStatus==='error' && <div className="small text-danger mt-2">Save failed. {saveError}</div>}
                </div>
              </div>
            </div>
          </div>
          <div className="col-12 col-md-10">
            <div className="card shadow-sm">
              <div className="card-header d-flex justify-content-end align-items-center">
                <div className="d-flex gap-2">
                  <button className="btn btn-outline-primary btn-sm" onClick={addNode}><i className="bi bi-plus-lg me-1"></i>Add Node</button>
                </div>
              </div>
              <div className="card-body" ref={canvasRef} style={{height:'calc(100vh - 220px)', position:'relative', overflow:'hidden', backgroundImage:'linear-gradient(90deg, rgba(0,0,0,0.05) 1px, transparent 1px), linear-gradient(180deg, rgba(0,0,0,0.05) 1px, transparent 1px)', backgroundSize:'20px 20px'}}>
                <svg width="2000" height="2000" style={{position:'absolute', left:0, top:0, pointerEvents:'none'}}>
                  <defs>
                    <marker id="arrow-success" markerWidth="10" markerHeight="10" refX="10" refY="3" orient="auto" markerUnits="strokeWidth">
                      <path d="M0,0 L10,3 L0,6 Z" fill="#198754"></path>
                    </marker>
                    <marker id="arrow-failure" markerWidth="10" markerHeight="10" refX="10" refY="3" orient="auto" markerUnits="strokeWidth">
                      <path d="M0,0 L10,3 L0,6 Z" fill="#dc3545"></path>
                    </marker>
                  </defs>
                  {/* temp connecting path */}
                  {isConnecting && connectFromIdx!==null && (()=>{
                    const src = nodes[connectFromIdx];
                    if (!src) return null;
                    const sp = src.position||{x:0,y:0};
                    const x1 = sp.x + NODE_W;
                    const y1 = sp.y + NODE_H/2;
                    const x2 = mousePos.x;
                    const y2 = mousePos.y;
                    const stroke = connectCondition==='on_failure' ? '#dc3545' : '#198754';
                    return <path d={`M ${x1} ${y1} C ${x1+60} ${y1}, ${x2-60} ${y2}, ${x2} ${y2}`} stroke={stroke} strokeWidth="2" fill="none" />
                  })()}
                  {(edges||[]).map((e, i) => {
                    const src = nodes.find(n=>n.key===e.source);
                    const dst = nodes.find(n=>n.key===e.target);
                    if(!src || !dst) return null;
                    const sp = (src.position||{x:50,y:50});
                    const dp = (dst.position||{x:200,y:200});
                    const x1 = (sp.x || 0) + NODE_W; // right edge of source
                    const y1 = (sp.y || 0) + NODE_H/2;
                    const x2 = (dp.x || 0); // left edge of target
                    const y2 = (dp.y || 0) + NODE_H/2;
                    const stroke = e.condition==='on_failure' ? '#dc3545' : '#198754';
                    const marker = e.condition==='on_failure' ? 'url(#arrow-failure)' : 'url(#arrow-success)';
                    return (
                      <g key={i}>
                        <path d={`M ${x1} ${y1} C ${x1+60} ${y1}, ${x2-60} ${y2}, ${x2} ${y2}`} stroke={stroke} strokeWidth="2.5" fill="none" markerEnd={marker}/>
                      </g>
                    );
                  })}
                </svg>
                {(nodes||[]).map((n, idx)=>{
                  const pos = n.position || {x: 60 + idx*40, y: 60 + idx*20};
                  if(!n.position) {
                    const copy=[...nodes]; copy[idx] = {...n, position: pos}; setNodes(copy);
                  }
                  const isSel = selectedIdx===idx;
                  const hue = hslFromHash(n.key || idx);
                  const bg = hslStr(hue);
                  const borderCol = hslStr(darken(hue, 25));
                  return (
                    <div key={idx}
                      onMouseEnter={()=>setHoverIdx(idx)}
                      onMouseLeave={()=>setHoverIdx(curr => curr===idx ? null : curr)}
                      onMouseDown={(ev)=>{
                        // ignore drag start if clicking the gear button
                        if ((ev.target.closest && ev.target.closest('button')) || ev.target.tagName === 'BUTTON' || ev.target.tagName === 'I') return;
                        if (!canvasRef.current) return;
                        const rect = canvasRef.current.getBoundingClientRect();
                        const x = ev.clientX - rect.left;
                        const y = ev.clientY - rect.top;
                        setDragIdx(idx);
                        setIsDragging(true);
                        setDragOffset({x: x - (n.position?.x||0), y: y - (n.position?.y||0)});
                      }}
                      onClick={()=>{
                        if (connectFromIdx===null) {
                          setSelectedIdx(idx);
                        } else if (connectFromIdx!==idx) {
                          // add edge using keys
                          const srcKey = nodes[connectFromIdx]?.key;
                          const dstKey = nodes[idx]?.key;
                          if (srcKey && dstKey) {
                            setEdges([...edges, { source: srcKey, target: dstKey, condition: connectCondition }]);
                            toast.success(`Connected ${srcKey} -> ${dstKey} (${connectCondition})`);
                          }
                          setConnectFromIdx(null);
                        }
                      }}
                      onDoubleClick={()=>{
                        // start connect from this node
                        setConnectFromIdx(idx);
                        setSelectedIdx(idx);
                      }}
                      className={`card shadow-sm ${isSel?'border-primary':''}`}
                      style={{position:'absolute', left: n.position?.x||0, top: n.position?.y||0, width: NODE_W, cursor: isDragging && dragIdx===idx ? 'grabbing' : 'grab', userSelect:'none', backgroundColor: bg, border: `2px solid ${borderCol}`}}>
                      <div className="card-body p-2 position-relative">
                        <button type="button" className="btn btn-sm btn-light position-absolute" style={{right:6, top:6, padding:'2px 6px'}} onClick={(e)=>{ e.stopPropagation(); setEditIdx(idx); const sName = (n.script_id && scripts.find(s=>String(s.id)===String(n.script_id))?.name) || ''; const tName = (()=>{ if(n.target_type==='server'){ return servers.find(s=>String(s.id)===String(n.target_id))?.name || ''; } if(n.target_type==='group'){ return groups.find(g=>String(g.id)===String(n.target_id))?.name || ''; } return ''; })(); setEditNode({ name:n.name||'', script_id:n.script_id||'', script_name:sName, target_type:n.target_type||'', target_id:n.target_id||'', target_name:tName }); setShowNodeEdit(true); }} title="Edit node">
                          <i className="bi bi-gear"></i>
                        </button>
                        {/* connection handle on right edge for mouse drag connect */}
                        <span
                          title="Drag to connect"
                          onMouseDown={(e)=>{
                            e.stopPropagation();
                            // left click => success, right click => failure
                            if (e.button === 2) {
                              setConnectCondition('on_failure');
                            } else {
                              setConnectCondition('on_success');
                            }
                            setConnectFromIdx(idx);
                            setIsConnecting(true);
                          }}
                          onContextMenu={(e)=>{ e.preventDefault(); }}
                          style={{position:'absolute', right:-6, top:'50%', transform:'translateY(-50%)', width:12, height:12, borderRadius:'50%', backgroundColor: connectCondition==='on_failure'?'#dc3545':'#198754', border:'2px solid #fff', boxShadow:'0 0 0 2px rgba(0,0,0,0.15)', cursor:'crosshair'}}
                        />
                        <div className="fw-bold small text-truncate" title={n.name || 'New Node'}>{n.name || 'New Node'}</div>
                        {(() => {
                          const sName = (n.script_id && scripts.find(s=>String(s.id)===String(n.script_id))?.name) || '';
                          const tName = (()=>{ if(n.target_type==='server'){ return servers.find(s=>String(s.id)===String(n.target_id))?.name || ''; } if(n.target_type==='group'){ return groups.find(g=>String(g.id)===String(n.target_id))?.name || ''; } return ''; })();
                          return (
                            <>
                              {sName ? <div className="small text-muted">{sName}</div> : null}
                              {tName ? <div className="small text-muted">{tName}</div> : null}
                            </>
                          );
                        })()}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
        
          {showNodeEdit && editIdx!==null && (
            <div className="modal show d-block" style={{backgroundColor:'rgba(0,0,0,0.5)'}}>
              <div className="modal-dialog">
                <div className="modal-content">
                  <div className="modal-header border-secondary">
                    <h5 className="modal-title">Edit Node</h5>
                    <button type="button" className="btn-close btn-close-white" onClick={()=>setShowNodeEdit(false)}></button>
                  </div>
                  <div className="modal-body">
                    <div className="mb-2">
                      <label className="form-label small">Name</label>
                      <input className="form-control form-control-sm" value={editNode.name} onChange={(e)=>setEditNode({...editNode, name: e.target.value})} />
                    </div>
                    <div className="mb-2">
                      <label className="form-label small">Script</label>
                      <select className="form-select form-select-sm" value={editNode.script_name} onChange={(e)=>{ const name = e.target.value; const s = scripts.find(x=>x.name===name); setEditNode({...editNode, script_name: name, script_id: s? s.id : ''}); }}>
                        <option value="">-</option>
                        {scripts.map(s=> <option key={s.id} value={s.name}>{s.name}</option>)}
                      </select>
                    </div>
                    <div className="mb-2">
                      <label className="form-label small">Target Type</label>
                      <select className="form-select form-select-sm" value={editNode.target_type} onChange={(e)=>setEditNode({...editNode, target_type: e.target.value})}>
                        <option value="">-</option>
                        <option value="server">server</option>
                        <option value="group">group</option>
                      </select>
                    </div>
                    <div className="mb-2">
                      <label className="form-label small">Target</label>
                      {editNode.target_type==='server' && (
                        <select className="form-select form-select-sm" value={editNode.target_name} onChange={(e)=>{ const name=e.target.value; const t=servers.find(x=>x.name===name); setEditNode({...editNode, target_name: name, target_id: t? t.id : ''}); }}>
                          <option value="">-</option>
                          {servers.map(s=> <option key={s.id} value={s.name}>{s.name}</option>)}
                        </select>
                      )}
                      {editNode.target_type==='group' && (
                        <select className="form-select form-select-sm" value={editNode.target_name} onChange={(e)=>{ const name=e.target.value; const g=groups.find(x=>x.name===name); setEditNode({...editNode, target_name: name, target_id: g? g.id : ''}); }}>
                          <option value="">-</option>
                          {groups.map(g=> <option key={g.id} value={g.name}>{g.name}</option>)}
                        </select>
                      )}
                      {!editNode.target_type && (
                        <input className="form-control form-control-sm" value="" disabled />
                      )}
                    </div>
                  </div>
                  <div className="modal-footer border-secondary">
                    <button className="btn btn-secondary" onClick={()=>setShowNodeEdit(false)}>Cancel</button>
                    <button className="btn btn-primary" onClick={()=>{
                      const copy=[...nodes];
                      copy[editIdx] = {
                        ...copy[editIdx],
                        key: copy[editIdx].key,
                        name: editNode.name||copy[editIdx].name,
                        script_id: editNode.script_id?Number(editNode.script_id):null,
                        target_type: editNode.target_type||null,
                        target_id: editNode.target_id?Number(editNode.target_id):null,
                      };
                      setNodes(copy);
                      setShowNodeEdit(false);
                    }}>Save</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default WorkflowBuilder;


