import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';

const UserProfile = () => {
  const { user, logout } = useAuth();
  const [editMode, setEditMode] = useState(false);
  const [editForm, setEditForm] = useState({
    username: user?.username || '',
    email: user?.email || ''
  });
  const [passwordForm, setPasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  });
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState({ type: '', text: '' });

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ type: '', text: '' });

    try {
      const response = await axios.put(`/api/users/${user.id}`, editForm);
      
      // Update the user context (you might need to add an updateUser function to AuthContext)
      // For now, we'll just show success message
      setMessage({ type: 'success', text: 'Profile updated successfully!' });
      setEditMode(false);
      
      // Reload the page to reflect changes (simple approach)
      setTimeout(() => window.location.reload(), 1500);
    } catch (error) {
      setMessage({ 
        type: 'danger', 
        text: error.response?.data?.detail || 'Failed to update profile' 
      });
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage({ type: '', text: '' });

    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setMessage({ type: 'danger', text: 'New passwords do not match' });
      setLoading(false);
      return;
    }

    if (passwordForm.new_password.length < 6) {
      setMessage({ type: 'danger', text: 'New password must be at least 6 characters long' });
      setLoading(false);
      return;
    }

    try {
      await axios.put(`/api/users/${user.id}/password`, {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password
      });
      
      setMessage({ type: 'success', text: 'Password updated successfully!' });
      setPasswordForm({
        current_password: '',
        new_password: '',
        confirm_password: ''
      });
    } catch (error) {
      setMessage({ 
        type: 'danger', 
        text: error.response?.data?.detail || 'Failed to update password' 
      });
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
  };

  if (!user) {
    return (
      <div className="main-content">
        <div className="container">
          <div className="alert alert-warning border-0" role="alert" style={{backgroundColor: 'rgba(245, 158, 11, 0.1)'}}>
            <h4 className="alert-heading">
              <i className="bi bi-exclamation-triangle me-2"></i>
              User Not Found
            </h4>
            <p>Unable to load user profile.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="main-content">
      <div className="container">
        <div className="row">
          <div className="col-12">
            <div className="d-flex justify-content-between align-items-center mb-4">
              <h1>
                <i className="bi bi-person-circle me-3"></i>
                User Profile
              </h1>
              <button
                className="btn btn-outline-primary"
                onClick={() => setEditMode(!editMode)}
              >
                <i className={`bi ${editMode ? 'bi-x-circle' : 'bi-pencil'} me-2`}></i>
                {editMode ? 'Cancel Edit' : 'Edit Profile'}
              </button>
            </div>

            {message.text && (
              <div className={`alert alert-${message.type} border-0`} role="alert" 
                   style={{backgroundColor: message.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)'}}>
                <i className={`bi ${message.type === 'success' ? 'bi-check-circle' : 'bi-exclamation-circle'} me-2`}></i>
                {message.text}
              </div>
            )}

            <div className="row">
              <div className="col-md-6">
                <div className="card shadow-lg mb-4">
                  <div className="card-header">
                    <h5 className="card-title mb-0">
                      <i className="bi bi-person-badge me-2"></i>
                      Profile Information
                    </h5>
                  </div>
                  <div className="card-body">
                    {!editMode ? (
                      <div>
                        <div className="mb-3">
                          <strong className="text-info">Username:</strong> 
                          <span className="ms-2">{user.username}</span>
                        </div>
                        <div className="mb-3">
                          <strong className="text-info">Email:</strong> 
                          <span className="ms-2">{user.email}</span>
                        </div>
                        <div className="mb-3">
                          <strong className="text-info">Role:</strong> 
                          <span className={`badge ms-2 ${user.role === 'admin' ? 'bg-danger' : 'bg-primary'}`}>
                            {user.role}
                          </span>
                        </div>
                        <div className="mb-3">
                          <strong className="text-info">Member since:</strong> 
                          <span className="ms-2">{formatDate(user.created_at)}</span>
                        </div>
                        {user.updated_at && (
                          <div className="mb-3">
                            <strong className="text-info">Last updated:</strong> 
                            <span className="ms-2">{formatDate(user.updated_at)}</span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <form onSubmit={handleEditSubmit}>
                        <div className="mb-3">
                          <label htmlFor="username" className="form-label">Username</label>
                          <input
                            type="text"
                            className="form-control"
                            id="username"
                            name="username"
                            value={editForm.username}
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
                            name="email"
                            value={editForm.email}
                            onChange={(e) => setEditForm({...editForm, email: e.target.value})}
                            required
                          />
                        </div>
                        <div className="d-grid gap-2">
                          <button
                            type="submit"
                            className="btn btn-primary"
                            disabled={loading}
                          >
                            <i className="bi bi-check-circle me-2"></i>
                            {loading ? 'Saving...' : 'Save Changes'}
                          </button>
                        </div>
                      </form>
                    )}
                  </div>
                </div>
              </div>

              <div className="col-md-6">
                <div className="card shadow-lg">
                  <div className="card-header">
                    <h5 className="card-title mb-0">
                      <i className="bi bi-shield-lock me-2"></i>
                      Change Password
                    </h5>
                  </div>
                  <div className="card-body">
                    <form onSubmit={handlePasswordSubmit}>
                      <div className="mb-3">
                        <label htmlFor="current_password" className="form-label">Current Password</label>
                        <input
                          type="password"
                          className="form-control"
                          id="current_password"
                          name="current_password"
                          value={passwordForm.current_password}
                          onChange={(e) => setPasswordForm({...passwordForm, current_password: e.target.value})}
                          required
                        />
                      </div>
                      <div className="mb-3">
                        <label htmlFor="new_password" className="form-label">New Password</label>
                        <input
                          type="password"
                          className="form-control"
                          id="new_password"
                          name="new_password"
                          value={passwordForm.new_password}
                          onChange={(e) => setPasswordForm({...passwordForm, new_password: e.target.value})}
                          required
                        />
                      </div>
                      <div className="mb-3">
                        <label htmlFor="confirm_password" className="form-label">Confirm New Password</label>
                        <input
                          type="password"
                          className="form-control"
                          id="confirm_password"
                          name="confirm_password"
                          value={passwordForm.confirm_password}
                          onChange={(e) => setPasswordForm({...passwordForm, confirm_password: e.target.value})}
                          required
                        />
                      </div>
                      <div className="d-grid gap-2">
                        <button
                          type="submit"
                          className="btn btn-warning"
                          disabled={loading}
                        >
                          <i className="bi bi-shield-check me-2"></i>
                          {loading ? 'Updating...' : 'Update Password'}
                        </button>
                      </div>
                    </form>
                  </div>
                </div>
              </div>
            </div>

            <div className="row mt-4">
              <div className="col-12">
                <div className="card shadow-lg">
                  <div className="card-header">
                    <h5 className="card-title mb-0">
                      <i className="bi bi-gear me-2"></i>
                      Account Actions
                    </h5>
                  </div>
                  <div className="card-body">
                    <div className="d-grid gap-2 d-md-block">
                      <button
                        className="btn btn-outline-danger"
                        onClick={logout}
                      >
                        <i className="bi bi-box-arrow-right me-2"></i>
                        Logout
                      </button>
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

export default UserProfile;
