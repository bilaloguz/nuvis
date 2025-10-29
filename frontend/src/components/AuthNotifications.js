import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './AuthNotifications.css';

const AuthNotifications = () => {
  const [notifications, setNotifications] = useState([]);
  const [isVisible, setIsVisible] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const fetchNotifications = async () => {
    try {
      setIsLoading(true);
      const response = await axios.get('/api/notifications/auth-notifications?limit=50');
      setNotifications(response.data.notifications || []);
    } catch (error) {
      console.error('Failed to fetch auth notifications:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const clearNotifications = async () => {
    try {
      await axios.delete('/api/notifications/auth-notifications');
      setNotifications([]);
    } catch (error) {
      console.error('Failed to clear notifications:', error);
    }
  };

  useEffect(() => {
    fetchNotifications();
    // Refresh every 5 seconds
    const interval = setInterval(fetchNotifications, 5000);
    return () => clearInterval(interval);
  }, []);

  const getNotificationIcon = (type, success) => {
    if (type === 'ssh_deployment') {
      return success ? '🔑' : '❌';
    } else if (type === 'script_execution_auth') {
      return success ? '🚀' : '❌';
    } else if (type === 'auth_attempt') {
      return success ? '✅' : '❌';
    }
    return 'ℹ️';
  };

  const getNotificationClass = (success) => {
    return success ? 'notification-success' : 'notification-error';
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  const toggleVisibility = () => {
    setIsVisible(!isVisible);
  };

  return (
    <div className="auth-notifications-container">
      <button 
        className="auth-notifications-toggle"
        onClick={toggleVisibility}
        title="Authentication Notifications"
      >
        🔐 Auth Logs ({notifications.length})
      </button>
      
      {isVisible && (
        <div className="auth-notifications-panel">
          <div className="auth-notifications-header">
            <h4>Authentication Events</h4>
            <div className="auth-notifications-actions">
              <button 
                className="btn btn-sm btn-outline-secondary"
                onClick={fetchNotifications}
                disabled={isLoading}
              >
                {isLoading ? '⏳' : '🔄'} Refresh
              </button>
              <button 
                className="btn btn-sm btn-outline-danger"
                onClick={clearNotifications}
                disabled={notifications.length === 0}
              >
                🗑️ Clear
              </button>
              <button 
                className="btn btn-sm btn-outline-secondary"
                onClick={toggleVisibility}
              >
                ✕ Close
              </button>
            </div>
          </div>
          
          <div className="auth-notifications-content">
            {notifications.length === 0 ? (
              <div className="no-notifications">
                <p>No authentication events yet</p>
              </div>
            ) : (
              <div className="notifications-list">
                {notifications.map((notification) => (
                  <div 
                    key={notification.id} 
                    className={`notification-item ${getNotificationClass(notification.success)}`}
                  >
                    <div className="notification-icon">
                      {getNotificationIcon(notification.type, notification.success)}
                    </div>
                    <div className="notification-content">
                      <div className="notification-message">
                        {notification.message}
                      </div>
                      <div className="notification-details">
                        <span className="notification-timestamp">
                          {formatTimestamp(notification.timestamp)}
                        </span>
                        {notification.details && Object.keys(notification.details).length > 0 && (
                          <details className="notification-details-expand">
                            <summary>Details</summary>
                            <pre>{JSON.stringify(notification.details, null, 2)}</pre>
                          </details>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AuthNotifications;
