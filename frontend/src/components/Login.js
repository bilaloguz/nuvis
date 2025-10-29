import React, { useState } from 'react';
import '../styles/login.css';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

const Login = () => {
  const [formData, setFormData] = useState({
    username: '',
    password: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (!formData.username || !formData.password) {
      setError('Please fill in all fields');
      setLoading(false);
      return;
    }

    const result = await login(formData.username, formData.password);
    
    if (result.success) {
      navigate('/dashboard');
    } else {
      setError(result.error);
    }
    
    setLoading(false);
  };

  return (
    <div className="login-bg">
      <div className="login-card">
        <div className="text-center mb-4">
          <div className="login-logo-container">
            <div className="login-logo-icon">
              <i className="bi bi-terminal" style={{ color: 'white', fontSize: '3rem' }}></i>
            </div>
            <div className="login-logo-text-container">
              <div className="login-logo-text">biRun</div>
              <div className="login-logo-subtitle">Script Manager</div>
            </div>
          </div>
          {/* Description removed as requested */}
        </div>

        {error && (
          <div className="alert alert-danger border-0" role="alert" style={{backgroundColor: 'rgba(239, 68, 68, 0.1)'}}>
            <i className="bi bi-exclamation-circle me-2"></i>
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} autoComplete="off">
          <div className="mb-3">
            <label htmlFor="username" className="form-label">Username</label>
            <input type="text" className="form-control" id="username" name="username" placeholder="Enter your username" value={formData.username} onChange={handleChange} required autoFocus />
          </div>
          <div className="mb-3">
            <label htmlFor="password" className="form-label">Password</label>
            <input type="password" className="form-control" id="password" name="password" placeholder="Enter your password" value={formData.password} onChange={handleChange} required />
          </div>
          <button type="submit" className="btn btn-primary w-100 mt-2" id="sshConnectBtn" disabled={loading}>
            {!loading ? (
              <>
                <i className="bi bi-terminal me-2"></i>
                Sign In
              </>
            ) : (
              <span className="btn-loading">
                <i className="bi bi-arrow-repeat me-2"></i>
                Signing in...
              </span>
            )}
          </button>
        </form>

        {/* Features row removed as requested */}
      </div>
    </div>
  );
};

export default Login;
