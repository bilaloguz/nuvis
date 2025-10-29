import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import './ScriptManagement.css';
import MonacoEditor from '@monaco-editor/react';

// Monaco-based code editor
const MonacoCodeEditor = ({ value, onChange, language }) => {
  const monacoLanguage = (
    language === 'python' ? 'python' :
    language === 'powershell' ? 'powershell' :
    'shell'
  );

  return (
    <div style={{ border: '1px solid #333', borderRadius: 6, overflow: 'hidden' }}>
      <MonacoEditor
        height="300px"
        theme="vs-dark"
        language={monacoLanguage}
        value={value || ''}
        onChange={(val) => onChange({ target: { value: val ?? '' } })}
        options={{
          minimap: { enabled: false },
          wordWrap: 'off',
          tabSize: 2,
          insertSpaces: true,
          detectIndentation: false,
          automaticLayout: true,
          scrollBeyondLastLine: false,
          renderWhitespace: 'selection',
          renderLineHighlight: 'line',
          autoClosingBrackets: 'always',
          autoClosingQuotes: 'always',
          matchBrackets: 'always',
          suggestOnTriggerCharacters: true,
          quickSuggestions: true,
        }}
      />
    </div>
  );
};

const ScriptManagement = () => {
  const { user: currentUser } = useAuth();
  const [scripts, setScripts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingScript, setEditingScript] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [scriptToDelete, setScriptToDelete] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  // Execute modal state
  const [showExecuteModal, setShowExecuteModal] = useState(false);
  const [executeScript, setExecuteScript] = useState(null);
  const [servers, setServers] = useState([]);
  const [serverGroups, setServerGroups] = useState([]);
  const [executeForm, setExecuteForm] = useState({ server_id: '', parameters_used: '' });
  const [executing, setExecuting] = useState(false);
  const [executeResult, setExecuteResult] = useState(null);
  const [targetType, setTargetType] = useState('server'); // group option removed
  const [groupId, setGroupId] = useState('');
  const [overrideEnabled, setOverrideEnabled] = useState(false);
  const [overrideConcurrency, setOverrideConcurrency] = useState('');
  const [overrideContinueOnError, setOverrideContinueOnError] = useState(true);
  const [overrideTimeout, setOverrideTimeout] = useState('');
  const [executions, setExecutions] = useState([]);
  const [loadingExecutions, setLoadingExecutions] = useState(false);
  const [filterScriptId, setFilterScriptId] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  // Live execute (WebSocket) state
  const [ws, setWs] = useState(null);
  const [liveOutput, setLiveOutput] = useState([]);
  const [liveStatus, setLiveStatus] = useState('idle'); // idle | connecting | running | error | done
  const [jobIdState, setJobIdState] = useState(null);
  const [linkedExecId, setLinkedExecId] = useState(null);
  // Export modal state
  const [showExportModal, setShowExportModal] = useState(false);
  const [exportScript, setExportScript] = useState(null);
  const [exportForm, setExportForm] = useState({ is_public: true, description: '', tagsText: '' });
  const [createForm, setCreateForm] = useState({
    name: '',
    description: '',
    content: '',
    script_type: 'bash',
    category: 'general',
    parameters: '',
    per_server_timeout_seconds: 60
  });

  const scriptTypes = [
    { value: 'bash', label: 'Bash', icon: 'bi-terminal' },
    { value: 'python', label: 'Python', icon: 'bi-code-slash' },
    { value: 'powershell', label: 'PowerShell', icon: 'bi-windows' }
  ];

  const categories = [
    { value: 'general', label: 'General', color: '#6b7280' },
    { value: 'deployment', label: 'Deployment', color: '#10b981' },
    { value: 'maintenance', label: 'Maintenance', color: '#f59e0b' },
    { value: 'monitoring', label: 'Monitoring', color: '#3b82f6' },
    { value: 'backup', label: 'Backup', color: '#8b5cf6' },
    { value: 'security', label: 'Security', color: '#ef4444' }
  ];

  useEffect(() => {
    if (currentUser?.role === 'admin') {
      fetchScripts();
      fetchServers();
      fetchServerGroups();
      fetchExecutions();
    }
  }, [currentUser]);

  const fetchScripts = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/scripts/');
      console.log('🔍 API Response:', response.data);
      console.log('📝 Scripts data:', response.data.scripts);
      setScripts(response.data.scripts);
    } catch (error) {
      setError('Failed to fetch scripts');
      console.error('Error fetching scripts:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchServers = async () => {
    try {
      const resp = await axios.get('/api/servers/');
      setServers(resp.data.servers || []);
    } catch (e) {
      console.error('Error fetching servers:', e);
    }
  };

  const fetchServerGroups = async () => {
    try {
      const resp = await axios.get('/api/server-groups/');
      setServerGroups(resp.data.groups || []);
    } catch (e) {
      console.error('Error fetching server groups:', e);
    }
  };

  const fetchExecutions = async () => {
    try {
      setLoadingExecutions(true);
      const resp = await axios.get('/api/scripts/executions/?limit=50');
      setExecutions(resp.data.executions || []);
    } catch (e) {
      console.error('Error fetching executions:', e);
    } finally {
      setLoadingExecutions(false);
    }
  };

  const handleEdit = (script) => {
    setEditingScript(script);
    setEditForm({
      name: script.name,
      description: script.description || '',
      content: script.content,
      script_type: script.script_type,
      category: script.category,
      parameters: script.parameters || ''
    });
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.put(`/api/scripts/${editingScript.id}`, editForm);
      
      // Update the scripts list
      setScripts(scripts.map(s => s.id === editingScript.id ? response.data : s));
      
      // Reset form
      setEditingScript(null);
      setEditForm({});
      
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to update script');
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    
    if (!createForm.name.trim()) {
      alert('Script name is required');
      return;
    }
    
    if (!createForm.content.trim()) {
      alert('Script content is required');
      return;
    }
    
    try {
      console.log('📤 Sending createForm:', createForm);
      const response = await axios.post('/api/scripts/', createForm);
      console.log('📥 Received response:', response.data);
      setScripts([...scripts, response.data]);
      setShowCreateModal(false);
      setCreateForm({
        name: '',
        description: '',
        content: '',
        script_type: 'bash',
        category: 'general',
        parameters: ''
      });
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to create script');
    }
  };

  const handleDelete = (script) => {
    setScriptToDelete(script);
    setShowDeleteModal(true);
  };

  const confirmDelete = async () => {
    try {
      await axios.delete(`/api/scripts/${scriptToDelete.id}`);
      
      // Remove script from list
      setScripts(scripts.filter(s => s.id !== scriptToDelete.id));
      
      // Close modal
      setShowDeleteModal(false);
      setScriptToDelete(null);
      
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to delete script');
    }
  };

  const openExportModal = (script) => {
    setExportScript(script);
    setExportForm({ is_public: true, description: script.description || '', tagsText: '' });
    setShowExportModal(true);
  };

  const submitExport = async () => {
    if (!exportScript) return;
    try {
      // Convert comma-separated tagsText to JSON array string
      const tagsArray = exportForm.tagsText
        .split(',')
        .map(t => t.trim())
        .filter(t => t.length > 0);
      const payload = {
        script_id: exportScript.id,
        is_public: !!exportForm.is_public,
        description: exportForm.description || exportScript.description || '',
        tags: JSON.stringify(tagsArray)
      };
      const resp = await axios.post('/api/marketplace/export', payload);
      // basic success UX
      alert('Exported to marketplace successfully. ID: ' + (resp.data?.marketplace_script_id ?? '')); 
      setShowExportModal(false);
      setExportScript(null);
    } catch (e) {
      alert(e.response?.data?.detail || 'Failed to export script');
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getScriptTypeIcon = (type) => {
    const scriptType = scriptTypes.find(t => t.value === type);
    return scriptType ? scriptType.icon : 'bi-file-text';
  };

  const getCategoryColor = (category) => {
    const cat = categories.find(c => c.value === category);
    return cat ? cat.color : '#6b7280';
  };

  // Safely stringify values for display in <pre>
  const toSafeString = (val) => {
    if (val == null) return '';
    if (typeof val === 'string') return val;
    try {
      return JSON.stringify(val, null, 2);
    } catch (e) {
      return String(val);
    }
  };

  // CodeEditor is defined at module scope to preserve focus

  if (currentUser?.role !== 'admin') {
    return (
      <div className="main-content">
        <div className="container-fluid">
          <div className="alert alert-warning border-0" role="alert" style={{backgroundColor: 'rgba(245, 158, 11, 0.1)'}}>
            <h4 className="alert-heading">
              <i className="bi bi-exclamation-triangle me-2"></i>
              Access Denied
            </h4>
            <p>You need admin privileges to access script management.</p>
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="main-content">
        <div className="container-fluid">
          <div className="text-center">
            <div className="spinner-border text-primary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
      <div className="container-fluid">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h1>
            <i className="bi bi-code-square me-3"></i>
            Scripts
          </h1>
        </div>

        {error && (
          <div className="alert alert-danger border-0" role="alert" style={{backgroundColor: 'rgba(239, 68, 68, 0.1)'}}>
            <i className="bi bi-exclamation-circle me-2"></i>
            {error}
          </div>
        )}

        <div className="card shadow-lg">
          <div className="card-body">
            <div className="table-responsive">
              <table className="table table-sm table-hover table-striped">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Category</th>
                    <th>Description</th>
                    <th>Creator</th>
                    <th>Created</th>
                    <th className="text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(() => {
                    console.log('🔍 Scripts array:', scripts);
                    return scripts.map((script) => (
                      <tr key={script.id}>
                        <td>
                          <strong>{script.name}</strong>
                        </td>
                        <td>
                          <span className="badge bg-info">
                            <i className={`bi ${getScriptTypeIcon(script.script_type)} me-1`}></i>
                            {script.script_type}
                          </span>
                        </td>
                        <td>
                          <span 
                            className="badge" 
                            style={{
                              backgroundColor: getCategoryColor(script.category),
                              color: 'white'
                            }}
                          >
                            {script.category}
                          </span>
                        </td>
                        <td>
                          <span style={{color: 'var(--text-primary)'}}>
                            {(() => {
                              const displayText = script.description ? 
                                (script.description.length > 50 ? 
                                  `${script.description.substring(0, 50)}...` : 
                                  script.description
                                ) : 
                                'No description';
                              return displayText;
                            })()}
                          </span>
                        </td>
                        <td>
                          <span className="badge bg-secondary">
                            {script.creator?.username || 'Unknown'}
                          </span>
                        </td>
                        <td>{formatDate(script.created_at)}</td>
                        <td>
                          <div className="d-flex gap-2 align-items-center justify-content-center" role="group">
                            {/* Left group: Edit, Delete */}
                            <button
                              className="btn btn-outline-primary"
                              onClick={() => handleEdit(script)}
                              title="Edit script"
                            >
                              <i className="bi bi-pencil me-1"></i>
                              Edit
                            </button>
                            <button
                              className="btn btn-outline-danger"
                              onClick={() => handleDelete(script)}
                              title="Delete script"
                            >
                              <i className="bi bi-trash me-1"></i>
                              Delete
                            </button>

                            {/* Separator */}
                            <span style={{opacity:0.6}}> | </span>

                            {/* Right group: Export, Execute */}
                            <button
                              className="btn btn-outline-warning"
                              onClick={() => openExportModal(script)}
                              title="Export to Marketplace"
                            >
                              <i className="bi bi-shop me-1"></i>
                              Export
                            </button>
                            <button
                              className="btn btn-outline-success"
                              onClick={() => {
                                setExecuteScript(script);
                                setShowExecuteModal(true);
                                setExecuteForm({ server_id: servers[0]?.id || '', parameters_used: '' });
                                setExecuteResult(null);
                                setTargetType('server');
                                setGroupId('');
                                setOverrideEnabled(false);
                                setOverrideConcurrency('');
                                setOverrideContinueOnError(true);
                                setOverrideTimeout('');
                              }}
                              title="Execute script"
                            >
                              <i className="bi bi-play-circle me-1"></i>
                              Execute
                            </button>
                          </div>
                        </td>
                      </tr>
                    ));
                  })()}
                </tbody>
              </table>
            </div>
            
            <div className="mt-3 text-center">
              <button className="btn btn-success" onClick={() => setShowCreateModal(true)}>
                <i className="bi bi-plus-circle me-2"></i>
                Create
              </button>
            </div>
          </div>
        </div>

        {/* Edit Script Modal */}
        {editingScript && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog modal-xl">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-pencil-square me-2"></i>
                    Edit Script: {editingScript.name}
                  </h5>
                  <button
                    type="button"
                    className="btn-close btn-close-white"
                    onClick={() => {
                      setEditingScript(null);
                      setEditForm({});
                    }}
                  ></button>
                </div>
                <form onSubmit={handleEditSubmit}>
                  <div className="modal-body">
                    <div className="row">
                      <div className="col-md-6">
                        <div className="mb-3">
                          <label htmlFor="scriptName" className="form-label">Script Name</label>
                          <input
                            type="text"
                            className="form-control"
                            id="scriptName"
                            value={editForm.name || ''}
                            onChange={(e) => setEditForm({...editForm, name: e.target.value})}
                            required
                          />
                        </div>
                      </div>
                      <div className="col-md-3">
                        <div className="mb-3">
                          <label htmlFor="scriptType" className="form-label">Script Type</label>
                          <select
                            className="form-control"
                            id="scriptType"
                            value={editForm.script_type || 'bash'}
                            onChange={(e) => setEditForm({...editForm, script_type: e.target.value})}
                          >
                            {scriptTypes.map(type => (
                              <option key={type.value} value={type.value}>
                                {type.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="col-md-3">
                        <div className="mb-3">
                          <label htmlFor="scriptCategory" className="form-label">Category</label>
                          <select
                            className="form-control"
                            id="scriptCategory"
                            value={editForm.category || 'general'}
                            onChange={(e) => setEditForm({...editForm, category: e.target.value})}
                          >
                            {categories.map(cat => (
                              <option key={cat.value} value={cat.value}>
                                {cat.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                    <div className="mb-3">
                      <label htmlFor="scriptDescription" className="form-label">Description</label>
                      <textarea
                        className="form-control"
                        id="scriptDescription"
                        rows="2"
                        value={editForm.description || ''}
                        onChange={(e) => setEditForm({...editForm, description: e.target.value})}
                        placeholder="Describe what this script does..."
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="scriptContent" className="form-label">Script Content</label>
                      <MonacoCodeEditor
                        value={editForm.content || ''}
                        onChange={(e) => setEditForm({...editForm, content: e.target.value})}
                        language={editForm.script_type || 'bash'}
                      />
                    </div>
                                          <div className="mb-3">
                        <label htmlFor="scriptParameters" className="form-label">Parameters (Optional)</label>
                        <textarea
                          className="form-control"
                          id="scriptParameters"
                          rows="3"
                          value={editForm.parameters || ''}
                          onChange={(e) => setEditForm({...editForm, parameters: e.target.value})}
                          placeholder='JSON format: {"param1": "value1", "param2": "value2"}'
                        />
                        <div className="form-text">
                          <i className="bi bi-info-circle me-1"></i>
                          Define script parameters in JSON format
                        </div>
                      </div>
                  </div>
                  <div className="modal-footer">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        setEditingScript(null);
                        setEditForm({});
                      }}
                    >
                      Cancel
                    </button>
                    <button type="submit" className="btn btn-primary">
                      <i className="bi bi-check-circle me-2"></i>
                      Save Changes
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Executions table removed (moved to /executions page) */}
        {/* Execute Script Modal */}
        {showExecuteModal && executeScript && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog modal-lg">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-play-circle me-2"></i>
                    Execute Script: {executeScript.name}
                  </h5>
                  <button
                    type="button"
                    className="btn-close btn-close-white"
                    onClick={() => setShowExecuteModal(false)}
                  ></button>
                </div>
                <div className="modal-body">
                  <div className="mb-3">
                    <label className="form-label">Target Server</label>
                    <select className="form-select" value={executeForm.server_id} onChange={(e) => setExecuteForm({ ...executeForm, server_id: Number(e.target.value) })}>
                      <option value="">Select a server</option>
                      {servers.map(s => (
                        <option key={s.id} value={s.id}>{s.name} ({s.ip})</option>
                      ))}
                    </select>
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Parameters (JSON, optional)</label>
                    <textarea
                      className="form-control"
                      rows="3"
                      value={executeForm.parameters_used}
                      onChange={(e) => setExecuteForm({ ...executeForm, parameters_used: e.target.value })}
                      placeholder='{"param1": "value1"}'
                    />
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Timeout Override (optional)</label>
                    <div className="input-group">
                      <input 
                        type="number" 
                        min="0" 
                        max="3600" 
                        className="form-control" 
                        value={executeForm.timeout_override || ''} 
                        onChange={(e) => setExecuteForm({ ...executeForm, timeout_override: e.target.value })} 
                        placeholder="Use script default" 
                      />
                      <div className="input-group-text">
                        <div className="form-check">
                          <input
                            className="form-check-input"
                            type="checkbox"
                            id="executeInfiniteTimeout"
                            checked={executeForm.timeout_override === '0'}
                            onChange={(e) => setExecuteForm({ ...executeForm, timeout_override: e.target.checked ? '0' : '' })}
                          />
                          <label className="form-check-label" htmlFor="executeInfiniteTimeout">
                            Infinite
                          </label>
                        </div>
                      </div>
                    </div>
                    <div className="form-text small">
                      Override script timeout (0 = infinite, leave blank for script default)
                    </div>
                  </div>

                  {/* Group options removed */}

                  {executeResult && (
                    <div className="mt-3">
                      {/* Group (aggregate) result */}
                      {executeResult.summary && Array.isArray(executeResult.results) ? (
                        <>
                          <div className="mb-2">
                            <span className="badge bg-info me-2">Total: {executeResult.summary.total}</span>
                            <span className="badge bg-success me-2">Succeeded: {executeResult.summary.succeeded}</span>
                            <span className="badge bg-danger">Failed: {executeResult.summary.failed}</span>
                          </div>
                          <div className="table-responsive">
                            <table className="table table-sm table-striped align-middle" style={{borderColor:'#333'}}>
                              <thead>
                                <tr>
                                  <th>Server</th>
                                  <th>Status</th>
                                  <th>Output</th>
                                  <th>Error</th>
                                </tr>
                              </thead>
                              <tbody>
                                {executeResult.results.map((r, idx) => (
                                  <tr key={idx}>
                                    <td><span className="badge bg-secondary me-2">{r.server_id}</span>{r.server_name}</td>
                                    <td>
                                      <span className={`badge ${r.status === 'completed' ? 'bg-success' : r.status === 'failed' ? 'bg-danger' : r.status === 'long_running' ? 'bg-warning' : 'bg-secondary'}`}>{r.status}</span>
                                    </td>
                                    <td style={{maxWidth:'30vw'}}>
                                      <pre style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', padding: '6px', border: '1px solid var(--border-primary)', borderRadius: 6, maxHeight: '160px', overflow: 'auto', margin:0 }}>{toSafeString(r.output)}</pre>
                                    </td>
                                    <td style={{maxWidth:'30vw'}}>
                                      {r.error ? (
                                        <pre style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', padding: '6px', border: '1px solid var(--border-primary)', borderRadius: 6, maxHeight: '160px', overflow: 'auto', margin:0 }}>{toSafeString(r.error)}</pre>
                                      ) : (
                                        <span className="text-muted">—</span>
                                      )}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </>
                      ) : (
                        // Single-server result
                        <>
                          <div className="mb-2">
                            <span className={`badge ${executeResult.status === 'completed' ? 'bg-success' : executeResult.status === 'failed' ? 'bg-danger' : executeResult.status === 'long_running' ? 'bg-warning' : 'bg-secondary'}`}>{executeResult.status}</span>
                          </div>
                          <div className="mb-2">
                            <label className="form-label">Output</label>
                            <pre style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', padding: '8px', border: '1px solid var(--border-primary)', borderRadius: 6, maxHeight: '240px', overflow: 'auto' }}>{toSafeString(executeResult.output)}</pre>
                          </div>
                          {executeResult.error && (
                            <div className="mb-2">
                              <label className="form-label">Error</label>
                              <pre style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', padding: '8px', border: '1px solid var(--border-primary)', borderRadius: 6, maxHeight: '240px', overflow: 'auto' }}>{toSafeString(executeResult.error)}</pre>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
                <div className="modal-footer">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => {
                      if (ws && ws.readyState === WebSocket.OPEN) {
                        try { ws.close(); } catch {}
                      }
                      setLiveStatus('idle');
                      setLiveOutput([]);
                      setShowExecuteModal(false);
                    }}
                    disabled={executing}
                  >
                    Close
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={async () => {
                      setExecuting(true);
                      setExecuteResult(null);
                      setLiveOutput([]);
                      setJobIdState(null);
                      setLinkedExecId(null);
                      try {
                        if (targetType === 'server') {
                          if (!executeForm.server_id) { alert('Please select a server'); setExecuting(false); return; }
                          // Live output via WebSocket
                          setLiveStatus('connecting');
                          setLiveOutput([]);
                          const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
                          const host = window.location.host;
                          const wsUrl = `${proto}://${host}/api/ws/execute/${encodeURIComponent(executeScript.id)}/${encodeURIComponent(executeForm.server_id)}`;
                          try {
                            const socket = new WebSocket(wsUrl);
                            setWs(socket);
                            socket.onopen = () => {
                              setLiveStatus('running');
                              setLiveOutput(prev => [...prev, 'Connected. Streaming output...']);
                            };
                            socket.onmessage = (evt) => {
                              try {
                                const msg = JSON.parse(evt.data);
                                if (msg.type === 'output' || msg.type === 'error_output') {
                                  setLiveOutput(prev => [...prev, msg.data]);
                                } else if (msg.type === 'finished') {
                                  if (msg.execution_id) setLinkedExecId(msg.execution_id);
                                  setLiveStatus('done');
                                  try { socket.close(); } catch {}
                                } else if (msg.type === 'error' || msg.type === 'ssh_failed') {
                                  setLiveStatus('error');
                                  setLiveOutput(prev => [...prev, `Error: ${msg.message}`]);
                                  try { socket.close(); } catch {}
                                }
                              } catch (e) {
                                setLiveOutput(prev => [...prev, String(evt.data || '')]);
                              }
                            };
                            socket.onerror = () => {
                              setLiveStatus('error');
                              setLiveOutput(prev => [...prev, 'WebSocket error.']);
                            };
                            socket.onclose = () => {
                              // keep status as set
                            };
                          } catch (e) {
                            setLiveStatus('error');
                            setLiveOutput(prev => [...prev, `Failed to open WebSocket: ${e.message}`]);
                          }
                        } else {
                          if (!groupId) { alert('Please select a group'); setExecuting(false); return; }
                          const params = new URLSearchParams();
                          params.set('group_id', groupId);
                          if (overrideEnabled) {
                            if (overrideConcurrency) params.set('concurrency', String(overrideConcurrency));
                            if (overrideTimeout) params.set('timeout_seconds', String(overrideTimeout));
                            params.set('continue_on_error', String(overrideContinueOnError));
                          }
                          const resp = await axios.post(`/api/scripts/${executeScript.id}/execute-group?${params.toString()}`, null);
                          setExecuteResult(resp.data);
                        }
                      } catch (e) {
                        const msg = e.response?.data?.detail || e.message;
                        setExecuteResult({ status: 'failed', output: '', error: msg });
                        setLiveStatus('error');
                        setLiveOutput(prev => [...prev, `Error: ${msg}`]);
                      } finally {
                        setExecuting(false);
                      }
                    }}
                    disabled={executing}
                  >
                    {executing ? (
                      <>
                        <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                        Running...
                      </>
                    ) : (
                      <>
                        <i className="bi bi-play-fill me-2"></i>
                        Run
                      </>
                    )}
                  </button>
                </div>
                {/* Live Output Panel (single server via WebSocket) */}
                {targetType === 'server' && (
                  <div className="px-3 pb-3">
                    <div className="d-flex align-items-center gap-2 mb-2"></div>
                    <label className="form-label">Live Output</label>
                    <div style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', padding: '8px', border: '1px solid var(--border-primary)', borderRadius: 6, height: '260px', overflow: 'auto', whiteSpace: 'pre-wrap' }}>
                      {liveOutput.length === 0 ? (
                        <span className="text-muted">{liveStatus === 'connecting' ? 'Connecting...' : liveStatus === 'running' ? 'Waiting for output...' : 'No output yet'}</span>
                      ) : (
                        liveOutput.map((line, idx) => (
                          <div key={idx}>{line}</div>
                        ))
                      )}
                    </div>
                    {ws && liveStatus === 'running' && (
                      <div className="mt-2 d-flex gap-2">
                        <button type="button" className="btn btn-outline-danger btn-sm" onClick={() => { try { ws.close(); } catch {}; }}>
                          <i className="bi bi-stop-circle me-1"></i>Stop Streaming
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
        {/* Create Script Modal */}
        {showCreateModal && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog modal-xl">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-plus-circle me-2"></i>
                    Create New Script
                  </h5>
                  <button
                    type="button"
                    className="btn-close btn-close-white"
                    onClick={() => setShowCreateModal(false)}
                  ></button>
                </div>
                <form onSubmit={handleCreateSubmit}>
                  <div className="modal-body">
                    <div className="row">
                      <div className="col-md-6">
                        <div className="mb-3">
                          <label htmlFor="newScriptName" className="form-label">Script Name</label>
                          <input
                            type="text"
                            className="form-control"
                            id="newScriptName"
                            value={createForm.name || ''}
                            onChange={(e) => setCreateForm({...createForm, name: e.target.value})}
                            required
                          />
                        </div>
                      </div>
                      <div className="col-md-3">
                        <div className="mb-3">
                          <label htmlFor="newScriptType" className="form-label">Script Type</label>
                          <select
                            className="form-control"
                            id="newScriptType"
                            value={createForm.script_type || 'bash'}
                            onChange={(e) => setCreateForm({...createForm, script_type: e.target.value})}
                          >
                            {scriptTypes.map(type => (
                              <option key={type.value} value={type.value}>
                                {type.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                      <div className="col-md-3">
                        <div className="mb-3">
                          <label htmlFor="newScriptCategory" className="form-label">Category</label>
                          <select
                            className="form-control"
                            id="newScriptCategory"
                            value={createForm.category || 'general'}
                            onChange={(e) => setCreateForm({...createForm, category: e.target.value})}
                          >
                            {categories.map(cat => (
                              <option key={cat.value} value={cat.value}>
                                {cat.label}
                              </option>
                            ))}
                          </select>
                        </div>
                      </div>
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newScriptDescription" className="form-label">Description</label>
                      <textarea
                        className="form-control"
                        id="newScriptDescription"
                        rows="2"
                        value={createForm.description || ''}
                        onChange={(e) => setCreateForm({...createForm, description: e.target.value})}
                        placeholder="Describe what this script does..."
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newScriptContent" className="form-label">Script Content</label>
                      <MonacoCodeEditor
                        value={createForm.content || ''}
                        onChange={(e) => setCreateForm({...createForm, content: e.target.value})}
                        language={createForm.script_type || 'bash'}
                      />
                    </div>
                                          <div className="mb-3">
                        <label htmlFor="newScriptParameters" className="form-label">Parameters (Optional)</label>
                        <textarea
                          className="form-control"
                          id="newScriptParameters"
                          rows="3"
                          value={createForm.parameters || ''}
                          onChange={(e) => setCreateForm({...createForm, parameters: e.target.value})}
                          placeholder='JSON format: {"param1": "value1", "param2": "value2"}'
                        />
                        <div className="form-text">
                          <i className="bi bi-info-circle me-1"></i>
                          Define script parameters in JSON format
                        </div>
                      </div>
                      <div className="mb-3">
                        <label htmlFor="newScriptTimeout" className="form-label">Timeout (seconds)</label>
                        <div className="input-group">
                          <input
                            type="number"
                            className="form-control"
                            id="newScriptTimeout"
                            value={createForm.per_server_timeout_seconds || ''}
                            onChange={(e) => setCreateForm({...createForm, per_server_timeout_seconds: e.target.value ? parseInt(e.target.value) : null})}
                            placeholder="60"
                            min="0"
                            max="3600"
                          />
                          <div className="input-group-text">
                            <div className="form-check">
                              <input
                                className="form-check-input"
                                type="checkbox"
                                id="newScriptInfiniteTimeout"
                                checked={createForm.per_server_timeout_seconds === 0}
                                onChange={(e) => setCreateForm({...createForm, per_server_timeout_seconds: e.target.checked ? 0 : 60})}
                              />
                              <label className="form-check-label" htmlFor="newScriptInfiniteTimeout">
                                Infinite
                              </label>
                            </div>
                          </div>
                        </div>
                        <div className="form-text">
                          <i className="bi bi-info-circle me-1"></i>
                          Set to 0 for infinite timeout (useful for monitoring scripts like ping)
                        </div>
                      </div>
                  </div>
                  <div className="modal-footer">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setShowCreateModal(false)}
                    >
                      Cancel
                    </button>
                    <button type="submit" className="btn btn-primary">
                      <i className="bi bi-check-circle me-2"></i>
                      Create Script
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Delete Confirmation Modal */}
        {showDeleteModal && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-exclamation-triangle me-2 text-warning"></i>
                    Confirm Delete
                  </h5>
                  <button
                    type="button"
                    className="btn-close btn-close-white"
                    onClick={() => setShowDeleteModal(false)}
                  ></button>
                </div>
                <div className="modal-body">
                  <p>Are you sure you want to delete script <strong>{scriptToDelete?.name}</strong>?</p>
                  <p className="text-danger">
                    <i className="bi bi-exclamation-circle me-2"></i>
                    This action cannot be undone.
                  </p>
                </div>
                <div className="modal-footer">
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={() => setShowDeleteModal(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={confirmDelete}
                  >
                    <i className="bi bi-trash me-2"></i>
                    Delete Script
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Export Script Modal */}
        {showExportModal && exportScript && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-shop me-2"></i>
                    Export to Marketplace: {exportScript.name}
                  </h5>
                  <button
                    type="button"
                    className="btn-close btn-close-white"
                    onClick={() => setShowExportModal(false)}
                  ></button>
                </div>
                <div className="modal-body">
                  <div className="form-check form-switch mb-3">
                    <input
                      className="form-check-input"
                      type="checkbox"
                      id="exportPublicSwitch"
                      checked={exportForm.is_public}
                      onChange={(e) => setExportForm({ ...exportForm, is_public: e.target.checked })}
                    />
                    <label className="form-check-label" htmlFor="exportPublicSwitch">Public</label>
                  </div>
                  <div className="mb-3">
                    <label className="form-label">Description</label>
                    <textarea
                      className="form-control"
                      rows="3"
                      value={exportForm.description}
                      onChange={(e) => setExportForm({ ...exportForm, description: e.target.value })}
                      placeholder="Short description for marketplace"
                    />
                  </div>
                  <div className="mb-2">
                    <label className="form-label">Tags</label>
                    <input
                      type="text"
                      className="form-control"
                      value={exportForm.tagsText}
                      onChange={(e) => setExportForm({ ...exportForm, tagsText: e.target.value })}
                      placeholder="comma,separated,tags"
                    />
                    <div className="form-text">Comma-separated. Example: monitoring,bash,linux</div>
                  </div>
                </div>
                <div className="modal-footer">
                  <button type="button" className="btn btn-secondary" onClick={() => setShowExportModal(false)}>
                    Cancel
                  </button>
                  <button type="button" className="btn btn-primary" onClick={submitExport}>
                    <i className="bi bi-cloud-upload me-2"></i>
                    Export
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ScriptManagement;
