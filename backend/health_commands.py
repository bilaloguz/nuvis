"""
Health check commands for different operating systems
"""
import re
from typing import Dict, Any, Optional
from datetime import datetime

def parse_uptime_linux(output: str) -> Optional[int]:
    """Parse uptime from Linux uptime command"""
    try:
        # Format: " 14:30:25 up 2 days,  3:45,  1 user,  load average: 0.52, 0.58, 0.59"
        match = re.search(r'up\s+(\d+)\s+days?,\s*(\d+):(\d+)', output)
        if match:
            days, hours, minutes = map(int, match.groups())
            return days * 86400 + hours * 3600 + minutes * 60
        
        # Format: " 14:30:25 up  3:45,  1 user,  load average: 0.52, 0.58, 0.59"
        match = re.search(r'up\s+(\d+):(\d+)', output)
        if match:
            hours, minutes = map(int, match.groups())
            return hours * 3600 + minutes * 60
            
        # Format: " 14:30:25 up 45 min,  1 user,  load average: 0.52, 0.58, 0.59"
        match = re.search(r'up\s+(\d+)\s+min', output)
        if match:
            return int(match.group(1)) * 60
            
        return None
    except:
        return None

def parse_load_average(output: str) -> Dict[str, float]:
    """Parse load average from uptime command"""
    try:
        # Format: "load average: 0.52, 0.58, 0.59"
        match = re.search(r'load average:\s*([\d.]+),\s*([\d.]+),\s*([\d.]+)', output)
        if match:
            return {
                'load_1min': float(match.group(1)),
                'load_5min': float(match.group(2)),
                'load_15min': float(match.group(3))
            }
        return {}
    except:
        return {}

def parse_disk_usage_linux(output: str) -> Optional[float]:
    """Parse disk usage from df command"""
    try:
        # Format: "/dev/sda1       20G  5.2G   14G  28% /"
        lines = output.strip().split('\n')
        for line in lines[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 5 and parts[4].endswith('%'):
                return float(parts[4].rstrip('%'))
        return None
    except:
        return None

def parse_memory_usage_linux(output: str) -> Optional[float]:
    """Parse memory usage from free command"""
    try:
        # Format: "Mem:       16384       8192       8192          0        512       6144"
        lines = output.strip().split('\n')
        for line in lines:
            if line.startswith('Mem:'):
                parts = line.split()
                if len(parts) >= 3:
                    total = int(parts[1])
                    used = int(parts[2])
                    if total > 0:
                        return (used / total) * 100
        return None
    except:
        return None

def parse_cpu_usage_linux(output: str) -> Optional[float]:
    """Parse CPU usage from top command (simplified)"""
    try:
        # This is a simplified parser - in production you'd want more sophisticated parsing
        # Format: "%Cpu(s):  5.2 us,  1.3 sy,  0.0 ni, 93.4 id,  0.1 wa,  0.0 hi,  0.0 si,  0.0 st"
        match = re.search(r'%Cpu\(s\):\s*([\d.]+)\s+us', output)
        if match:
            return float(match.group(1))
        return None
    except:
        return None

def parse_network_interfaces_linux(output: str) -> Dict[str, Any]:
    """Parse network interface stats from ifconfig or ip"""
    try:
        interfaces = {}
        lines = output.strip().split('\n')
        current_interface = None
        
        for line in lines:
            # Interface line: "eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 1500"
            if ':' in line and ('flags=' in line or 'state' in line):
                current_interface = line.split(':')[0]
                interfaces[current_interface] = {
                    'status': 'up' if 'UP' in line or 'state UP' in line else 'down',
                    'mtu': None,
                    'rx_bytes': 0,
                    'tx_bytes': 0
                }
                
                # Extract MTU
                mtu_match = re.search(r'mtu\s+(\d+)', line)
                if mtu_match:
                    interfaces[current_interface]['mtu'] = int(mtu_match.group(1))
            
            # RX/TX stats: "RX packets 12345  bytes 6789012 (6.4 MiB)"
            elif current_interface and 'RX packets' in line:
                rx_match = re.search(r'RX packets\s+\d+\s+bytes\s+(\d+)', line)
                if rx_match:
                    interfaces[current_interface]['rx_bytes'] = int(rx_match.group(1))
            
            elif current_interface and 'TX packets' in line:
                tx_match = re.search(r'TX packets\s+\d+\s+bytes\s+(\d+)', line)
                if tx_match:
                    interfaces[current_interface]['tx_bytes'] = int(tx_match.group(1))
        
        return interfaces
    except:
        return {}

# Windows parsing functions
def parse_uptime_windows(output: str) -> Optional[int]:
    """Parse uptime from Windows systeminfo command"""
    try:
        # Format: "System Boot Time:          12/25/2023, 2:30:45 PM"
        match = re.search(r'System Boot Time:\s*(\d+)/(\d+)/(\d+),\s*(\d+):(\d+):(\d+)\s*(AM|PM)', output)
        if match:
            month, day, year, hour, minute, second, ampm = match.groups()
            
            # Convert to 24-hour format
            hour = int(hour)
            if ampm == 'PM' and hour != 12:
                hour += 12
            elif ampm == 'AM' and hour == 12:
                hour = 0
            
            boot_time = datetime(int(year), int(month), int(day), hour, int(minute), int(second))
            uptime = datetime.now() - boot_time
            return int(uptime.total_seconds())
        return None
    except:
        return None

def parse_disk_usage_windows(output: str) -> Optional[float]:
    """Parse disk usage from Windows wmic command"""
    try:
        # Format: "Caption  FreeSpace     Size        \nC:       1234567890   9876543210"
        lines = output.strip().split('\n')
        for line in lines[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 3 and parts[0].endswith(':'):
                try:
                    free_space = int(parts[1])
                    total_space = int(parts[2])
                    if total_space > 0:
                        used_percent = ((total_space - free_space) / total_space) * 100
                        return used_percent
                except ValueError:
                    continue
        return None
    except:
        return None

def parse_memory_usage_windows(output: str) -> Optional[float]:
    """Parse memory usage from Windows wmic command"""
    try:
        # Format: "FreePhysicalMemory=1234567\nTotalVisibleMemorySize=2345678"
        total_memory = None
        free_memory = None
        
        for line in output.strip().split('\n'):
            if 'TotalVisibleMemorySize=' in line:
                total_memory = int(line.split('=')[1])
            elif 'FreePhysicalMemory=' in line:
                free_memory = int(line.split('=')[1])
        
        if total_memory and free_memory and total_memory > 0:
            used_memory = total_memory - free_memory
            return (used_memory / total_memory) * 100
        return None
    except:
        return None

def parse_cpu_usage_windows(output: str) -> Optional[float]:
    """Parse CPU usage from Windows wmic command"""
    try:
        # Format: "LoadPercentage=25"
        match = re.search(r'LoadPercentage=(\d+)', output)
        if match:
            return float(match.group(1))
        return None
    except:
        return None

def parse_network_interfaces_windows(output: str) -> Dict[str, Any]:
    """Parse network interface stats from Windows ipconfig command"""
    try:
        interfaces = {}
        lines = output.strip().split('\n')
        current_interface = None
        
        for line in lines:
            # Interface line: "Ethernet adapter Ethernet:"
            if 'adapter' in line and ':' in line:
                current_interface = line.split(':')[0].strip()
                interfaces[current_interface] = {
                    'status': 'unknown',
                    'mtu': None,
                    'rx_bytes': 0,
                    'tx_bytes': 0
                }
            
            # Status line: "Media State . . . . . . . . . . : Media disconnected"
            elif current_interface and 'Media State' in line:
                if 'disconnected' in line:
                    interfaces[current_interface]['status'] = 'down'
                else:
                    interfaces[current_interface]['status'] = 'up'
        
        return interfaces
    except:
        return {}

# Health check commands for different OS
HEALTH_COMMANDS = {
    'linux': {
        'uptime': 'uptime',
        'disk': 'df -h /',
        'memory': 'free -m',
        'cpu': 'top -bn1 | head -n 3',
        'network': 'ifconfig'
    },
    'windows': {
        'uptime': 'systeminfo | findstr "System Boot Time"',
        'disk': 'wmic logicaldisk where size>0 get size,freespace,caption',
        'memory': 'wmic OS get TotalVisibleMemorySize,FreePhysicalMemory /value',
        'cpu': 'wmic cpu get loadpercentage /value',
        'network': 'ipconfig /all'
    }
}

def get_health_commands(os_type: str = 'linux') -> Dict[str, str]:
    """Get health check commands for the specified OS"""
    return HEALTH_COMMANDS.get(os_type, HEALTH_COMMANDS['linux'])

def detect_os(ssh_client) -> str:
    """Detect the operating system of the remote server"""
    try:
        stdin, stdout, stderr = ssh_client.exec_command('uname -s')
        output = stdout.read().decode('utf-8').strip().lower()
        if 'linux' in output:
            return 'linux'
        elif 'windows' in output or 'microsoft' in output:
            return 'windows'
    except:
        pass
    
    try:
        # Try Windows-specific command
        stdin, stdout, stderr = ssh_client.exec_command('ver')
        output = stdout.read().decode('utf-8').strip().lower()
        if 'windows' in output or 'microsoft' in output:
            return 'windows'
    except:
        pass
    
    # Default to Linux if detection fails
    return 'linux'

def parse_health_output(os_type: str, command_type: str, output: str) -> Dict[str, Any]:
    """Parse health check output based on OS and command type"""
    result = {}
    
    if os_type == 'linux':
        if command_type == 'uptime':
            result['uptime_seconds'] = parse_uptime_linux(output)
            result.update(parse_load_average(output))
        elif command_type == 'disk':
            result['disk_usage'] = parse_disk_usage_linux(output)
        elif command_type == 'memory':
            result['memory_usage'] = parse_memory_usage_linux(output)
        elif command_type == 'cpu':
            result['cpu_usage'] = parse_cpu_usage_linux(output)
        elif command_type == 'network':
            result['network_interfaces'] = parse_network_interfaces_linux(output)
    
    elif os_type == 'windows':
        if command_type == 'uptime':
            result['uptime_seconds'] = parse_uptime_windows(output)
        elif command_type == 'disk':
            result['disk_usage'] = parse_disk_usage_windows(output)
        elif command_type == 'memory':
            result['memory_usage'] = parse_memory_usage_windows(output)
        elif command_type == 'cpu':
            result['cpu_usage'] = parse_cpu_usage_windows(output)
        elif command_type == 'network':
            result['network_interfaces'] = parse_network_interfaces_windows(output)
    
    return result

def determine_health_status(load_1min: Optional[float], disk_usage: Optional[float], 
                          memory_usage: Optional[float], cpu_usage: Optional[float]) -> str:
    """Determine overall health status based on metrics"""
    critical_thresholds = {
        'load': 5.0,
        'disk': 90.0,
        'memory': 90.0,
        'cpu': 90.0
    }
    
    warning_thresholds = {
        'load': 2.0,
        'disk': 80.0,
        'memory': 80.0,
        'cpu': 80.0
    }
    
    # Check for critical conditions
    if (load_1min and load_1min > critical_thresholds['load']) or \
       (disk_usage and disk_usage > critical_thresholds['disk']) or \
       (memory_usage and memory_usage > critical_thresholds['memory']) or \
       (cpu_usage and cpu_usage > critical_thresholds['cpu']):
        return 'critical'
    
    # Check for warning conditions
    if (load_1min and load_1min > warning_thresholds['load']) or \
       (disk_usage and disk_usage > warning_thresholds['disk']) or \
       (memory_usage and memory_usage > warning_thresholds['memory']) or \
       (cpu_usage and cpu_usage > warning_thresholds['cpu']):
        return 'warning'
    
    return 'healthy'
