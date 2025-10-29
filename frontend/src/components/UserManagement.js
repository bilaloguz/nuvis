import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const UserManagement = () => {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingUser, setEditingUser] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [userToDelete, setUserToDelete] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState({
    username: '',
    email: '',
    password: '',
    role: 'user'
  });

  useEffect(() => {
    if (currentUser?.role === 'admin') {
      fetchUsers();
    }
  }, [currentUser]);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/users/');
      setUsers(response.data.users);
    } catch (error) {
      setError('Failed to fetch users');
      console.error('Error fetching users:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (user) => {
    setEditingUser(user);
    setEditForm({
      username: user.username,
      email: user.email,
      role: user.role
    });
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.put(`/api/users/${editingUser.id}`, editForm);
      
      // Update the users list
      setUsers(users.map(u => u.id === editingUser.id ? response.data : u));
      
      // Reset form
      setEditingUser(null);
      setEditForm({});
      
      // Show success message
      alert('User updated successfully!');
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to update user');
    }
  };

  const handleDelete = (user) => {
    setUserToDelete(user);
    setShowDeleteModal(true);
  };

  const confirmDelete = async () => {
    try {
      await axios.delete(`/api/users/${userToDelete.id}`);
      
      // Remove user from list
      setUsers(users.filter(u => u.id !== userToDelete.id));
      
      // Close modal
      setShowDeleteModal(false);
      setUserToDelete(null);
      
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to delete user');
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    
    // Validate password length
    if (createForm.password.length < 6) {
      alert('Password must be at least 6 characters long');
      return;
    }
    
    try {
      const response = await axios.post('/api/users/', createForm);
      setUsers([...users, response.data]);
      setShowCreateModal(false);
      setCreateForm({
        username: '',
        email: '',
        password: '',
        role: 'user'
      });
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to create user');
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
            <p>You need admin privileges to access user management.</p>
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
            <i className="bi bi-people me-3"></i>
            Users
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
                    <th>Username</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Created</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>
                        <strong>{user.username}</strong>
                      </td>
                      <td>{user.email}</td>
                      <td>
                        <span className={`badge ${user.role === 'admin' ? 'bg-danger' : 'bg-primary'}`}>
                          {user.role}
                        </span>
                      </td>
                      <td>{formatDate(user.created_at)}</td>
                      <td>
                        <div className="btn-group" role="group">
                          <button
                            className="btn btn-outline-primary"
                            onClick={() => handleEdit(user)}
                          >
                            <i className="bi bi-pencil me-1"></i>
                            Edit
                          </button>
                          {user.id !== currentUser.id && (
                            <button
                              className="btn btn-outline-danger"
                              onClick={() => handleDelete(user)}
                            >
                              <i className="bi bi-trash me-1"></i>
                              Delete
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            
            <div className="mt-3 text-center">
              <button className="btn btn-success" onClick={() => setShowCreateModal(true)}>
                <i className="bi bi-person-plus me-2"></i>
                Create
              </button>
            </div>
          </div>
        </div>

        {/* Edit User Modal */}
        {editingUser && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-pencil-square me-2"></i>
                    Edit User: {editingUser.username}
                  </h5>
                  <button
                    type="button"
                    className="btn-close btn-close-white"
                    onClick={() => {
                      setEditingUser(null);
                      setEditForm({});
                    }}
                  ></button>
                </div>
                <form onSubmit={handleEditSubmit}>
                  <div className="modal-body">
                    <div className="mb-3">
                      <label htmlFor="username" className="form-label">Username</label>
                      <input
                        type="text"
                        className="form-control"
                        id="username"
                        value={editForm.username || ''}
                        onChange={(e) => setEditForm({...editForm, username: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="email" className="form-label">Email</label>
                      <input
                        type="email"
                        className="form-control"
                        id="email"
                        value={editForm.email || ''}
                        onChange={(e) => setEditForm({...editForm, email: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="role" className="form-label">Role</label>
                      <select
                        className="form-select"
                        id="role"
                        value={editForm.role || ''}
                        onChange={(e) => setEditForm({...editForm, role: e.target.value})}
                      >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                      </select>
                    </div>
                  </div>
                  <div className="modal-footer">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        setEditingUser(null);
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
                  <p>Are you sure you want to delete user <strong>{userToDelete?.username}</strong>?</p>
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
                    Delete User
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Create User Modal */}
        {showCreateModal && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-person-plus me-2"></i>
                    Create New User
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
                      <label htmlFor="newUsername" className="form-label">Username</label>
                      <input
                        type="text"
                        className="form-control"
                        id="newUsername"
                        value={createForm.username || ''}
                        onChange={(e) => setCreateForm({...createForm, username: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newEmail" className="form-label">Email</label>
                      <input
                        type="email"
                        className="form-control"
                        id="newEmail"
                        value={createForm.email || ''}
                        onChange={(e) => setCreateForm({...createForm, email: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newPassword" className="form-label">Password</label>
                      <input
                        type="password"
                        className="form-control"
                        id="newPassword"
                        value={createForm.password || ''}
                        onChange={(e) => setCreateForm({...createForm, password: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newRole" className="form-label">Role</label>
                      <select
                        className="form-select"
                        id="newRole"
                        value={createForm.role || ''}
                        onChange={(e) => setCreateForm({...createForm, role: e.target.value})}
                      >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                      </select>
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
                      Create User
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

export default UserManagement;
