# Dashboard Operational Fixes - Requirements Document

**Project Creator:** Herman Swanepoel  
**Document Version:** 1.0  
**Last Updated:** December 13, 2025

## Introduction

The Aura IA MCP Dashboard V3 "Grand Unification" is currently deployed but experiencing several operational issues that prevent users from accessing real-time system data and functionality. This specification addresses critical dashboard problems including non-functional governance data, chat performance issues, missing model statistics, and mocked monitoring data that needs to be replaced with live server metrics.

## Glossary

- **Dashboard**: The web-based monitoring UI running on port 9205
- **Governance Tab**: The administrative interface showing role hierarchy and audit logs
- **AI System Panel**: Widget displaying current model loading status and statistics
- **Chat Feature**: Interactive chat interface supporting multiple modes (Concierge, Debug, etc.)
- **Intelligence Arena**: Model comparison interface showing debate statistics and model performance
- **Omni Monitor**: Real-time system monitoring dashboard showing server metrics
- **WebSocket**: Real-time bidirectional communication protocol for live data updates
- **Model Gateway**: Service managing model lifecycle and routing (port 9200)
- **Role Engine**: Service managing permissions and governance (port 9206)
- **Ollama Service**: External LLM container service (port 9207)
- **PostgreSQL**: Database service storing conversations and debate history (port 9208)

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want to view governance data in the dashboard, so that I can monitor role hierarchies and audit system activities.

#### Acceptance Criteria

1. WHEN a user clicks the Governance tab, THE Dashboard SHALL fetch and display the complete role hierarchy from the Role Engine
2. WHEN governance data is requested, THE Role Engine SHALL return all active roles with their capabilities and trust levels
3. WHEN audit logs are requested, THE Dashboard SHALL display recent security events from the audit log file
4. WHEN the governance tab loads, THE Dashboard SHALL show both role tree visualization and audit log entries within 3 seconds
5. WHEN role data is unavailable, THE Dashboard SHALL display a clear error message with retry option

### Requirement 2

**User Story:** As a system operator, I want to see accurate model loading status, so that I can verify which AI models are currently active and available.

#### Acceptance Criteria

1. WHEN the AI System panel loads, THE Dashboard SHALL query the Model Gateway for current model status
2. WHEN models are loaded in Ollama, THE AI System panel SHALL display the actual model names and memory usage
3. WHEN no models are loaded, THE AI System panel SHALL show "No models currently loaded" with a load button
4. WHEN model status changes, THE Dashboard SHALL update the display within 5 seconds via WebSocket
5. WHEN model loading fails, THE Dashboard SHALL display the specific error message and suggested actions

### Requirement 3

**User Story:** As a user, I want chat responses to be fast and reliable, so that I can interact with the AI system efficiently.

#### Acceptance Criteria

1. WHEN a user sends a chat message, THE Chat Feature SHALL respond within 30 seconds for normal queries
2. WHEN the chat system is overloaded, THE Dashboard SHALL display a queue position and estimated wait time
3. WHEN a chat request times out, THE Dashboard SHALL provide a retry option and error explanation
4. WHEN switching chat modes, THE Dashboard SHALL update the interface within 2 seconds
5. WHEN the Ollama service is unavailable, THE Chat Feature SHALL display a clear service status message

### Requirement 4

**User Story:** As a system analyst, I want to view model performance statistics in the Intelligence Arena, so that I can analyze model effectiveness and debate outcomes.

#### Acceptance Criteria

1. WHEN the Intelligence Arena loads, THE Dashboard SHALL display all available models with their current status
2. WHEN model statistics are requested, THE Dashboard SHALL show win rates, total debates, and performance metrics from PostgreSQL
3. WHEN a model is selected, THE Intelligence Arena SHALL display detailed match history and confidence scores
4. WHEN new debate results are available, THE Dashboard SHALL update statistics in real-time via WebSocket
5. WHEN no debate history exists, THE Intelligence Arena SHALL show placeholder data with "Start Debate" option

### Requirement 5

**User Story:** As a database administrator, I want to monitor database health and connections, so that I can ensure data persistence and system reliability.

#### Acceptance Criteria

1. WHEN the database widget loads, THE Dashboard SHALL display PostgreSQL connection status and active connections
2. WHEN database metrics are requested, THE Dashboard SHALL show table sizes, query performance, and connection pool status
3. WHEN database issues occur, THE Dashboard SHALL display specific error messages and health indicators
4. WHEN database performance degrades, THE Dashboard SHALL show warning indicators and performance metrics
5. WHEN the database is unreachable, THE Dashboard SHALL display connection retry options and status

### Requirement 6

**User Story:** As a system monitor, I want real-time server metrics including GPU and temperature data, so that I can track system performance and prevent overheating.

#### Acceptance Criteria

1. WHEN the Omni Monitor loads, THE Dashboard SHALL display live CPU, RAM, disk, and network metrics from the server
2. WHEN GPU monitoring is available, THE Dashboard SHALL show GPU utilization, memory usage, and temperature
3. WHEN temperature sensors are detected, THE Dashboard SHALL display CPU and system temperatures with warning thresholds
4. WHEN system metrics exceed safe thresholds, THE Dashboard SHALL display warning indicators and alerts
5. WHEN WebSocket connection fails, THE Dashboard SHALL fall back to polling mode and display connection status

### Requirement 7

**User Story:** As a system integrator, I want WebSocket-based real-time updates, so that dashboard data stays current without manual refreshing.

#### Acceptance Criteria

1. WHEN the dashboard loads, THE System SHALL establish WebSocket connections to all monitoring endpoints
2. WHEN server data changes, THE Dashboard SHALL receive updates via WebSocket within 2 seconds
3. WHEN WebSocket connections drop, THE Dashboard SHALL automatically attempt reconnection with exponential backoff
4. WHEN real-time updates are received, THE Dashboard SHALL update relevant widgets without full page refresh
5. WHEN WebSocket is unavailable, THE Dashboard SHALL fall back to HTTP polling every 10 seconds

### Requirement 8

**User Story:** As a developer, I want comprehensive error handling and logging, so that dashboard issues can be quickly diagnosed and resolved.

#### Acceptance Criteria

1. WHEN API calls fail, THE Dashboard SHALL log detailed error information to browser console
2. WHEN WebSocket connections fail, THE Dashboard SHALL display connection status indicators to users
3. WHEN data parsing errors occur, THE Dashboard SHALL show user-friendly error messages with technical details in console
4. WHEN services are unavailable, THE Dashboard SHALL provide service-specific status information and retry options
5. WHEN critical errors occur, THE Dashboard SHALL offer a "Reset Dashboard" option to restore functionality
