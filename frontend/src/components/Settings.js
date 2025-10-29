import React, { useEffect, useState } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';

const Settings = () => {
  const { user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    smtp_host: '',
    smtp_port: 587,
    smtp_user: '',
    smtp_pass: '',
    from_email: '',
    digest_to_emails: '',
    digest_only_failed: false,
    ssh_key_type: 'rsa',
    virtual_timeout_duration: 60,
    long_running_delay_seconds: 300,
    schedule_trigger_tolerance_seconds: 30,
    access_token_expire_minutes: 30,
    max_concurrent_executions: 8
  });

  useEffect(() => {
    const init = async () => {
      try {
        setLoading(true);
        const res = await axios.get('/api/settings/');
        setForm({
          smtp_host: res.data.smtp_host || '',
          smtp_port: res.data.smtp_port || 587,
          smtp_user: res.data.smtp_user || '',
          smtp_pass: res.data.smtp_pass || '',
          from_email: res.data.from_email || '',
          digest_to_emails: res.data.digest_to_emails || '',
          digest_only_failed: !!res.data.digest_only_failed,
          ssh_key_type: res.data.ssh_key_type || 'rsa',
          virtual_timeout_duration: res.data.virtual_timeout_duration || 60,
          long_running_delay_seconds: res.data.long_running_delay_seconds || 300,
          schedule_trigger_tolerance_seconds: res.data.schedule_trigger_tolerance_seconds || 30,
          access_token_expire_minutes: res.data.access_token_expire_minutes || 30,
          max_concurrent_executions: res.data.max_concurrent_executions || 8
        });
      } catch (e) {
        setError('Failed to load settings');
      } finally {
        setLoading(false);
      }
    };
    if (user?.role === 'admin') init();
  }, [user]);

  const onSave = async (e) => {
    e.preventDefault();
    try {
      setSaving(true);
      // Basic client-side validation
      const vt = Number(form.virtual_timeout_duration);
      const lr = Number(form.long_running_delay_seconds);
      const tm = Number(form.access_token_expire_minutes);
      const mc = Number(form.max_concurrent_executions);
      if (!Number.isFinite(vt) || vt < 10 || vt > 3600) {
        setError('Virtual Timeout Duration must be between 10 and 3600 seconds.');
        setSaving(false);
        return;
      }
      if (!Number.isFinite(lr) || lr < 60 || lr > 86400) {
        setError('Long Running Delay must be between 60 and 86400 seconds.');
        setSaving(false);
        return;
      }
      if (!Number.isFinite(tm) || tm < 5 || tm > 1440) {
        setError('Token expiry must be between 5 and 1440 minutes.');
        setSaving(false);
        return;
      }
      if (!Number.isFinite(mc) || mc < 1 || mc > 128) {
        setError('Max concurrent executions must be between 1 and 128.');
        setSaving(false);
        return;
      }
      setError('');
      await axios.put('/api/settings/', form);
      alert('Settings saved');
    } catch (e) {
      console.error(e);
      alert('Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="main-content"><div className="container-fluid"><div className="alert alert-warning border-0" role="alert" style={{backgroundColor: 'rgba(245, 158, 11, 0.1)'}}><i className="bi bi-exclamation-triangle me-2"></i>Admins only</div></div></div>
    );
  }

  if (loading) {
    return (
      <div className="main-content"><div className="container-fluid"><div className="text-center"><div className="spinner-border text-primary" role="status"><span className="visually-hidden">Loading...</span></div></div></div></div>
    );
  }

  return (
    <div className="main-content">
      <div className="container-fluid settings-text-dark">
        <div className="d-flex justify-content-between align-items-center mb-3">
          <h1><i className="bi bi-gear me-3"></i>Settings</h1>
        </div>
        {error && (
          <div className="alert alert-danger border-0" role="alert" style={{backgroundColor: 'rgba(239, 68, 68, 0.1)'}}>
            <i className="bi bi-exclamation-circle me-2"></i>{error}
          </div>
        )}
        <div className="card shadow-lg">
          <div className="card-body">
            <form onSubmit={onSave}>
              <h5 className="mb-3">SMTP</h5>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">SMTP Host</label>
                  <input className="form-control" value={form.smtp_host} onChange={(e)=> setForm({...form, smtp_host: e.target.value})} />
                </div>
                <div className="col-md-3">
                  <label className="form-label">SMTP Port</label>
                  <input type="number" className="form-control" value={form.smtp_port} onChange={(e)=> setForm({...form, smtp_port: Number(e.target.value)})} />
                </div>
                <div className="col-md-6">
                  <label className="form-label">SMTP User</label>
                  <input className="form-control" value={form.smtp_user} onChange={(e)=> setForm({...form, smtp_user: e.target.value})} />
                </div>
                <div className="col-md-6">
                  <label className="form-label">SMTP Password</label>
                  <input type="password" className="form-control" value={form.smtp_pass} onChange={(e)=> setForm({...form, smtp_pass: e.target.value})} />
                </div>
                <div className="col-md-6">
                  <label className="form-label">From Email</label>
                  <input className="form-control" value={form.from_email} onChange={(e)=> setForm({...form, from_email: e.target.value})} />
                </div>
                <div className="col-md-12">
                  <label className="form-label">Digest Recipients (comma-separated)</label>
                  <input className="form-control" placeholder="admin@example.com,ops@example.com" value={form.digest_to_emails} onChange={(e)=> setForm({...form, digest_to_emails: e.target.value})} />
                </div>
                <div className="col-md-12">
                  <div className="form-check mt-2">
                    <input className="form-check-input" type="checkbox" id="digestOnlyFailed" checked={form.digest_only_failed} onChange={(e)=> setForm({...form, digest_only_failed: e.target.checked})} />
                    <label className="form-check-label" htmlFor="digestOnlyFailed">
                      Send only failed executions in daily digest
                    </label>
                  </div>
                </div>
              </div>
              
              <hr className="my-4" />
              
              <h5 className="mb-3">SSH Key Configuration</h5>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">Default SSH Key Type</label>
                  <select 
                    className="form-select" 
                    value={form.ssh_key_type} 
                    onChange={(e) => setForm({...form, ssh_key_type: e.target.value})}
                  >
                    <option value="rsa">RSA (4096-bit) - Most Compatible</option>
                    <option value="ed25519">Ed25519 (256-bit) - Recommended</option>
                    <option value="ecdsa">ECDSA (256-bit) - Modern Alternative</option>
                  </select>
                  <div className="form-text">
                    This setting determines the SSH key type used when creating new servers or generating new keys.
                  </div>
                </div>
              </div>
              
              <hr className="my-4" />
              
              <h5 className="mb-3">Script Execution</h5>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">Virtual Timeout Duration (seconds)</label>
                  <input 
                    type="number" 
                    className="form-control" 
                    value={form.virtual_timeout_duration} 
                    onChange={(e) => setForm({...form, virtual_timeout_duration: Number(e.target.value)})}
                    min="10"
                    max="3600"
                    required 
                  />
                  <div className="form-text">
                    For infinite scripts, capture output after this duration and show in executions. The script continues running in the background.
                  </div>
                </div>
                <div className="col-md-6">
                  <label className="form-label">Long Running Delay (seconds)</label>
                  <input 
                    type="number" 
                    className="form-control" 
                    value={form.long_running_delay_seconds}
                    onChange={(e) => setForm({...form, long_running_delay_seconds: Number(e.target.value)})}
                    min="60"
                    max="86400"
                    required 
                  />
                  <div className="form-text">
                    After this delay, executions that are still running will be marked as long_running.
                  </div>
                </div>
                <div className="col-md-6">
                  <label className="form-label">Schedule Trigger Tolerance (seconds)</label>
                  <input 
                    type="number" 
                    className="form-control" 
                    value={form.schedule_trigger_tolerance_seconds}
                    onChange={(e) => setForm({...form, schedule_trigger_tolerance_seconds: Number(e.target.value)})}
                    min="0"
                    max="300"
                    required 
                  />
                  <div className="form-text">
                    Window to consider a schedule on-time even if the exact second is missed.
                  </div>
                </div>
                <div className="col-md-6">
                  <label className="form-label">Max Concurrent Executions</label>
                  <input 
                    type="number" 
                    className="form-control" 
                    value={form.max_concurrent_executions}
                    onChange={(e) => setForm({...form, max_concurrent_executions: Number(e.target.value)})}
                    min="1"
                    max="128"
                    required 
                  />
                  <div className="form-text">
                    Upper bound on parallel script executions (worker-level semaphore). Default 8.
                  </div>
                </div>
              </div>

              <hr className="my-4" />

              <h5 className="mb-3">Authentication</h5>
              <div className="row g-3">
                <div className="col-md-6">
                  <label className="form-label">Token Expiry (minutes)</label>
                  <input 
                    type="number" 
                    className="form-control" 
                    value={form.access_token_expire_minutes}
                    onChange={(e) => setForm({...form, access_token_expire_minutes: Number(e.target.value)})}
                    min="5"
                    max="1440"
                    required 
                  />
                  <div className="form-text">
                    JWT access token lifetime for user sessions. Default 30 minutes.
                  </div>
                </div>
              </div>
              
              <div className="mt-4 d-flex justify-content-end">
                <button type="submit" className="btn btn-primary" disabled={saving}>
                  {saving ? 'Saving...' : 'Save Settings'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;


