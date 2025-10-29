import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useTheme } from '../contexts/ThemeContext';

const Navbar = () => {
  const { user, logout, isAuthenticated } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => {
    return location.pathname === path;
  };

  if (!isAuthenticated) {
    return null;
  }

  return (
    <nav className="navbar navbar-expand-lg">
      <div className="container-fluid px-3">
        <Link to="/" className="navbar-brand d-flex align-items-center">
          <img src="/favicon.svg?v=3" alt="biRun" height="32" className="me-2" />
          biRun
        </Link>
        
        <button 
          className="navbar-toggler" 
          type="button" 
          data-bs-toggle="collapse" 
          data-bs-target="#navbarNav"
        >
          <span className="navbar-toggler-icon"></span>
        </button>
        
        <div className="collapse navbar-collapse" id="navbarNav">
          <ul className="navbar-nav mx-auto gap-2 justify-content-center">
            {/* Group 1: Dashboard */}
            <li className="nav-item">
              <Link className={`nav-link ${isActive('/dashboard') ? 'active' : ''}`} to="/dashboard"><i className="bi bi-speedometer2 me-1"></i>Dashboard</Link>
            </li>
            {user?.role === 'admin' && (
              <>
                <li className="nav-item text-muted align-self-center">|</li>
                {/* Group 2: Servers Groups */}
                <li className="nav-item"><Link className={`nav-link ${isActive('/servers') ? 'active' : ''}`} to="/servers"><i className="bi bi-server me-1"></i>Servers</Link></li>
                <li className="nav-item"><Link className={`nav-link ${isActive('/server-groups') ? 'active' : ''}`} to="/server-groups"><i className="bi bi-collection me-1"></i>Groups</Link></li>
                <li className="nav-item text-muted align-self-center">|</li>
                {/* Group 3: Scripts Marketplace */}
                <li className="nav-item"><Link className={`nav-link ${isActive('/scripts') ? 'active' : ''}`} to="/scripts"><i className="bi bi-code-square me-1"></i>Scripts</Link></li>
                <li className="nav-item"><Link className={`nav-link ${isActive('/marketplace') ? 'active' : ''}`} to="/marketplace"><i className="bi bi-shop me-1"></i>Marketplace</Link></li>
                <li className="nav-item text-muted align-self-center">|</li>
                {/* Group 4: Schedules Workflows */}
                <li className="nav-item"><Link className={`nav-link ${isActive('/schedules') ? 'active' : ''}`} to="/schedules"><i className="bi bi-alarm me-1"></i>Schedules</Link></li>
                <li className="nav-item"><Link className={`nav-link ${isActive('/workflows') ? 'active' : ''}`} to="/workflows"><i className="bi bi-diagram-3 me-1"></i>Workflows</Link></li>
                <li className="nav-item text-muted align-self-center">|</li>
                             {/* Group 5: Executions Audit */}
             <li className="nav-item"><Link className={`nav-link ${isActive('/executions') ? 'active' : ''}`} to="/executions"><i className="bi bi-clock-history me-1"></i>Executions</Link></li>
             <li className="nav-item"><Link className={`nav-link ${isActive('/audit') ? 'active' : ''}`} to="/audit"><i className="bi bi-shield-check me-1"></i>Audit</Link></li>
                <li className="nav-item text-muted align-self-center">|</li>
                {/* Group 6: Settings Users */}
                <li className="nav-item"><Link className={`nav-link ${isActive('/settings') ? 'active' : ''}`} to="/settings"><i className="bi bi-gear me-1"></i>Settings</Link></li>
                <li className="nav-item"><Link className={`nav-link ${isActive('/users') ? 'active' : ''}`} to="/users"><i className="bi bi-people me-1"></i>Users</Link></li>
              </>
            )}
          </ul>
          
          <ul className="navbar-nav gap-2">
            <li className="nav-item">
              <button 
                className="btn btn-link nav-link border-0" 
                onClick={toggleTheme}
                title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
                style={{ fontSize: '1.2rem' }}
              >
                <i className={`bi ${theme === 'dark' ? 'bi-sun' : 'bi-moon'}`}></i>
              </button>
            </li>
            <li className="nav-item dropdown">
              <a 
                className="nav-link dropdown-toggle" 
                href="#" 
                role="button" 
                data-bs-toggle="dropdown"
              >
                <i className="bi bi-person-circle me-1"></i>
                {user?.username}
              </a>
              <ul className="dropdown-menu dropdown-menu-end">
                <li>
                  <Link className="dropdown-item" to="/profile">
                    <i className="bi bi-person me-2"></i>
                    Profile
                  </Link>
                </li>
                <li>
                  <button className="dropdown-item" onClick={handleLogout}>
                    <i className="bi bi-box-arrow-right me-2"></i>
                    Logout
                  </button>
                </li>
              </ul>
            </li>
          </ul>
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
