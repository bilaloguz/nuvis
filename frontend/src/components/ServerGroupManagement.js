import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import './ServerGroupManagement.css';

const ServerGroupManagement = () => {
  const { user: currentUser } = useAuth();
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingGroup, setEditingGroup] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [groupToDelete, setGroupToDelete] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    name: '',
    description: '',
    color: '#6366f1'
  });

  useEffect(() => {
    if (currentUser?.role === 'admin') {
      fetchGroups();
    }
  }, [currentUser]);

  const fetchGroups = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/server-groups/');
      setGroups(response.data.groups);
    } catch (error) {
      setError('Failed to fetch server groups');
      console.error('Error fetching server groups:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (group) => {
    setEditingGroup(group);
    setEditForm({
      name: group.name,
      description: group.description || '',
      color: group.color
    });
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.put(`/api/server-groups/${editingGroup.id}`, editForm);
      
      // Update the groups list
      setGroups(groups.map(g => g.id === editingGroup.id ? response.data : g));
      
      // Reset form
      setEditingGroup(null);
      setEditForm({});
      
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to update server group');
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    
    if (!createForm.name.trim()) {
      alert('Group name is required');
      return;
    }
    
    try {
      const response = await axios.post('/api/server-groups/', createForm);
      setGroups([...groups, response.data]);
      setShowCreateModal(false);
      setCreateForm({
        name: '',
        description: '',
        color: '#6366f1'
      });
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to create server group');
    }
  };

  const handleDelete = (group) => {
    setGroupToDelete(group);
    setShowDeleteModal(true);
  };

  const confirmDelete = async () => {
    try {
      await axios.delete(`/api/server-groups/${groupToDelete.id}`);
      
      // Remove group from list
      setGroups(groups.filter(g => g.id !== groupToDelete.id));
      
      // Close modal
      setShowDeleteModal(false);
      setGroupToDelete(null);
      
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to delete server group');
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
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
            <p>You need admin privileges to access server group management.</p>
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
            <i className="bi bi-collection me-3"></i>
            Server Groups
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
                    <th>Description</th>
                    <th>Color</th>
                    <th>Servers</th>
                    <th>Created</th>
                    <th className="text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {groups.map((group) => (
                    <tr key={group.id}>
                      <td>
                        <strong>{group.name}</strong>
                      </td>
                      <td>{group.description || '-'}</td>
                      <td>
                        <div className="d-flex align-items-center">
                          <div 
                            className="color-preview me-2" 
                            style={{
                              width: '20px', 
                              height: '20px', 
                              backgroundColor: group.color,
                              borderRadius: '4px',
                              border: '1px solid var(--border-color)'
                            }}
                          ></div>
                          <span className="text-muted">{group.color}</span>
                        </div>
                      </td>
                      <td>
                        <span className="badge bg-info">
                          {group.servers ? group.servers.length : 0} server{group.servers && group.servers.length !== 1 ? 's' : ''}
                        </span>
                      </td>
                      <td>{formatDate(group.created_at)}</td>
                      <td className="text-center">
                        <div className="btn-group" role="group">
                          <button
                            className="btn btn-outline-primary"
                            onClick={() => handleEdit(group)}
                          >
                            <i className="bi bi-pencil me-1"></i>
                            Edit
                          </button>
                          <button
                            className="btn btn-outline-danger"
                            onClick={() => handleDelete(group)}
                          >
                            <i className="bi bi-trash me-1"></i>
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
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

        {/* Edit Group Modal */}
        {editingGroup && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-pencil-square me-2"></i>
                    Edit Group: {editingGroup.name}
                  </h5>
                  <button
                    type="button"
                    className="btn-close btn-close-white"
                    onClick={() => {
                      setEditingGroup(null);
                      setEditForm({});
                    }}
                  ></button>
                </div>
                <form onSubmit={handleEditSubmit}>
                  <div className="modal-body">
                    <div className="mb-3">
                      <label htmlFor="groupName" className="form-label">Group Name</label>
                      <input
                        type="text"
                        className="form-control"
                        id="groupName"
                        value={editForm.name || ''}
                        onChange={(e) => setEditForm({...editForm, name: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="groupDescription" className="form-label">Description</label>
                      <textarea
                        className="form-control"
                        id="groupDescription"
                        rows="3"
                        value={editForm.description || ''}
                        onChange={(e) => setEditForm({...editForm, description: e.target.value})}
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="groupColor" className="form-label">Color</label>
                      <div className="input-group">
                        <input
                          type="color"
                          className="form-control form-control-color"
                          id="groupColor"
                          value={editForm.color || '#6366f1'}
                          onChange={(e) => setEditForm({...editForm, color: e.target.value})}
                          style={{ width: '60px' }}
                        />
                        <input
                          type="text"
                          className="form-control"
                          value={editForm.color || '#6366f1'}
                          onChange={(e) => setEditForm({...editForm, color: e.target.value})}
                          placeholder="#6366f1"
                        />
                      </div>
                    </div>
                  </div>
                  <div className="modal-footer">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        setEditingGroup(null);
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

        {/* Create Group Modal */}
        {showCreateModal && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-plus-circle me-2"></i>
                    Create New Server Group
                  </h5>
                  <button
                    type="button"
                    className="btn-close btn-close-white"
                    onClick={() => setShowCreateModal(false)}
                  ></button>
                </div>
                <form onSubmit={handleCreateSubmit}>
                  <div className="modal-body">
                    <div className="mb-3">
                      <label htmlFor="newGroupName" className="form-label">Group Name</label>
                      <input
                        type="text"
                        className="form-control"
                        id="newGroupName"
                        value={createForm.name}
                        onChange={(e) => setCreateForm({...createForm, name: e.target.value})}
                        placeholder="e.g., Production, Staging, Development"
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newGroupDescription" className="form-label">Description</label>
                      <textarea
                        className="form-control"
                        id="newGroupDescription"
                        rows="3"
                        value={createForm.description}
                        onChange={(e) => setCreateForm({...createForm, description: e.target.value})}
                        placeholder="Optional description for this server group"
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newGroupColor" className="form-label">Color</label>
                      <div className="input-group">
                        <input
                          type="color"
                          className="form-control form-control-color"
                          id="newGroupColor"
                          value={createForm.color}
                          onChange={(e) => setCreateForm({...createForm, color: e.target.value})}
                          style={{ width: '60px' }}
                        />
                        <input
                          type="text"
                          className="form-control"
                          value={createForm.color}
                          onChange={(e) => setCreateForm({...createForm, color: e.target.value})}
                          placeholder="#6366f1"
                        />
                      </div>
                      <div className="form-text">Choose a color to visually identify this group</div>
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
                      Create Group
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
                  <p>Are you sure you want to delete server group <strong>{groupToDelete?.name}</strong>?</p>
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
                    Delete Group
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

export default ServerGroupManagement;
