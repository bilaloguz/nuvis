import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import './AuditLogs.css';

const AuditLogs = () => {
  const { user: currentUser } = useAuth();
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filters, setFilters] = useState({
    action: '',
    resource_type: '',
    user_id: '',
    success: '',
    from_date: '',
    to_date: ''
  });
  const [pagination, setPagination] = useState({
    page: 1,
    size: 50,
    total: 0
  });
  const [availableActions, setAvailableActions] = useState([]);
  const [availableResourceTypes, setAvailableResourceTypes] = useState([]);
  const [users, setUsers] = useState([]);
  const [expandedLogIds, setExpandedLogIds] = useState(new Set());

  useEffect(() => {
    if (currentUser?.role === 'admin') {
      fetchAuditLogs();
      fetchFilterOptions();
      fetchUsers();
    }
  }, [currentUser, filters, pagination.page, pagination.size]);

  const fetchAuditLogs = async () => {
    try {
      setLoading(true);
      const params = {
        page: pagination.page,
        size: pagination.size,
        ...filters
      };
      
      // Remove empty filters
      Object.keys(params).forEach(key => {
        if (params[key] === '' || params[key] === null || params[key] === undefined) {
          delete params[key];
        }
      });

      const response = await axios.get('/api/audit/', { params });
      setLogs(response.data.logs);
      setPagination(prev => ({
        ...prev,
        total: response.data.total
      }));
    } catch (error) {
      setError('Failed to fetch audit logs');
      console.error('Error fetching audit logs:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchFilterOptions = async () => {
    try {
      const [actionsRes, typesRes] = await Promise.all([
        axios.get('/api/audit/actions'),
        axios.get('/api/audit/resource-types')
      ]);
      setAvailableActions(actionsRes.data.actions);
      setAvailableResourceTypes(typesRes.data.resource_types);
    } catch (error) {
      console.error('Error fetching filter options:', error);
    }
  };

  const fetchUsers = async () => {
    try {
      const response = await axios.get('/api/users/');
      setUsers(response.data.users || []);
    } catch (error) {
      console.error('Error fetching users:', error);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPagination(prev => ({ ...prev, page: 1 })); // Reset to first page
  };

  const handlePageChange = (newPage) => {
    setPagination(prev => ({ ...prev, page: newPage }));
  };

  const handlePageSizeChange = (newSize) => {
    setPagination(prev => ({ ...prev, page: 1, size: newSize }));
  };

  const clearFilters = () => {
    setFilters({
      action: '',
      resource_type: '',
      user_id: '',
      success: '',
      from_date: '',
      to_date: ''
    });
    setPagination(prev => ({ ...prev, page: 1 }));
  };

  const toggleExpanded = (logId) => {
    setExpandedLogIds(prev => {
      const newSet = new Set(prev);
      if (newSet.has(logId)) {
        newSet.delete(logId);
      } else {
        newSet.add(logId);
      }
      return newSet;
    });
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const getActionIcon = (action) => {
    const iconMap = {
      'user_login': 'bi-box-arrow-in-right',
      'user_logout': 'bi-box-arrow-left',
      'user_create': 'bi-person-plus',
      'user_update': 'bi-person-gear',
      'user_delete': 'bi-person-x',
      'server_create': 'bi-server',
      'server_update': 'bi-server',
      'server_delete': 'bi-server',
      'script_create': 'bi-file-earmark-code',
      'script_update': 'bi-file-earmark-code',
      'script_execute': 'bi-play-circle',
      'schedule_create': 'bi-calendar-plus',
      'schedule_update': 'bi-calendar-check',
      'group_create': 'bi-collection',
      'group_update': 'bi-collection',
      'settings_update': 'bi-gear'
    };
    return iconMap[action] || 'bi-activity';
  };

  const getActionColor = (action) => {
    if (action.includes('delete')) return 'text-danger';
    if (action.includes('create')) return 'text-success';
    if (action.includes('update')) return 'text-warning';
    if (action.includes('login') || action.includes('logout')) return 'text-info';
    return 'text-primary';
  };

  const exportAudit = async (format) => {
    try {
      // Export current page with active filters
      const rows = logs || [];
      if (format === 'json') {
        const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'audit_logs.json';
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
        return;
      }
      // CSV
      const headers = ['id','created_at','user','action','resource_type','resource_id','ip_address','success','details'];
      const escapeCell = (val) => {
        if (val == null) return '';
        const s = String(val);
        if (/[",\n]/.test(s)) return '"' + s.replace(/"/g,'""') + '"';
        return s;
      };
      const lines = [headers.join(',')];
      rows.forEach(r => {
        const line = [
          r.id,
          r.created_at,
          (r.user && r.user.username) ? r.user.username : 'system',
          r.action,
          r.resource_type || '',
          r.resource_id || '',
          r.ip_address || '',
          r.success ? 'true' : 'false',
          r.details || ''
        ].map(escapeCell).join(',');
        lines.push(line);
      });
      const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'audit_logs.csv';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Audit export failed', e);
      alert('Export failed');
    }
  };

  if (currentUser?.role !== 'admin') {
    return (
      <div className="main-content">
        <div className="container-fluid">
          <div className="alert alert-warning border-0" role="alert" style={{backgroundColor: 'rgba(245, 158, 11, 0.1)'}}>
            <h4 className="alert-heading">
              <i className="bi bi-exclamation-triangle me-2"></i>
              Access Denied
            </h4>
            <p>You need admin privileges to view audit logs.</p>
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

  const totalPages = Math.ceil(pagination.total / pagination.size);

  return (
    <div className="main-content">
      <div className="container-fluid">
        <div className="d-flex justify-content-between align-items-center mb-4">
          <h1>
            <i className="bi bi-shield-check me-3"></i>
            Audit Logs
          </h1>
          <div className="btn-group" role="group">
            <button type="button" className="btn btn-outline-light btn-sm" onClick={() => exportAudit('csv')} title="Export CSV">
              <i className="bi bi-download me-1"></i>CSV
            </button>
            <button type="button" className="btn btn-outline-light btn-sm" onClick={() => exportAudit('json')} title="Export JSON">
              <i className="bi bi-filetype-json me-1"></i>JSON
            </button>
          </div>
        </div>

        {error && (
          <div className="alert alert-danger border-0" role="alert" style={{backgroundColor: 'rgba(239, 68, 68, 0.1)'}}>
            <i className="bi bi-exclamation-circle me-2"></i>
            {error}
          </div>
        )}

        {/* Filters - Same layout as executions table */}
        <div className="card shadow-lg">
          <div className="card-header d-flex flex-wrap gap-2 align-items-center">
            <label className="form-label mb-0 me-2">Date range:</label>
            <input 
              type="date" 
              className="form-control form-control-sm bg-dark text-light border border-secondary" 
              style={{maxWidth:'180px'}} 
              value={filters.from_date} 
              onChange={(e) => handleFilterChange('from_date', e.target.value)} 
            />
            <span className="text-muted">to</span>
            <input 
              type="date" 
              className="form-control form-control-sm bg-dark text-light border border-secondary" 
              style={{maxWidth:'180px'}} 
              value={filters.to_date} 
              onChange={(e) => handleFilterChange('to_date', e.target.value)} 
            />
            <div className="d-flex align-items-center gap-2 ms-auto">
              <label className="form-label mb-0">Page Size:</label>
              <select
                className="form-select form-select-sm bg-dark text-light border border-secondary"
                style={{width: '80px'}}
                value={pagination.size}
                onChange={(e) => handlePageSizeChange(parseInt(e.target.value))}
              >
                <option value={25}>25</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </div>
          </div>
          <div className="card-body">
            <div className="table-responsive" style={{overflow: 'visible'}}>
              <table className="table table-sm table-hover table-striped">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>User</th>
                    <th>Action</th>
                    <th>Resource</th>
                    <th>IP Address</th>
                    <th>Status</th>
                    <th>Details</th>
                  </tr>
                  <tr>
                    <th></th>
                    <th>
                      <select 
                        className="form-select form-select-sm bg-dark text-light border border-secondary" 
                        value={filters.user_id} 
                        onChange={(e) => handleFilterChange('user_id', e.target.value)}
                      >
                        <option value="">All Users</option>
                        {users.map(user => (
                          <option key={user.id} value={user.id}>{user.username}</option>
                        ))}
                      </select>
                    </th>
                    <th>
                      <select 
                        className="form-select form-select-sm bg-dark text-light border border-secondary" 
                        value={filters.action} 
                        onChange={(e) => handleFilterChange('action', e.target.value)}
                      >
                        <option value="">All Actions</option>
                        {availableActions.map(action => (
                          <option key={action} value={action}>{action}</option>
                        ))}
                      </select>
                    </th>
                    <th>
                      <select 
                        className="form-select form-select-sm bg-dark text-light border border-secondary" 
                        value={filters.resource_type} 
                        onChange={(e) => handleFilterChange('resource_type', e.target.value)}
                      >
                        <option value="">All Types</option>
                        {availableResourceTypes.map(type => (
                          <option key={type} value={type}>{type}</option>
                        ))}
                      </select>
                    </th>
                    <th></th>
                    <th>
                      <select 
                        className="form-select form-select-sm bg-dark text-light border border-secondary" 
                        value={filters.success} 
                        onChange={(e) => handleFilterChange('success', e.target.value)}
                      >
                        <option value="">All</option>
                        <option value="true">Success</option>
                        <option value="false">Failed</option>
                      </select>
                    </th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <React.Fragment key={log.id}>
                      <tr>
                        <td>
                          <small>{formatDate(log.created_at)}</small>
                        </td>
                        <td>
                          {log.user ? (
                            <span className="badge bg-primary">{log.user.username}</span>
                          ) : (
                            <span className="badge bg-secondary">System</span>
                          )}
                        </td>
                        <td>
                          <span className={`d-flex align-items-center ${getActionColor(log.action)}`}>
                            <i className={`bi ${getActionIcon(log.action)} me-2`}></i>
                            {log.action}
                          </span>
                        </td>
                        <td>
                          {log.resource_type && log.resource_id ? (
                            <span className="badge bg-info">
                              {log.resource_type}:{log.resource_id}
                            </span>
                          ) : (
                            <span className="text-muted">—</span>
                          )}
                        </td>
                        <td>
                          <small className="text-muted">{log.ip_address || '—'}</small>
                        </td>
                        <td>
                          <span className={`badge ${log.success ? 'bg-success' : 'bg-danger'}`}>
                            {log.success ? 'Success' : 'Failed'}
                          </span>
                        </td>
                        <td>
                          {log.details ? (
                            <button
                              className="btn btn-sm btn-outline-secondary"
                              onClick={() => toggleExpanded(log.id)}
                              title="Click to view details"
                            >
                              <i className={`bi ${expandedLogIds.has(log.id) ? 'bi-chevron-up' : 'bi-chevron-down'} me-1`}></i>
                              {expandedLogIds.has(log.id) ? 'Hide' : 'View'}
                            </button>
                          ) : (
                            <span className="text-muted">—</span>
                          )}
                        </td>
                      </tr>
                      {/* Expanded details row */}
                      {log.details && expandedLogIds.has(log.id) && (
                        <tr className="audit-details-row">
                          <td colSpan="7">
                            <div className="audit-details-content p-3">
                              <h6 className="mb-2">
                                <i className="bi bi-info-circle me-2"></i>
                                Action Details
                              </h6>
                              <pre className="audit-details-json mb-0">
                                {log.details}
                              </pre>
                            </div>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))}
                  {logs.length === 0 && (
                    <tr>
                      <td colSpan="7" className="text-center text-muted">
                        No audit logs found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="d-flex justify-content-center mt-3">
            <nav aria-label="Audit logs pagination">
              <ul className="pagination">
                <li className={`page-item ${pagination.page === 1 ? 'disabled' : ''}`}>
                  <button
                    className="page-link"
                    onClick={() => handlePageChange(pagination.page - 1)}
                    disabled={pagination.page === 1}
                  >
                    Previous
                  </button>
                </li>
                
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const pageNum = i + 1;
                  return (
                    <li key={pageNum} className={`page-item ${pageNum === pagination.page ? 'active' : ''}`}>
                      <button
                        className="page-link"
                        onClick={() => handlePageChange(pageNum)}
                      >
                        {pageNum}
                      </button>
                    </li>
                  );
                })}
                
                <li className={`page-item ${pagination.page === totalPages ? 'disabled' : ''}`}>
                  <button
                    className="page-link"
                    onClick={() => handlePageChange(pagination.page + 1)}
                    disabled={pagination.page === totalPages}
                  >
                    Next
                  </button>
                </li>
              </ul>
            </nav>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuditLogs;
