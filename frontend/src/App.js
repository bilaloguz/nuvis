import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { ThemeProvider } from './contexts/ThemeContext';
import Login from './components/Login';
import Register from './components/Register';
import Dashboard from './components/Dashboard';
import Navbar from './components/Navbar';
import UserManagement from './components/UserManagement';
import UserProfile from './components/UserProfile';
import ServerManagement from './components/ServerManagement';
import ServerGroupManagement from './components/ServerGroupManagement';
import ScriptManagement from './components/ScriptManagement';
import Executions from './components/Executions';
import Schedules from './components/Schedules';
import Settings from './components/Settings';
import AuditLogs from './components/AuditLogs';
import Marketplace from './components/Marketplace';
import Workflows from './components/Workflows';
import WorkflowDetail from './components/WorkflowDetail';
import WorkflowBuilder from './components/WorkflowBuilder';
import WorkflowMonitor from './components/WorkflowMonitor';
import 'bootstrap/dist/css/bootstrap.min.css';
import './styles/themes.css';

// Protected Route Component
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading } = useAuth();
  
  if (loading) {
    return <div>Loading...</div>;
  }
  
  return isAuthenticated ? children : <Navigate to="/login" />;
};

// Admin Route Component
const AdminRoute = ({ children }) => {
  const { isAuthenticated, loading, user } = useAuth();
  
  if (loading) {
    return <div>Loading...</div>;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  
  if (user?.role !== 'admin') {
    return <Navigate to="/dashboard" />;
  }
  
  return children;
};

function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <Router>
        <div className="App">
          <Navbar />
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/dashboard" element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            } />
            <Route path="/users" element={
              <AdminRoute>
                <UserManagement />
              </AdminRoute>
            } />
            <Route path="/servers" element={
              <AdminRoute>
                <ServerManagement />
              </AdminRoute>
            } />
            <Route path="/server-groups" element={
              <AdminRoute>
                <ServerGroupManagement />
              </AdminRoute>
            } />
            <Route path="/scripts" element={
              <AdminRoute>
                <ScriptManagement />
              </AdminRoute>
            } />
            <Route path="/executions" element={
              <AdminRoute>
                <Executions />
              </AdminRoute>
            } />
            <Route path="/schedules" element={
              <AdminRoute>
                <Schedules />
              </AdminRoute>
            } />
            <Route path="/settings" element={
              <AdminRoute>
                <Settings />
              </AdminRoute>
            } />
            <Route path="/audit" element={
              <AdminRoute>
                <AuditLogs />
              </AdminRoute>
            } />
            <Route path="/marketplace" element={
              <ProtectedRoute>
                <Marketplace />
              </ProtectedRoute>
            } />
            <Route path="/workflows" element={
              <AdminRoute>
                <Workflows />
              </AdminRoute>
            } />
            <Route path="/workflows/:id" element={
              <AdminRoute>
                <WorkflowDetail />
              </AdminRoute>
            } />
            <Route path="/workflows/:id/builder" element={
              <AdminRoute>
                <WorkflowBuilder />
              </AdminRoute>
            } />
            <Route path="/workflow-run/:workflowRunId/monitor" element={
              <AdminRoute>
                <WorkflowMonitor />
              </AdminRoute>
            } />
            <Route path="/profile" element={
              <ProtectedRoute>
                <UserProfile />
              </ProtectedRoute>
            } />
            <Route path="/" element={<Navigate to="/dashboard" />} />
          </Routes>
        </div>
      </Router>
    </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
