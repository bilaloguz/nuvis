# Nuvis (Infrastructure Orchestration Platform)

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.68%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://reactjs.org/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED?logo=docker)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Nuvis** is a distributed infrastructure automation and orchestration platform. It allows DevOps engineers and SysAdmins to manage, monitor, and execute complex script workflows across heterogeneous server environments (Linux & Windows) from a centralized interface.

Unlike simple script runners, Nuvis features a **Visual Workflow Builder (DAG)** capable of handling conditional logic, group failure policies, and self-healing scenarios.

![Nuvis Dashboard](docs/dashboard.png)
[cite_start]*(Screenshot: Real-time System & Server Health Dashboard)* [cite: 42-46]

---

## 🚀 Key Features

### 1. Visual Workflow Orchestration
Build complex automation pipelines using a node-based Drag-and-Drop editor.
* [cite_start]**Conditional Logic:** Define "On Success" and "On Failure" paths [cite: 392-393].
* [cite_start]**Group Failure Policies:** Configure whether a workflow fails if *any* node fails or only if *all* nodes fail[cite: 378].
* [cite_start]**Retry Logic:** Automatic retries with configurable intervals for transient network issues[cite: 367].

### 2. Distributed Remote Execution
* **Agentless:** Connects to target nodes via secure **SSH Tunnels** (Linux) or WinRM/SSH (Windows).
* [cite_start]**Multi-Language Support:** Natively supports **Bash**, **PowerShell**, and **Python** scripts[cite: 229].
* [cite_start]**Virtual Terminal:** Web-based interactive terminal for ad-hoc commands on remote servers [cite: 153-155].

### 3. Enterprise-Grade Observability
* [cite_start]**Health Checks:** Real-time monitoring of CPU, RAM, and Disk usage across the server fleet[cite: 130].
* [cite_start]**Audit Logging:** Immutable logs of every user action (who executed what, when, and where)[cite: 454].
* [cite_start]**Virtual Timeouts:** Smart handling of infinite processes (e.g., `ping -t`) with "snapshot" logic to prevent zombie processes[cite: 235].

---

## 🏗 Architecture

Nuvis follows a **Centralized Orchestrator Pattern** to ensure data integrity and scalable execution.

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
