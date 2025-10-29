# User Guide

## Getting Started

### First Login

1. **Access the application** at `http://localhost:3000`
2. **Login** with your credentials:
   - Default admin: `admin` / `password`
   - Or register a new account using the "Register" link

### Dashboard Overview

The dashboard provides three main sections:

#### 1. System Health (Admin Only)
- **Database Status**: Connection health and response time
- **Redis Status**: Cache and queue system health
- **Worker Queue**: Background job processing status
- **System Metrics**: Current load and execution statistics

#### 2. Server Health (Admin Only)
- **Individual Server Status**: Uptime, load, disk, and memory usage
- **Health Check Controls**: Manual health check triggers
- **Server Overview**: Quick status summary

#### 3. Script Statistics
- **Recent Executions**: Chart and table of recent script runs
- **Failing Executions**: List of failed script executions
- **Upcoming Schedules**: Scheduled script runs for the next 24 hours
- **Performance Charts**: Status distribution and top scripts

## Managing Servers

### Adding a Server

1. **Navigate** to "Servers" in the main menu
2. **Click** "Add Server" button
3. **Fill in server details**:
   - **Name**: Descriptive name for the server
   - **Hostname/IP**: Server address
   - **Username**: SSH username
   - **Port**: SSH port (default: 22)
   - **Authentication**: Choose SSH key or password
   - **SSH Key**: Paste your private key (if using key auth)
   - **Password**: Enter password (if using password auth)

4. **Click** "Create Server"

### Server Management

#### Viewing Servers
- **List View**: See all servers in a table format
- **Search**: Use the search box to find specific servers
- **Filter**: Filter by health status or authentication type

#### Server Actions
- **Edit**: Modify server configuration
- **Delete**: Remove server from the system
- **Health Check**: Trigger immediate health check
- **Terminal**: Open interactive terminal session
- **Execute Script**: Run a script directly on the server

#### Health Monitoring
- **Status Indicators**: Green (healthy), Yellow (warning), Red (critical)
- **Detailed Metrics**: Click "Show Details" to see:
  - Uptime information
  - System load (1-minute average)
  - Disk usage percentage
  - Memory usage percentage
  - Last health check timestamp

## Managing Scripts

### Creating Scripts

1. **Navigate** to "Scripts" in the main menu
2. **Click** "Create Script" button
3. **Enter script details**:
   - **Name**: Descriptive name for the script
   - **Description**: Optional description
   - **Content**: The actual script code

4. **Click** "Create Script"

### Script Execution

#### Direct Execution
1. **Select** a script from the scripts list
2. **Click** "Execute" button
3. **Choose execution method**:
   - **Individual Servers**: Select specific servers
   - **Server Group**: Execute on all servers in a group
4. **Set timeout** (optional)
5. **Click** "Execute Script"

#### Execution Status
- **Queued**: Script is waiting in the queue
- **Running**: Script is currently executing
- **Completed**: Script finished successfully
- **Failed**: Script encountered an error
- **Long Running**: Script has been running for extended time

### Script Management

#### Viewing Scripts
- **List View**: See all scripts with basic information
- **Search**: Find scripts by name or description
- **Sort**: Sort by name, creation date, or last execution

#### Script Actions
- **Edit**: Modify script content and details
- **Delete**: Remove script from the system
- **Execute**: Run the script immediately
- **View Executions**: See execution history
- **Copy**: Duplicate an existing script

## Scheduling Scripts

### Creating Schedules

1. **Navigate** to "Schedules" in the main menu
2. **Click** "Create Schedule" button
3. **Configure schedule**:
   - **Name**: Descriptive name for the schedule
   - **Cron Expression**: When to run (e.g., `0 2 * * *` for daily at 2 AM)
   - **Script**: Select which script to run
   - **Servers**: Choose target servers or server groups
   - **Enabled**: Toggle schedule on/off

4. **Click** "Create Schedule"

### Cron Expression Examples

| Expression | Description |
|------------|-------------|
| `0 2 * * *` | Daily at 2:00 AM |
| `0 */6 * * *` | Every 6 hours |
| `0 0 * * 0` | Weekly on Sunday at midnight |
| `0 0 1 * *` | Monthly on the 1st at midnight |
| `*/15 * * * *` | Every 15 minutes |

### Schedule Management

#### Viewing Schedules
- **List View**: See all schedules with next run times
- **Cron Display**: Human-readable cron expression
- **Status**: Enabled/disabled status
- **Next Run**: When the schedule will run next

#### Schedule Actions
- **Edit**: Modify schedule configuration
- **Delete**: Remove schedule
- **Toggle**: Enable/disable schedule
- **Run Now**: Execute schedule immediately

## Workflow Builder

### Creating Workflows

1. **Navigate** to "Workflows" in the main menu
2. **Click** "Create Workflow" button
3. **Design workflow**:
   - **Add Nodes**: Drag and drop different node types
   - **Connect Nodes**: Link nodes to create execution flow
   - **Configure Nodes**: Set parameters for each node

### Node Types

#### Trigger Nodes
- **Schedule Trigger**: Run workflow on a schedule
- **Manual Trigger**: Run workflow manually
- **Webhook Trigger**: Run workflow via HTTP request

#### Action Nodes
- **Script Node**: Execute a script on servers
- **Condition Node**: Add conditional logic
- **Delay Node**: Add delays between actions
- **Notification Node**: Send notifications

#### Data Nodes
- **Input Node**: Define workflow inputs
- **Output Node**: Define workflow outputs
- **Variable Node**: Store and manipulate data

### Workflow Execution

#### Running Workflows
- **Manual Execution**: Click "Run" button
- **Scheduled Execution**: Based on trigger configuration
- **Monitor Progress**: Real-time execution monitoring

#### Execution Monitoring
- **Node Status**: See which nodes are running, completed, or failed
- **Execution Logs**: View detailed execution logs
- **Error Handling**: See where and why workflows fail

## Terminal Sessions

### Opening Terminal

1. **Navigate** to "Servers" page
2. **Find** the server you want to access
3. **Click** "Terminal" button
4. **Wait** for connection to establish

### Using Terminal

#### Basic Commands
- **Navigation**: `cd`, `ls`, `pwd`
- **File Operations**: `cat`, `vi`, `nano`, `cp`, `mv`, `rm`
- **System Info**: `top`, `htop`, `df`, `free`
- **Process Management**: `ps`, `kill`, `killall`

#### Terminal Features
- **Real-time Output**: See command output as it happens
- **Interactive Commands**: Run interactive programs like `vi` or `htop`
- **Command History**: Use arrow keys to navigate command history
- **Tab Completion**: Press Tab for command/file completion

#### Stopping Commands
- **Ctrl+C**: Stop current running command
- **Ctrl+D**: End terminal session
- **Close Button**: Close terminal window

## Monitoring and Logs

### Execution History

1. **Navigate** to "Executions" page
2. **View execution list** with:
   - Script name and server
   - Execution status and timing
   - Output preview
   - Exit codes

#### Filtering Executions
- **Status Filter**: Show only completed, running, or failed executions
- **Date Range**: Filter by execution date
- **Script Filter**: Show executions for specific scripts
- **Server Filter**: Show executions for specific servers

#### Execution Details
- **Full Output**: View complete script output
- **Error Messages**: See detailed error information
- **Execution Time**: Start and end times
- **Resource Usage**: CPU and memory usage (if available)

### Audit Logs

1. **Navigate** to "Audit Logs" page
2. **View system activities**:
   - User logins and logouts
   - Script executions
   - Server modifications
   - Schedule changes
   - System configuration changes

#### Exporting Logs
- **CSV Export**: Download logs as CSV file
- **JSON Export**: Download logs as JSON file
- **Date Range**: Export specific date ranges

## Settings and Configuration

### Application Settings (Admin Only)

1. **Navigate** to "Settings" page
2. **Configure system parameters**:
   - **Max Concurrent Executions**: Maximum number of simultaneous script executions
   - **Long Running Delay**: Time before marking scripts as "long running"
   - **Schedule Tolerance**: Tolerance for schedule trigger timing
   - **Token Expiry**: JWT token expiration time

### User Preferences

#### Profile Management
- **Change Password**: Update your password
- **Update Email**: Change email address
- **View Role**: See your current role and permissions

#### Notification Settings
- **Email Notifications**: Configure email alerts
- **Execution Alerts**: Get notified of script failures
- **System Alerts**: Receive system health notifications

## Troubleshooting

### Common Issues

#### Script Execution Problems
- **Permission Denied**: Check script permissions on target server
- **Command Not Found**: Verify command paths and dependencies
- **Timeout Issues**: Increase timeout or optimize script performance
- **SSH Connection Failed**: Verify server credentials and connectivity

#### Schedule Issues
- **Schedules Not Running**: Check if schedules are enabled
- **Wrong Timing**: Verify cron expression syntax
- **Server Unavailable**: Ensure target servers are online

#### Terminal Connection Issues
- **Connection Timeout**: Check server SSH service
- **Authentication Failed**: Verify SSH credentials
- **Permission Denied**: Check user permissions on server

### Getting Help

#### Self-Service
1. **Check Documentation**: Review this guide and API documentation
2. **View Logs**: Check execution logs and audit logs
3. **Health Checks**: Use system health monitoring

#### Support
1. **Contact Admin**: Reach out to system administrator
2. **Report Issues**: Use the issue reporting system
3. **Check Status**: View system status page

## Best Practices

### Script Development
- **Test Locally**: Test scripts on local machines first
- **Use Absolute Paths**: Avoid relative paths in scripts
- **Handle Errors**: Include proper error handling
- **Add Logging**: Include logging statements in scripts
- **Document Scripts**: Add comments and descriptions

### Security
- **Use SSH Keys**: Prefer SSH key authentication over passwords
- **Limit Permissions**: Use least privilege principle
- **Regular Updates**: Keep servers and scripts updated
- **Monitor Access**: Review audit logs regularly

### Performance
- **Optimize Scripts**: Write efficient scripts
- **Use Timeouts**: Set appropriate execution timeouts
- **Monitor Resources**: Watch server resource usage
- **Batch Operations**: Group related operations together

### Maintenance
- **Regular Backups**: Backup important scripts and configurations
- **Clean Up Logs**: Regularly clean old execution logs
- **Update Schedules**: Review and update schedules as needed
- **Monitor Health**: Use health monitoring features
