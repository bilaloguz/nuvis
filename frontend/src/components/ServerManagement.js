import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';
import axios from 'axios';
import './ServerManagement.css';

const ServerManagement = () => {
  const { user: currentUser } = useAuth();
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [editingServer, setEditingServer] = useState(null);
  const [createForm, setCreateForm] = useState({
    name: '',
    ip: '',
    username: '',
    password: '',
    group_ids: []  // Changed from group_id to group_ids array
  });

  const [editForm, setEditForm] = useState({
    name: '',
    ip: '',
    username: '',
    auth_method: 'password',
    group_ids: [],  // Changed from group_id to group_ids array
    password: ''
  });
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [serverToDelete, setServerToDelete] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showSshKeyModal, setShowSshKeyModal] = useState(false);
  const [sshKeyForm, setSshKeyForm] = useState({
    key_name: '',
    passphrase: ''
  });
  const [generatedSshKey, setGeneratedSshKey] = useState(null);
  const [sshKeys, setSshKeys] = useState([]);
  const [serverGroups, setServerGroups] = useState([]);
  const [deployServerId, setDeployServerId] = useState(null);
  const [deploying, setDeploying] = useState(false);
  const [testingConnections, setTestingConnections] = useState({});
  const [connectionStatus, setConnectionStatus] = useState({});
  const [terminalModal, setTerminalModal] = useState(false);
  const [currentTerminalServer, setCurrentTerminalServer] = useState(null);
  const [terminalConnected, setTerminalConnected] = useState(false);
  const [websocket, setWebsocket] = useState(null);
  const [terminalOutput, setTerminalOutput] = useState([]);
  const [terminalInput, setTerminalInput] = useState('');
  const [connectionHealth, setConnectionHealth] = useState('disconnected');
  const [connectingTerminal, setConnectingTerminal] = useState(false);
  const [serverHealth, setServerHealth] = useState({});
  const [disconnectingTerminal, setDisconnectingTerminal] = useState(false);
  const [commandHistory, setCommandHistory] = useState([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  // Create progress modal & logs
  const [showCreateProgressModal, setShowCreateProgressModal] = useState(false);
  const [createLogs, setCreateLogs] = useState([]);
  const [createProgressStatus, setCreateProgressStatus] = useState('idle');

  const appendCreateLog = (message) => {
    setCreateLogs((prev) => [...prev, `${new Date().toLocaleTimeString()} • ${message}`]);
  };
  
  // Terminal modal drag functionality
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [modalPosition, setModalPosition] = useState({ x: 0, y: 0 });

  // OS Display Name mapping
  const getOsDisplayName = (osType) => {
    const names = {
      'linux': 'Linux',
      'windows': 'Windows',
      'macos': 'macOS',
      'freebsd': 'FreeBSD',
      'unix_like': 'Unix',
      'unknown': 'Unknown'
    };
    return names[osType] || 'Unknown';
  };

  useEffect(() => {
    if (currentUser?.role === 'admin') {
      fetchServers();
      fetchSshKeys();
      fetchServerGroups();
      fetchServerHealth();
    }
  }, [currentUser]);



  // Connection health check
  useEffect(() => {
    if (websocket) {
      const healthInterval = setInterval(checkConnectionHealth, 1000);
      return () => clearInterval(healthInterval);
    }
  }, [websocket]);

  const fetchServers = async () => {
    try {
      setLoading(true);
      const response = await axios.get('/api/servers/');
      setServers(response.data.servers);
    } catch (error) {
      setError('Failed to fetch servers');
      console.error('Error fetching servers:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchSshKeys = async () => {
    try {
      const response = await axios.get('/api/servers/ssh-keys');
      setSshKeys(response.data.keys);
    } catch (error) {
      console.error('Error fetching SSH keys:', error);
    }
  };

  const fetchServerGroups = async () => {
    try {
      const response = await axios.get('/api/server-groups/');
      setServerGroups(response.data.groups);
    } catch (error) {
      console.error('Error fetching server groups:', error);
    }
  };

  const fetchServerHealth = async () => {
    try {
      const response = await axios.get('/api/health/summary');
      const healthMap = {};
      response.data.forEach(health => {
        healthMap[health.server_id] = health;
      });
      setServerHealth(healthMap);
    } catch (error) {
      console.error('Error fetching server health:', error);
    }
  };

  const checkServerHealth = async (serverId) => {
    try {
      await axios.post(`/api/servers/${serverId}/health/check`);
      // Refresh health data
      await fetchServerHealth();
    } catch (error) {
      console.error('Error checking server health:', error);
      alert('Failed to check server health');
    }
  };

  const generateSshKey = async (e) => {
    e.preventDefault();
    
    if (!sshKeyForm.key_name.trim()) {
      alert('Please enter a key name');
      return;
    }
    
    // Check if user is admin
    if (!currentUser || currentUser.role !== 'admin') {
      alert('You need admin privileges to generate SSH keys');
      return;
    }
    
    try {
      console.log('Generating SSH key with name:', sshKeyForm.key_name.trim());
      console.log('Current user:', currentUser);
      
      const response = await axios.post('/api/servers/generate-ssh-key', null, {
        params: { key_name: sshKeyForm.key_name.trim() }
      });
      
      console.log('SSH key generated successfully:', response.data);
      setGeneratedSshKey(response.data);
      setSshKeyForm({ key_name: '', passphrase: '' });
      
      // Refresh SSH keys list
      await fetchSshKeys();
      
    } catch (error) {
      console.error('Error generating SSH key:', error);
      console.error('Error response:', error.response);
      
      if (error.response?.status === 403) {
        alert('Access denied: You need admin privileges to generate SSH keys');
      } else if (error.response?.status === 401) {
        alert('Authentication failed: Please log in again');
      } else {
        alert(`Failed to generate SSH key: ${error.response?.data?.detail || error.message}`);
      }
    }
  };

  const handleEdit = (server) => {
    setEditingServer(server);
    setEditForm({
      name: server.name,
      ip: server.ip,
      username: server.username,
      auth_method: server.auth_method,
      group_ids: server.groups ? server.groups.map(g => g.id) : [], // Extract group IDs from groups array
      password: ''
    });
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.put(`/api/servers/${editingServer.id}`, editForm);
      const updatedServer = response.data;
      
      // Update the servers list
      setServers(servers.map(s => s.id === editingServer.id ? updatedServer : s));
      
      // If SSH key authentication was added, automatically deploy the key
      if (editForm.auth_method === 'ssh_key' && editForm.ssh_key_path && 
          editingServer.auth_method !== 'ssh_key') {
        try {
          // Extract key name from the SSH key path
          const keyName = editForm.ssh_key_path.split('/').pop().replace('_id_rsa', '');
          
          console.log(`🚀 Auto-deploying SSH key '${keyName}' to updated server '${updatedServer.name}'...`);
          alert(`🚀 Auto-deploying SSH key '${keyName}' to updated server '${updatedServer.name}'...\n\nPlease wait while the key is being deployed.`);
          
          // Deploy the SSH key to the updated server
          const deployResponse = await axios.post('/api/servers/deploy-ssh-key', {
            key_name: keyName,
            server_id: updatedServer.id
          });
          
          if (deployResponse.data.status === 'deployed') {
            console.log(`✅ SSH key '${keyName}' automatically deployed to server '${updatedServer.name}'`);
            // Update the server's connection status to show successful deployment
            setConnectionStatus(prev => ({
              ...prev,
              [updatedServer.id]: {
                success: true,
                message: `✅ SSH key deployed successfully`,
                timestamp: new Date().toLocaleTimeString(),
                details: `Key '${keyName}' was automatically deployed`
              }
            }));
            // Show success message to user
            alert(`✅ Server '${updatedServer.name}' updated successfully!\n\n🚀 SSH key '${keyName}' was automatically deployed to the server.`);
          } else if (deployResponse.data.status === 'already_exists') {
            console.log(`ℹ️ SSH key '${keyName}' already exists on server '${updatedServer.name}'`);
            setConnectionStatus(prev => ({
              ...prev,
              [updatedServer.id]: {
                success: true,
                message: `ℹ️ Key already deployed`,
                timestamp: new Date().toLocaleTimeString(),
                details: `Key '${keyName}' was already present on the server`
              }
            }));
            // Show info message to user
            alert(`✅ Server '${updatedServer.name}' updated successfully!\n\nℹ️ SSH key '${keyName}' was already present on the server.`);
          }
        } catch (deployError) {
          console.error('Auto-deployment failed:', deployError);
          // Don't fail the server update, just log the deployment error
          setConnectionStatus(prev => ({
            ...prev,
            [updatedServer.id]: {
              success: false,
              message: `⚠️ Auto-deployment failed`,
              timestamp: new Date().toLocaleTimeString(),
              details: `Failed to deploy SSH key: ${deployError.response?.data?.detail || deployError.message}`
            }
          }));
        }
      }
      
      // Reset form
      setEditingServer(null);
      setEditForm({});
      
    } catch (error) {
      alert(error.response?.data?.detail || 'Failed to update server');
    }
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    // Start progress modal
    setShowCreateProgressModal(true);
    setCreateLogs([]);
    setCreateProgressStatus('running');
    appendCreateLog('Starting server creation...');

    // Validate password (always required for new servers)
    if (!createForm.password || createForm.password.length < 6) {
      appendCreateLog('❌ Password must be at least 6 characters long');
      setCreateProgressStatus('error');
      return; 
    }
    
    try {
      // Create the server first (always with password auth initially)
      const serverData = {
        ...createForm,
        auth_method: 'password' // Always start with password auth
      };
      appendCreateLog('Calling API: POST /api/servers ...');
      const response = await axios.post('/api/servers/', serverData);
      const newServer = response.data;
      setServers([...servers, newServer]);
      appendCreateLog(`✅ Server created: ${newServer.name} (${newServer.ip})`);
      
      // Always deploy SSH key for future use
      if (createForm.password) {
        try {
          // Find the first available SSH key to deploy
          if (sshKeys.length > 0) {
            const keyToDeploy = sshKeys[0]; // Use the first available key
            const keyName = keyToDeploy.name;
            
            appendCreateLog(`Deploying SSH key '${keyName}' to '${newServer.name}'...`);
            
            // Deploy the SSH key to the newly created server
            const deployResponse = await axios.post('/api/servers/deploy-ssh-key', {
              key_name: keyName,
              server_id: newServer.id
            });
            
            if (deployResponse.data.status === 'deployed') {
              appendCreateLog(`✅ SSH key deployed to '${newServer.name}'`);
              // Update the server's connection status to show successful deployment
              setConnectionStatus(prev => ({
                ...prev,
                [newServer.id]: {
                  success: true,
                  message: `✅ SSH key deployed successfully`,
                  timestamp: new Date().toLocaleTimeString(),
                  details: `Key '${keyName}' was automatically deployed`
                }
              }));
              // Optional: inline status updated in UI; no alert
            } else if (deployResponse.data.status === 'already_exists') {
              appendCreateLog(`ℹ️ SSH key already existed on '${newServer.name}'`);
              setConnectionStatus(prev => ({
                ...prev,
                [newServer.id]: {
                  success: true,
                  message: `ℹ️ Key already deployed`,
                  timestamp: new Date().toLocaleTimeString(),
                  details: `Key '${keyName}' was already present on the server`
                }
              }));
              // Optional: inline status updated in UI; no alert
            }
          }
        } catch (deployError) {
          console.error('Auto-deployment failed:', deployError);
          appendCreateLog(`⚠️ SSH key deployment failed: ${deployError.response?.data?.detail || deployError.message}`);
          // Don't fail the server creation, just log the deployment error
          setConnectionStatus(prev => ({
            ...prev,
            [newServer.id]: {
              success: false,
              message: `⚠️ Auto-deployment failed`,
              timestamp: new Date().toLocaleTimeString(),
              details: `Failed to deploy SSH key: ${deployError.response?.data?.detail || deployError.message}`
            }
          }));
        }
      }
      
      // 🚀 AUTOMATIC CONNECTION TEST AFTER SERVER CREATION
      appendCreateLog(`Testing connection to '${newServer.name}'...`);
      
      try {
        // Set loading state for the new server
        setTestingConnections(prev => ({ ...prev, [newServer.id]: true }));
        
        // Wait a moment for SSH key deployment to complete (if applicable)
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Test the connection
        const testResponse = await axios.post(`/api/servers/${newServer.id}/test-connection`);
        
        if (testResponse.data.success) {
          const status = {
            success: true,
            message: `✅ Auto-test: Connected in ${testResponse.data.response_time}ms`,
            timestamp: new Date().toLocaleTimeString(),
            details: `Server created and connection verified automatically`
          };
          setConnectionStatus(prev => ({ ...prev, [newServer.id]: status }));
          appendCreateLog(`✅ Connection verified in ${testResponse.data.response_time}ms`);
        } else {
          const status = {
            success: false,
            message: `⚠️ Auto-test: ${testResponse.data.message}`,
            timestamp: new Date().toLocaleTimeString(),
            details: 'Connection test completed with warnings after server creation'
          };
          setConnectionStatus(prev => ({ ...prev, [newServer.id]: status }));
          appendCreateLog(`⚠️ Connection test warning: ${testResponse.data.message}`);
        }
      } catch (testError) {
        console.error('Auto-connection test failed:', testError);
        
        const errorMessage = (() => {
          if (testError.response?.status === 401) return 'Authentication failed: Invalid credentials or SSH key';
          else if (testError.response?.status === 403) return 'Access denied: Server rejected the connection';
          else if (testError.response?.status === 404) return 'Server not found: Check if the server is running';
          else if (testError.response?.status === 500) return `Server error: ${testError.response?.data?.detail || 'Unknown server error'}`;
          else if (testError.code === 'ECONNREFUSED') return 'Connection refused: Server is not accessible or SSH service is down';
          else if (testError.code === 'ETIMEDOUT') return 'Connection timeout: Server took too long to respond';
          else return `Connection failed: ${testError.response?.data?.detail || testError.message}`;
        })();
        
        const status = {
          success: false,
          message: `❌ Auto-test: ${errorMessage}`,
          timestamp: new Date().toLocaleTimeString(),
          details: 'Auto-connection test failed after server creation'
        };
        setConnectionStatus(prev => ({ ...prev, [newServer.id]: status }));
        appendCreateLog(`❌ Connection test failed: ${errorMessage}`);
      } finally {
        // Clear loading state
        setTestingConnections(prev => ({ ...prev, [newServer.id]: false }));
      }
      
      appendCreateLog('🎉 Server setup flow completed');
      setCreateProgressStatus('success');
      // Auto-close progress modal shortly after success
      setTimeout(() => setShowCreateProgressModal(false), 1200);

      setShowCreateModal(false);
      setCreateForm({
        name: '',
        ip: '',
        username: '',
        password: '',
        group_ids: []
      });
    } catch (error) {
      appendCreateLog(`❌ Failed to create server: ${error.response?.data?.detail || error.message}`);
      setCreateProgressStatus('error');
    }
  };

  const handleDelete = (server) => {
    setServerToDelete(server);
    setShowDeleteModal(true);
  };

  const confirmDelete = async () => {
    try {
      await axios.delete(`/api/servers/${serverToDelete.id}`);
      
      // Remove server from list
      setServers(servers.filter(s => s.id !== serverToDelete.id));
      
      // Notify success
      if (window?.toast?.success) {
        window.toast.success(`Server "${serverToDelete.name}" deleted`);
      }

      // Refresh list to stay in sync
      fetchServers();

      // Close modal
      setShowDeleteModal(false);
      setServerToDelete(null);
      
    } catch (error) {
      const msg = error.response?.data?.detail || 'Failed to delete server';
      if (window?.toast?.error) {
        window.toast.error(msg);
      } else {
        alert(msg);
      }
    }
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString();
  };

  const handleAuthMethodChange = (method, isCreate = true) => {
    // Only handle edit form changes now, create form is always password-based
    if (!isCreate) {
      setEditForm({
        ...editForm,
        auth_method: method,
        password: '',
        ssh_key_path: '',
        ssh_key_passphrase: ''
      });
    }
  };

  const handleDeployKey = async () => {
    if (!deployServerId) {
      alert('Please select a server to deploy to.');
      return;
    }

    try {
      setDeploying(true);
      const response = await axios.post('/api/servers/deploy-ssh-key', {
        key_name: generatedSshKey.key_name,
        server_id: deployServerId
      });
      
      if (response.data.status === 'deployed') {
        alert(`✅ Key deployed successfully to ${response.data.server_name}!`);
      } else if (response.data.status === 'already_exists') {
        alert(`ℹ️ Key already exists on ${response.data.server_name}.`);
      }
      
      setDeployServerId(null); // Clear selected server after deployment
    } catch (error) {
      alert(`❌ Failed to deploy key: ${error.response?.data?.detail || error.message}`);
    } finally {
      setDeploying(false);
    }
  };

  const testConnection = async (serverId, silent = false) => {
    if (testingConnections[serverId]) return; // Prevent multiple simultaneous tests
    
    setTestingConnections(prev => ({ ...prev, [serverId]: true }));
    
    try {
      console.log(`Testing connection to server ${serverId}...`);
      
      const response = await axios.post(`/api/servers/${serverId}/test-connection`);
      
      if (response.data.success) {
        const status = {
          success: true,
          message: `✅ Connected in ${response.data.response_time}ms`,
          timestamp: new Date().toLocaleTimeString(),
          details: response.data.server_info
        };
        setConnectionStatus(prev => ({ ...prev, [serverId]: status }));

      } else {
        const status = {
          success: false,
          message: `⚠️ ${response.data.message}`,
          timestamp: new Date().toLocaleTimeString(),
          details: 'Connection test completed with warnings'
        };
        setConnectionStatus(prev => ({ ...prev, [serverId]: status }));
        if (!silent) alert(`⚠️ Connection test completed with warnings:\n\n${response.data.message}`);
      }
      
    } catch (error) {
      console.error('Connection test failed:', error);
      
      const errorMessage = (() => {
        if (error.response?.status === 401) return 'Authentication failed: Invalid credentials or SSH key';
        else if (error.response?.status === 403) return 'Access denied: Server rejected the connection';
        else if (error.response?.status === 404) return 'Server not found: Check if the server is running';
        else if (error.response?.status === 500) return `Server error: ${error.response?.data?.detail || 'Unknown server error'}`;
        else if (error.code === 'ECONNREFUSED') return 'Connection refused: Server is not accessible or SSH service is down';
        else if (error.code === 'ETIMEDOUT') return 'Connection timeout: Server took too long to respond';
        else return `Connection failed: ${error.response?.data?.detail || error.message}`;
      })();
      
      const status = {
        success: false,
        message: `❌ ${errorMessage}`,
        timestamp: new Date().toLocaleTimeString(),
        details: 'Connection test failed'
      };
      setConnectionStatus(prev => ({ ...prev, [serverId]: status }));
      
      if (!silent) alert(`❌ ${errorMessage}`);
    } finally {
      setTestingConnections(prev => ({ ...prev, [serverId]: false }));
    }
  };

  // Auto-refresh connection badges silently
  useEffect(() => {
    if (!servers || servers.length === 0) return;
    let isCancelled = false;

    const runCycle = async () => {
      // Stagger requests to avoid bursts
      for (let i = 0; i < servers.length; i++) {
        if (isCancelled) return;
        const s = servers[i];
        // Skip if a manual test is already running
        if (!testingConnections[s.id]) {
          // Fire and forget, silent
          testConnection(s.id, true);
        }
        await new Promise(r => setTimeout(r, 400));
      }
    };

    // Initial cycle shortly after load
    const initialTimer = setTimeout(runCycle, 1500);
    // Repeat every 60s
    const interval = setInterval(runCycle, 60000);

    return () => {
      isCancelled = true;
      clearTimeout(initialTimer);
      clearInterval(interval);
    };
  }, [servers]);

  const openTerminal = (server) => {
    console.log('=== OPEN TERMINAL CALLED ===');
    console.log('Server object:', server);
    console.log('Setting terminal modal to true');
    setCurrentTerminalServer(server);
    setTerminalModal(true);
    setTerminalConnected(false);
    setTerminalOutput([]);
    setTerminalInput('');
    setConnectingTerminal(true); // Set connecting state immediately
    setDisconnectingTerminal(false); // Reset disconnecting state
    
    // Reset modal position to center of screen
    setModalPosition({
      x: Math.max(0, (window.innerWidth - 800) / 2),
      y: Math.max(0, (window.innerHeight - 600) / 2)
    });
    
    console.log('Terminal modal should now be open');
    
    // Automatically start connection after a short delay to let modal render
    setTimeout(() => {
      console.log('Auto-starting terminal connection...');
      handleTerminalConnect(server); // Pass server directly instead of relying on state
    }, 200); // Increased delay to ensure modal is fully rendered
  };



  const clearTerminal = () => {
    setTerminalOutput([]);
    setTerminalInput('');
    setCommandHistory([]);
    setHistoryIndex(-1);
  };

  const disconnectTerminal = () => {
    console.log('🔌 Disconnect button clicked!');
    
    // Set disconnecting state
    setDisconnectingTerminal(true);
    
    // Close WebSocket connection
    if (websocket) {
      console.log('🔌 Closing WebSocket connection...');
      websocket.close();
      setWebsocket(null);
    }
    
    // Reset all terminal states
    setTerminalConnected(false);
    setTerminalOutput(prev => [...prev, '🔌 SSH connection disconnected']);
    setConnectionHealth('disconnected');
    setConnectingTerminal(false);
    
    // Close the modal after a short delay to show the disconnect message
    setTimeout(() => {
      console.log('🔌 Closing terminal modal...');
      setTerminalModal(false);
      setCurrentTerminalServer(null);
      setTerminalOutput([]);
      setTerminalInput('');
      setCommandHistory([]);
      setHistoryIndex(-1);
      setDisconnectingTerminal(false);
    }, 1000); // 1 second delay to show disconnect message
    
    console.log('🔌 Disconnect sequence completed');
  };

  const closeTerminal = () => {
    console.log('❌ Close button clicked!');
    
    // Close WebSocket connection
    if (websocket) {
      console.log('❌ Closing WebSocket connection...');
      websocket.close();
      setWebsocket(null);
    }
    
    // Reset all terminal states and close modal
    setTerminalModal(false);
    setCurrentTerminalServer(null);
    setTerminalConnected(false);
    setTerminalOutput([]);
    setTerminalInput('');
    setCommandHistory([]);
    setHistoryIndex(-1);
    setConnectionHealth('disconnected');
    setConnectingTerminal(false);
    setDisconnectingTerminal(false);
    
    console.log('❌ Terminal modal closed');
  };

  const sendTerminalInput = (input) => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      console.log('Sending terminal input:', input);
      
      // Add command to history
      if (input.trim()) {
        console.log('Adding to command history:', input.trim());
        setCommandHistory(prev => {
          const newHistory = [...prev, input.trim()];
          console.log('New command history:', newHistory);
          return newHistory;
        });
        setHistoryIndex(-1); // Reset history index
      }
      
      websocket.send(JSON.stringify({
        type: 'input',
        data: input
      }));
      setTerminalInput('');
    } else {
      console.error('WebSocket not ready or not open');
    }
  };

  const sendCtrlC = () => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({ type: 'ctrl_c' }));
    }
  };

  const handleTerminalInputKeyPress = (e) => {
    console.log('Key pressed:', e.key, 'History length:', commandHistory.length, 'History index:', historyIndex);
    
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c') {
      e.preventDefault();
      sendCtrlC();
      return;
    }

    if (e.key === 'Enter') {
      sendTerminalInput(terminalInput);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      console.log('ArrowUp pressed, commandHistory:', commandHistory);
      if (commandHistory.length > 0) {
        // Simple logic: go back through history
        const newIndex = historyIndex === -1 ? 0 : Math.min(historyIndex + 1, commandHistory.length - 1);
        const commandToShow = commandHistory[commandHistory.length - 1 - newIndex];
        console.log('Setting history index to:', newIndex, 'Command to show:', commandToShow);
        setHistoryIndex(newIndex);
        setTerminalInput(commandToShow);
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      console.log('ArrowDown pressed, historyIndex:', historyIndex);
      if (historyIndex > 0) {
        // Go forward in history
        const newIndex = historyIndex - 1;
        const commandToShow = commandHistory[commandHistory.length - 1 - newIndex];
        console.log('Setting history index to:', newIndex, 'Command to show:', commandToShow);
        setHistoryIndex(newIndex);
        setTerminalInput(commandToShow);
      } else if (historyIndex === 0) {
        // Reset to empty input
        console.log('Resetting to empty input');
        setHistoryIndex(-1);
        setTerminalInput('');
      }
    }
  };

  const checkConnectionHealth = () => {
    if (websocket) {
      if (websocket.readyState === WebSocket.OPEN) {
        setConnectionHealth('connected');
      } else if (websocket.readyState === WebSocket.CONNECTING) {
        setConnectionHealth('connecting');
      } else if (websocket.readyState === WebSocket.CLOSED) {
        setConnectionHealth('disconnected');
      } else if (websocket.readyState === WebSocket.CLOSING) {
        setConnectionHealth('closing');
      }
    }
  };

  // Terminal modal drag handlers
  const handleMouseDown = (e) => {
    if (e.target.closest('.btn-close')) return; // Don't drag when clicking close button
    
    setIsDragging(true);
    const rect = e.currentTarget.getBoundingClientRect();
    setDragOffset({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top
    });
  };

  const handleMouseMove = (e) => {
    if (!isDragging) return;
    
    const newX = e.clientX - dragOffset.x;
    const newY = e.clientY - dragOffset.y;
    
    // Keep modal within viewport bounds
    const maxX = window.innerWidth - 800; // Approximate modal width
    const maxY = window.innerHeight - 600; // Approximate modal height
    
    setModalPosition({
      x: Math.max(0, Math.min(newX, maxX)),
      y: Math.max(0, Math.min(newY, maxY))
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const centerModal = () => {
    setModalPosition({
      x: Math.max(0, (window.innerWidth - 800) / 2),
      y: Math.max(0, (window.innerHeight - 600) / 2)
    });
  };

  // Add global mouse event listeners for dragging
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDragging, dragOffset]);

  const handleTerminalConnect = async (server = null) => {
    // Use passed server parameter or fall back to state
    const targetServer = server || currentTerminalServer;
    
    if (!targetServer) {
      console.error('No terminal server provided!');
      return;
    }
    
    try {
      console.log('=== STARTING TERMINAL CONNECTION ===');
      console.log('Server:', targetServer);
      console.log('Server ID:', targetServer.id);
      console.log('Current user:', currentUser);
      
      // Clear previous output
      setTerminalOutput([]);
      
      // Create WebSocket connection
      const getApiBaseUrl = () => {
        if (process.env.REACT_APP_API_URL) {
          return process.env.REACT_APP_API_URL;
        }
        const hostname = window.location.hostname;
        if (hostname === 'localhost' || hostname === '127.0.0.1') {
          return 'http://localhost:8000';
        } else {
          return `http://${hostname}:8000`;
        }
      };
      const API_BASE_URL = getApiBaseUrl();
      const wsUrl = `ws://${API_BASE_URL.replace('http://', '')}/api/ws/terminal/${targetServer.id}`;
      console.log('🔌 Connecting to WebSocket URL:', wsUrl);
      
      // Test if WebSocket is supported
      if (!window.WebSocket) {
        console.error('❌ WebSocket not supported in this browser');
        setTerminalOutput(prev => [...prev, '❌ WebSocket not supported in this browser']);
        setConnectingTerminal(false);
        return;
      }
      
      const ws = new WebSocket(wsUrl);
      console.log('🔌 WebSocket object created:', ws);
      
      // Set WebSocket immediately for state management
      setWebsocket(ws);
      
      ws.onmessage = (event) => {
        console.log('📨 WebSocket message received:', event.data);
        const message = JSON.parse(event.data);
        console.log('📨 Parsed message:', message);
        
        switch (message.type) {
          case 'connected':
            console.log('✅ WebSocket connected message received');
            // Don't show duplicate connection message
            break;
          case 'ssh_connected':
            console.log('🚀 SSH connected message received');
            setTerminalConnected(true);
            setTerminalOutput(prev => [...prev, `🚀 ${message.message}`]);
            break;
          case 'output':
            console.log('📤 Terminal output received:', message.data);
            setTerminalOutput(prev => [...prev, message.data]);
            break;
          case 'error':
            console.log('❌ Error message received:', message.message);
            setTerminalOutput(prev => [...prev, `❌ Error: ${message.message}`]);
            break;
          case 'ssh_failed':
            console.log('❌ SSH failed message received:', message.message);
            setTerminalOutput(prev => [...prev, `❌ SSH failed: ${message.message}`]);
            break;
          default:
            console.log('📡 Unknown message type:', message.type);
            setTerminalOutput(prev => [...prev, `📡 ${JSON.stringify(message)}`]);
        }
      };
      
      ws.onerror = (error) => {
        console.error('❌ WebSocket error:', error);
        setConnectingTerminal(false);
        setTerminalOutput(prev => [...prev, `❌ WebSocket error: ${error.message || 'Connection failed'}`]);
        setTerminalConnected(false);
      };
      
      ws.onclose = (event) => {
        console.log('🔌 WebSocket closed:', event.code, event.reason);
        setConnectingTerminal(false);
        setTerminalConnected(false);
        setWebsocket(null);
        setTerminalOutput(prev => [...prev, `🔌 WebSocket connection closed (Code: ${event.code})`]);
      };
      
      // Add connection timeout
      const connectionTimeout = setTimeout(() => {
        console.log('⏰ Connection timeout reached');
        if (ws.readyState === WebSocket.CONNECTING) {
          console.log('⏰ Closing WebSocket due to timeout');
          ws.close();
          setConnectingTerminal(false);
          setTerminalOutput(prev => [...prev, '⏰ Connection timeout - please try again']);
          setTerminalOutput(prev => [...prev, '🔍 Debug: Check if backend is running and terminal endpoint is accessible']);
        }
      }, 10000); // 10 second timeout
      
      // Clear timeout when connection is established
      ws.onopen = () => {
        console.log('✅ WebSocket connected successfully');
        clearTimeout(connectionTimeout);
        setConnectingTerminal(false);
        setTerminalOutput(prev => [...prev, '🔌 WebSocket connected, establishing SSH...']);
      };
      
    } catch (error) {
      console.error('❌ Failed to connect to terminal:', error);
      setConnectingTerminal(false);
      setTerminalOutput(prev => [...prev, `❌ Connection failed: ${error.message}`]);
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
            <p>You need admin privileges to access server management.</p>
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
            <i className="bi bi-server me-3"></i>
            Servers
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
                    <th style={{width: '150px'}}>Name</th>
                    <th>IP Address</th>
                    <th style={{width: '80px'}}>OS</th>
                    <th>Username</th>
                    <th style={{width: '150px'}}>Group</th>
                    <th>Auth Method</th>
                    <th>Health</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th className="text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {servers.map((server) => (
                    <tr key={server.id}>
                      <td>
                        <strong>{server.name}</strong>
                      </td>
                      <td>{server.ip}</td>
                                                                                                                                                                                                                                                <td style={{textAlign: 'center !important', verticalAlign: 'middle !important', paddingRight: '40px'}}>
                        {getOsDisplayName(server.detected_os)}
                      </td>
                      <td>{server.username}</td>
                      <td>
                        {server.groups && server.groups.length > 0 ? (
                          <div className="d-flex flex-wrap gap-1">
                            {server.groups.map((group) => (
                              <span 
                                key={group.id}
                                className="badge" 
                                style={{
                                  backgroundColor: group.color,
                                  color: 'white'
                                }}
                              >
                                {group.name}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="badge bg-secondary">No Groups</span>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${server.auth_method === 'password' ? 'bg-primary' : 'bg-success'}`}>
                          {server.auth_method === 'password' ? 'Password' : 'SSH Key'}
                        </span>
                      </td>
                      <td>
                        {serverHealth[server.id] ? (
                          <span 
                            className={`badge ${
                              serverHealth[server.id].status === 'healthy' ? 'bg-success' :
                              serverHealth[server.id].status === 'warning' ? 'bg-warning' :
                              serverHealth[server.id].status === 'critical' ? 'bg-danger' :
                              'bg-secondary'
                            }`}
                            title={`Health: ${serverHealth[server.id].status}\nLast checked: ${serverHealth[server.id].last_checked ? new Date(serverHealth[server.id].last_checked).toLocaleString() : 'Never'}`}
                            style={{ cursor: 'help' }}
                          >
                            {serverHealth[server.id].status === 'healthy' ? '💚 Healthy' :
                             serverHealth[server.id].status === 'warning' ? '⚠️ Warning' :
                             serverHealth[server.id].status === 'critical' ? '🔴 Critical' :
                             '❓ Unknown'}
                          </span>
                        ) : (
                          <span className="badge bg-secondary">No data</span>
                        )}
                      </td>
                      <td>
                        {connectionStatus[server.id] ? (
                          <span 
                            className={`badge ${connectionStatus[server.id].success ? 'bg-success' : 'bg-warning'}`}
                            title={`${connectionStatus[server.id].message}\nTime: ${connectionStatus[server.id].timestamp}\nDetails: ${connectionStatus[server.id].details}`}
                            style={{ cursor: 'help' }}
                          >
                            {connectionStatus[server.id].message.includes('Auto-test') ? (
                              connectionStatus[server.id].success ? '🔍 Auto-tested ✅' : '🔍 Auto-tested ⚠️'
                            ) : (
                              connectionStatus[server.id].success ? '✅ Online' : '⚠️ Warning'
                            )}
                          </span>
                        ) : (
                          <span className="badge bg-secondary">❌ Offline</span>
                        )}
                      </td>
                      <td>{formatDate(server.created_at)}</td>
                      <td>
                        <div className="d-flex gap-2 align-items-center justify-content-center" role="group">
                          {/* Edit Delete Group */}
                          <div className="btn-group" role="group">
                            <button
                              className="btn btn-outline-primary btn-sm"
                              onClick={() => handleEdit(server)}
                              title="Edit server configuration"
                            >
                              <i className="bi bi-pencil me-1"></i>
                              Edit
                            </button>
                            <button
                              className="btn btn-outline-danger btn-sm"
                              onClick={() => handleDelete(server)}
                              title="Delete this server"
                            >
                              <i className="bi bi-trash me-1"></i>
                              Delete
                            </button>
                          </div>
                          
                          {/* Visual separator */}
                          <div className="vr mx-1" style={{height: '20px'}}></div>
                          
                          {/* Health Test Group */}
                          <div className="btn-group" role="group">
                            <button
                              className="btn btn-outline-warning btn-sm"
                              onClick={() => checkServerHealth(server.id)}
                              title="Check server health metrics"
                            >
                              <i className="bi bi-heart-pulse me-1"></i>
                              Health
                            </button>
                            <button
                              className="btn btn-outline-info btn-sm"
                              onClick={() => testConnection(server.id)}
                              disabled={testingConnections[server.id]}
                              title="Test SSH connection to this server"
                            >
                              {testingConnections[server.id] ? (
                                <>
                                  <span className="spinner-border spinner-border-sm me-1" role="status"></span>
                                  Testing...
                                </>
                              ) : (
                                <>
                                  <i className="bi bi-link-45deg me-1"></i>
                                  Test
                                </>
                              )}
                            </button>
                          </div>
                          
                          {/* Visual separator */}
                          <div className="vr mx-1" style={{height: '20px'}}></div>
                          
                          {/* Connect Group */}
                          <div className="btn-group" role="group">
                            <button
                              className="btn btn-outline-success btn-sm"
                              onClick={() => openTerminal(server)}
                              title="Open terminal connection to this server"
                            >
                              <i className="bi bi-terminal me-1"></i>
                              Connect
                            </button>
                          </div>
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

        {/* Edit Server Modal */}
        {editingServer && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-pencil-square me-2"></i>
                    Edit Server: {editingServer.name}
                  </h5>
                  <button
                    type="button"
                    className="btn-close btn-close-white"
                    onClick={() => {
                      setEditingServer(null);
                      setEditForm({});
                    }}
                  ></button>
                </div>
                <form onSubmit={handleEditSubmit}>
                  <div className="modal-body">
                    <div className="mb-3">
                      <label htmlFor="serverName" className="form-label">Server Name</label>
                      <input
                        type="text"
                        className="form-control"
                        id="serverName"
                        value={editForm.name || ''}
                        onChange={(e) => setEditForm({...editForm, name: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="serverIP" className="form-label">IP Address</label>
                      <input
                        type="text"
                        className="form-control"
                        id="serverIP"
                        value={editForm.ip || ''}
                        onChange={(e) => setEditForm({...editForm, ip: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="serverUsername" className="form-label">Username</label>
                      <input
                        type="text"
                        className="form-control"
                        id="serverUsername"
                        value={editForm.username || ''}
                        onChange={(e) => setEditForm({...editForm, username: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Server Groups</label>
                      <div className="form-text mb-2">
                        <i className="bi bi-info-circle me-1"></i>
                        Select one or more groups for this server
                      </div>
                      {serverGroups.map((group) => (
                        <div key={group.id} className="form-check">
                          <input
                            className="form-check-input"
                            type="checkbox"
                            id={`editGroup${group.id}`}
                            checked={editForm.group_ids.includes(group.id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setEditForm({
                                  ...editForm,
                                  group_ids: [...editForm.group_ids, group.id]
                                });
                              } else {
                                setEditForm({
                                  ...editForm,
                                  group_ids: editForm.group_ids.filter(id => id !== group.id)
                                });
                              }
                            }}
                          />
                          <label className="form-check-label" htmlFor={`editGroup${group.id}`}>
                            <span 
                              className="badge me-2" 
                              style={{
                                backgroundColor: group.color,
                                color: 'white'
                              }}
                            >
                              {group.name}
                            </span>
                          </label>
                        </div>
                      ))}
                      {editForm.group_ids.length === 0 && (
                        <div className="text-muted small">
                          <i className="bi bi-info-circle me-1"></i>
                          No groups selected
                        </div>
                      )}
                    </div>
                    <div className="mb-3">
                      <label htmlFor="serverPassword" className="form-label">Password</label>
                      <input
                        type="password"
                        className="form-control"
                        id="serverPassword"
                        value={editForm.password || ''}
                        onChange={(e) => setEditForm({...editForm, password: e.target.value})}
                        placeholder="Leave blank to keep current password"
                      />
                      <div className="form-text">
                        <i className="bi bi-info-circle me-1"></i>
                        Leave blank to keep the current password. SSH keys are managed automatically.
                      </div>
                    </div>
                  </div>
                  <div className="modal-footer">
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => {
                        setEditingServer(null);
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

        {/* Create Server Modal */}
        {showCreateModal && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">
                    <i className="bi bi-plus-circle me-2"></i>
                    Create New Server
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
                      <label htmlFor="newServerName" className="form-label">Server Name</label>
                      <input
                        type="text"
                        className="form-control"
                        id="newServerName"
                        value={createForm.name || ''}
                        onChange={(e) => setCreateForm({...createForm, name: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newServerIP" className="form-label">IP Address</label>
                      <input
                        type="text"
                        className="form-control"
                        id="newServerIP"
                        value={createForm.ip || ''}
                        onChange={(e) => setCreateForm({...createForm, ip: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newServerUsername" className="form-label">Username</label>
                      <input
                        type="text"
                        className="form-control"
                        id="newServerUsername"
                        value={createForm.username || ''}
                        onChange={(e) => setCreateForm({...createForm, username: e.target.value})}
                        required
                      />
                    </div>
                    <div className="mb-3">
                      <label className="form-label">Server Groups (Optional)</label>
                      <div className="form-text mb-2">
                        <i className="bi bi-info-circle me-1"></i>
                        Select one or more groups for this server
                      </div>
                      {serverGroups.map((group) => (
                        <div key={group.id} className="form-check">
                          <input
                            className="form-check-input"
                            type="checkbox"
                            id={`createGroup${group.id}`}
                            checked={createForm.group_ids.includes(group.id)}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setCreateForm({
                                  ...createForm,
                                  group_ids: [...createForm.group_ids, group.id]
                                });
                              } else {
                                setCreateForm({
                                  ...createForm,
                                  group_ids: createForm.group_ids.filter(id => id !== group.id)
                                });
                              }
                            }}
                          />
                          <label className="form-check-label" htmlFor={`createGroup${group.id}`}>
                            <span 
                              className="badge me-2" 
                              style={{
                                backgroundColor: group.color,
                                color: 'white'
                              }}
                            >
                              {group.name}
                            </span>
                          </label>
                        </div>
                      ))}
                      {createForm.group_ids.length === 0 && (
                        <div className="text-muted small">
                          <i className="bi bi-info-circle me-1"></i>
                          No groups selected
                        </div>
                      )}
                    </div>
                    <div className="mb-3">
                      <div className="form-text">
                        <i className="bi bi-info-circle me-1"></i>
                        <strong>Authentication:</strong> Password-based initially, then automatically switches to SSH key after deployment
                      </div>
                    </div>
                    <div className="mb-3">
                      <label htmlFor="newServerPassword" className="form-label">Password</label>
                      <input
                        type="password"
                        className="form-control"
                        id="newServerPassword"
                        value={createForm.password || ''}
                        onChange={(e) => setCreateForm({...createForm, password: e.target.value})}
                        required
                      />
                    </div>
                                          {/* Auto-deployment info */}
                      <div className="alert alert-success border-0" style={{backgroundColor: 'rgba(16, 185, 129, 0.1)'}}>
                        <h6 className="alert-heading">
                          <i className="bi bi-rocket me-2"></i>
                          🚀 Automatic SSH Key Deployment
                        </h6>
                        <p className="mb-0">
                          <strong>When you create this server:</strong>
                          <br />
                          • SSH key pair will be automatically generated
                          <br />
                          • Public key will be deployed to the server
                          <br />
                          • Server will be ready for SSH key authentication
                          <br />
                          <small className="text-muted">
                            <i className="bi bi-lightning-charge me-1"></i>
                            Zero manual configuration required!
                          </small>
                        </p>
                      </div>
                      
                      {/* Auto-connection test info */}
                      <div className="alert alert-info border-0" style={{backgroundColor: 'rgba(6, 182, 212, 0.1)'}}>
                        <h6 className="alert-heading">
                          <i className="bi bi-check-circle me-2"></i>
                          🔍 Automatic Connection Test
                        </h6>
                        <p className="mb-0">
                          <strong>After server creation:</strong>
                          <br />
                          • Connection will be automatically tested
                          <br />
                          • Results will be displayed in the servers table
                          <br />
                          <small className="text-muted">
                            <i className="bi bi-lightning-charge me-1"></i>
                            Instant verification that your server is working!
                          </small>
                        </p>
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
                      Create Server
                    </button>
                  </div>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Create Progress Modal */}
        {showCreateProgressModal && (
          <div className="modal fade show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}>
            <div className="modal-dialog modal-lg">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title d-flex align-items-center">
                    <i className="bi bi-hdd-network me-2"></i>
                    Creating Server
                  </h5>
                  {createProgressStatus === 'error' ? (
                    <button
                      type="button"
                      className="btn-close btn-close-white"
                      onClick={() => setShowCreateProgressModal(false)}
                    ></button>
                  ) : null}
                </div>
                <div className="modal-body">
                  {createProgressStatus === 'running' && (
                    <div className="mb-3">
                      <span className="spinner-border spinner-border-sm text-primary me-2"></span>
                      <span>Working through steps...</span>
                    </div>
                  )}
                  {createProgressStatus === 'success' && (
                    <div className="mb-3 text-success">
                      <i className="bi bi-check-circle me-2"></i>
                      Completed successfully. Closing...
                    </div>
                  )}
                  {createProgressStatus === 'error' && (
                    <div className="mb-3 text-danger">
                      <i className="bi bi-x-circle me-2"></i>
                      Failed. Review the steps below.
                    </div>
                  )}
                  <div className="border rounded p-2" style={{maxHeight: '300px', overflowY: 'auto', background: 'var(--bg-card)'}}>
                    <ul className="mb-0" style={{listStyle: 'none', paddingLeft: 0}}>
                      {createLogs.map((line, idx) => (
                        <li key={idx} style={{fontFamily: 'monospace'}}>{line}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div className="modal-footer">
                  {createProgressStatus === 'error' ? (
                    <button type="button" className="btn btn-secondary" onClick={() => setShowCreateProgressModal(false)}>
                      Close
                    </button>
                  ) : (
                    <button type="button" className="btn btn-secondary" disabled>
                      Working...
                    </button>
                  )}
                </div>
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
                  <p>Are you sure you want to delete server <strong>{serverToDelete?.name}</strong>?</p>
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
                    Delete Server
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

                {/* Terminal Modal */}
                {terminalModal && (
          <div 
            className="modal fade show d-block" 
            style={{ 
              backgroundColor: 'rgba(0,0,0,0.7)', 
              zIndex: 9999,
              position: 'fixed',
              top: 0,
              left: 0,
              width: '100%',
              height: '100%'
            }}
          >
            <div 
              className="modal-dialog modal-xl terminal-modal" 
              style={{ 
                margin: 0,
                position: 'absolute',
                top: `${modalPosition.y}px`,
                left: `${modalPosition.x}px`,
                transform: 'none',
                maxWidth: '90vw',
                maxHeight: '90vh'
              }}
            >
                              <div className="modal-content">
                  <div 
                    className="modal-header"
                    onMouseDown={handleMouseDown}
                    onDoubleClick={centerModal}
                    style={{ 
                      cursor: isDragging ? 'grabbing' : 'grab',
                      userSelect: 'none',
                      backgroundColor: 'var(--bg-secondary)',
                      borderBottom: '1px solid #444'
                    }}
                  >
                    <h5 className="modal-title d-flex align-items-center">
                      <i className="bi bi-grip-vertical me-2 text-muted" title="Drag to move • Double-click to center"></i>
                      <i className="bi bi-terminal me-2"></i>
                      Terminal: {currentTerminalServer?.name} ({currentTerminalServer?.ip})
                      {!terminalConnected && (
                        <small className="text-muted ms-2">- Auto-connecting...</small>
                      )}
                    </h5>
                    <button
                      type="button"
                      className="btn-close btn-close-white"
                      onClick={closeTerminal}
                    ></button>
                  </div>
                <div className="modal-body">
                  {!terminalConnected ? (
                    <div className="text-center py-5">
                      <div className="mb-3">
                        <i className="bi bi-terminal text-primary" style={{fontSize: '3rem'}}></i>
                      </div>
                      {disconnectingTerminal ? (
                        <>
                          <h6>Disconnecting from {currentTerminalServer?.name}...</h6>
                          <p className="text-muted">
                            Closing SSH terminal session
                          </p>
                          <div className="spinner-border text-warning mb-3" role="status">
                            <span className="visually-hidden">Disconnecting...</span>
                          </div>
                        </>
                      ) : (
                        <>
                          <h6>Connecting to {currentTerminalServer?.name}...</h6>
                          <p className="text-muted">
                            Establishing SSH terminal session automatically
                          </p>
                          <div className="spinner-border text-primary mb-3" role="status">
                            <span className="visually-hidden">Connecting...</span>
                          </div>
                        </>
                      )}
                      
                      {/* Debug info */}
                      <div className="text-muted small">
                        <div>Server ID: {currentTerminalServer?.id}</div>
                        <div>IP: {currentTerminalServer?.ip}</div>
                        <div>Username: {currentTerminalServer?.username}</div>
                        <div>Auth Method: {currentTerminalServer?.auth_method}</div>
                      </div>
                    </div>
                  ) : (
                    <div className="terminal-container">
                      <div 
                        className="terminal-header p-2 rounded-top d-flex justify-content-between align-items-center"
                        style={{
                          backgroundColor: 'var(--bg-secondary)',
                          color: '#f8f8f2',
                          border: '1px solid #333',
                          borderBottom: '1px solid #444'
                        }}
                      >
                        <small className="d-flex align-items-center">
                          <i className="bi bi-terminal me-2 text-success"></i>
                          <span className="text-info">{currentTerminalServer?.username}</span>
                          <span className="text-muted mx-1">@</span>
                          <span className="text-warning">{currentTerminalServer?.ip}</span>
                        </small>
                        <button
                          className="btn"
                          onClick={clearTerminal}
                          title="Clear terminal output"
                          style={{
                            backgroundColor: 'var(--bg-tertiary)',
                            borderColor: 'var(--border-primary)',
                            color: 'var(--text-primary)'
                          }}
                        >
                          <i className="bi bi-trash me-1"></i>
                          Clear
                        </button>
                      </div>
                      <div 
                        className="terminal-body p-3 rounded-bottom"
                        style={{
                          minHeight: '400px', 
                          fontFamily: '"JetBrains Mono", "Fira Code", "Consolas", "Monaco", monospace',
                          fontSize: '13px',
                          lineHeight: '1.5',
                          overflowY: 'auto',
                          backgroundColor: 'var(--bg-card)',
                          color: 'var(--text-primary)',
                          border: '1px solid var(--border-primary)',
                          borderTop: 'none'
                        }}
                      >
                        {/* Terminal Output */}
                        <div className="terminal-output mb-3">
                          {terminalOutput.map((line, index) => (
                            <div 
                              key={index} 
                              className="terminal-line" 
                              style={{ 
                                whiteSpace: 'pre-wrap',
                                padding: '1px 0',
                                borderBottom: '1px solid transparent'
                              }}
                            >
                              {line}
                            </div>
                          ))}
                        </div>
                        
                        {/* Terminal Input */}
                        <div 
                          className="terminal-input-line"
                          style={{
                            borderTop: '1px solid #444',
                            paddingTop: '8px',
                            marginTop: '8px'
                          }}
                        >
                          <span 
                            style={{ 
                              color: '#50fa7b',
                              fontWeight: 'bold',
                              fontSize: '14px'
                            }}
                          >
                            $ 
                          </span>
                          <input
                            type="text"
                            className="border-0"
                            style={{
                              outline: 'none',
                              fontFamily: 'inherit',
                              fontSize: 'inherit',
                              width: 'calc(100% - 60px)',
                              backgroundColor: 'transparent',
                              color: '#f8f8f2',
                              caretColor: '#50fa7b'
                            }}
                            value={terminalInput}
                            onChange={(e) => setTerminalInput(e.target.value)}
                            onKeyDown={handleTerminalInputKeyPress}
                            placeholder=""
                            disabled={!terminalConnected}
                          />
                          {commandHistory.length > 0 && (
                            <small 
                              style={{ 
                                color: '#6272a4',
                                fontSize: '11px',
                                fontStyle: 'italic'
                              }}
                            >
                              ↑↓ History: {commandHistory.length} commands
                            </small>
                          )}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
                <div className="modal-footer">
                  <button
                    type="button"
                    className="btn btn-danger"
                    onClick={disconnectTerminal}
                  >
                    <i className="bi bi-plug me-2"></i>
                    Disconnect
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

export default ServerManagement;