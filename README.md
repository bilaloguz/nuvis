# Nuvis (Infrastructure Orchestration Platform)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-High_Performance-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://reactjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?logo=docker)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Nuvis** (formerly biRun) is a distributed infrastructure automation and orchestration platform designed for DevOps teams and SysAdmins. It enables centralized management, monitoring, and execution of scripts across heterogeneous server environments (Linux & Windows) without installing agents.

Unlike simple script runners, Nuvis features a powerful **Visual Workflow Builder (DAG)** capable of handling complex dependencies, conditional logic, and self-healing scenarios.

---

## 📸 Visual Tour

### 1. The Command Center
*Real-time system health, server status, and execution metrics at a glance.*
<img src="docs/screenshots/03-main-dashboard.png" width="100%" alt="Nuvis Dashboard">

### 2. Visual Workflow Orchestration
**The Core Power of Nuvis:** A Node-based Workflow Engine. Define dependencies, set failure policies (e.g., "If Node A fails, run Cleanup Node B"), and visualize the execution path.
<img src="docs/screenshots/20-workflow-builder.png" width="100%" alt="Workflow Builder">

### 3. Live Remote Execution
Interact with remote servers directly via the web interface. Supports real-time stdout/stderr streaming over WebSocket/SSE.
<img src="docs/screenshots/25-terminal-interface.png" width="100%" alt="Terminal View">

---

## 🚀 Key Features

* **Agentless Architecture:** Connects to nodes via secure **SSH Tunnels** (Linux) or standard protocols, removing the need to install agents on target servers.
* **Multi-Language Support:** Natively supports **Bash**, **PowerShell**, and **Python** scripts.
* **Smart Scheduling:** Support for Cron expressions and Interval-based scheduling with "Trigger Tolerance" to handle missed execution windows.
* **Virtual Timeouts:** Intelligent handling of infinite processes (like `ping -t`) with snapshot logic to prevent zombie processes.
* **Audit & Security:** Immutable logs of every action and Role-Based Access Control (RBAC).

---

## 🔍 Deep Dive (UI Gallery)

<details>
<summary><strong>Click to expand and view the full interface gallery</strong></summary>
<br>

| Server Management | Script Management |
|:---:|:---:|
| <img src="docs/screenshots/07-servers-page.png" width="400"> | <img src="docs/screenshots/15-scripts-list.png" width="400"> |
| *Inventory & Health Checks* | *Script Library & Types* |

| Scheduling (Cron) | Audit Logs |
|:---:|:---:|
| <img src="docs/screenshots/17-create-schedule-form.png" width="400"> | <img src="docs/screenshots/29-audit-logs.png" width="400"> |
| *Complex Time Definitions* | *Security Tracking* |

| Settings & Config | Execution Details |
|:---:|:---:|
| <img src="docs/screenshots/31-settings-page.png" width="400"> | <img src="docs/screenshots/28-execution-details.png" width="400"> |
| *System Tuning* | *Live Output Streams* |

</details>

---

## 🏗 Architecture

Nuvis follows a **Centralized Orchestrator Pattern** to ensure data integrity.

```mermaid
graph TD
    User((User))
    UI[React Frontend]
    API[Core API <br/> FastAPI]
    DB[(PostgreSQL)]
    Queue[(Task Queue <br/> Redis)]
    
    subgraph "Execution Layer"
        Worker[Worker Node]
    end
    
    subgraph "Target Infrastructure"
        Linux[Linux Server <br/> SSH]
        Win[Windows Server <br/> SSH/PS]
    end

    User --> UI
    UI --> API
    API <--> DB
    API -- "Push Job" --> Queue
    Queue -- "Consume" --> Worker
    Worker -- "Execute Script" --> Linux
    Worker -- "Execute Script" --> Win
    Worker -- "Result/Log" --> API
