# Dashboard Operational Fixes - Implementation Plan

**Project Creator:** Herman Swanepoel  
**Document Version:** 1.0  
**Last Updated:** December 13, 2025

## Implementation Plan

This implementation plan addresses all identified dashboard issues through a systematic approach that enhances backend APIs, implements WebSocket real-time updates, and fixes frontend data display problems. Each task builds incrementally to ensure a fully functional dashboard with live monitoring capabilities.

- [x] 1. Backend API Enhancements and WebSocket Infrastructure

  - Create WebSocket endpoints for real-time data streaming
  - Enhance existing APIs to provide comprehensive data
  - Implement system monitoring with GPU and temperature support
  - Add database monitoring capabilities
  - _Requirements: 1.1, 1.2, 2.1, 2.2, 5.1, 6.1, 6.2, 7.1_

- [x] 1.1 Create WebSocket Manager Infrastructure

  - Implement WebSocketManager class in `aura_ia_mcp/services/websocket_manager.py`
  - Add WebSocket dependency management and connection pooling
  - Create base WebSocket endpoint handlers with error handling
  - _Requirements: 7.1, 7.3_

- [ ]\* 1.2 Write property test for WebSocket connection management

  - **Property 7: WebSocket Connection Management**
  - **Validates: Requirements 7.1, 7.3**

- [x] 1.3 Enhance Role Engine with Governance WebSocket Endpoint

  - Add `/ws/governance` WebSocket endpoint to `ops/role_engine/are_service.py`
  - Implement `/api/governance/roles` REST endpoint for role hierarchy
  - Add `/api/governance/audit-logs` endpoint for security audit events
  - Parse and format audit log files for dashboard consumption
  - _Requirements: 1.1, 1.2, 1.3_

- [ ]\* 1.4 Write property test for governance data loading

  - **Property 1: Governance Data Loading**
  - **Validates: Requirements 1.1, 1.2**

- [x] 1.5 Enhance Model Gateway with Real-time Model Status

  - Add `/ws/models` WebSocket endpoint to `src/mcp_server/ide_agents_mcp_server.py`
  - Implement real-time Ollama API integration for model status
  - Add model performance statistics from PostgreSQL integration
  - Create model lifecycle information endpoint
  - _Requirements: 2.1, 2.2, 4.1, 4.2_

- [ ]\* 1.6 Write property test for model status accuracy

  - **Property 2: Model Status Accuracy**
  - **Validates: Requirements 2.1, 2.2**

- [x] 1.7 Create System Monitoring Service

  - Implement `SystemMonitor` class in `aura_ia_mcp/services/system_monitor.py`
  - Add CPU, RAM, disk, and network monitoring via psutil
  - Implement GPU monitoring with GPUtil library
  - Add temperature sensor monitoring when available
  - Create `/ws/system` WebSocket endpoint for real-time metrics
  - _Requirements: 6.1, 6.2_

- [ ]\* 1.8 Write property test for system metrics collection

  - **Property 6: System Metrics Collection**
  - **Validates: Requirements 6.1**

- [ ]\* 1.9 Write property test for GPU monitoring conditional display

  - **Property 10: GPU Monitoring Conditional Display**
  - **Validates: Requirements 6.2**

- [x] 1.10 Create Database Monitoring Service

  - Implement `DatabaseMonitor` class in `aura_ia_mcp/services/database_monitor.py`
  - Add PostgreSQL connection and performance metrics
  - Implement table size and slow query monitoring
  - Create `/ws/database` WebSocket endpoint for database metrics
  - _Requirements: 5.1, 5.2_

- [ ]\* 1.11 Write property test for database monitoring accuracy

  - **Property 5: Database Monitoring Accuracy**
  - **Validates: Requirements 5.1, 5.2**

- [-] 2. Frontend WebSocket Integration and Real-time Updates

  - Implement WebSocket client management in dashboard
  - Create real-time update handlers for all dashboard components
  - Add connection status indicators and error handling
  - _Requirements: 7.1, 7.2, 7.3, 8.1, 8.2_

- [x] 2.1 Create Frontend WebSocket Manager

  - Implement `WebSocketManager` class in `dashboard/assets/websocket-manager.js`
  - Add automatic reconnection with exponential backoff
  - Implement connection status tracking and error handling
  - Create fallback to HTTP polling when WebSocket unavailable
  - _Requirements: 7.1, 7.3_

- [ ]\* 2.2 Write property test for real-time update delivery

  - **Property 4: Real-time Update Delivery**
  - **Validates: Requirements 7.2**

- [x] 2.3 Enhance AI System Panel with Real Model Data

  - Update `AISystemPanel` class in `dashboard/assets/app.js`
  - Connect to `/ws/models` WebSocket for real-time model updates
  - Display actual loaded models with memory usage and statistics
  - Add model loading/unloading controls
  - Remove "No model loaded" placeholder with dynamic content
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 2.4 Fix Governance Tab Data Loading

  - Update governance tab HTML structure in `dashboard/index.html`
  - Implement role hierarchy visualization with tree structure
  - Connect to `/ws/governance` WebSocket for real-time updates
  - Add audit log table with filtering and refresh capabilities
  - Display role capabilities and trust levels
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2.5 Create Intelligence Arena with Model Statistics

  - Implement model performance display with win rates and statistics
  - Connect to debate WebSocket for real-time debate updates
  - Add model comparison interface with detailed match history
  - Create "Load All Models" button with statistics overview
  - Display debate outcomes and model rankings from PostgreSQL

  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x]\* 2.6 Write property test for intelligence arena data integrity

  - **Property 9: Intelligence Arena Data Integrity**
  - **Validates: Requirements 4.2**

- [-] 2.7 Create Database Monitoring Widget

  - Add database widget to Omni Monitor tab
  - Display PostgreSQL connection status and active connections
  - Show database size, table sizes, and performance metrics
  - Connect to `/ws/database` WebSocket for real-time updates
  - Add database health indicators and alerts
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [-] 2.8 Enhance Omni Monitor with Real Server Data

  - Replace mocked data with real-time server metrics
  - Connect to `/ws/system` WebSocket for live updates
  - Display CPU, RAM, disk, network, GPU, and temperature data
  - Add performance graphs and threshold alerts
  - Implement responsive design for metric displays
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 3. Chat Performance Optimization and Error Handling

  - Optimize chat response times across all modes
  - Implement comprehensive error handling and user feedback
  - Add connection status indicators and retry mechanisms
  - _Requirements: 3.1, 3.2, 3.3, 8.1, 8.2, 8.3_

- [x] 3.1 Optimize Chat Performance and Timeout Handling

  - Review and optimize chat routing in `src/mcp_server/services/chat_service.py`
  - Implement proper timeout handling with user feedback
  - Add queue position display for overloaded systems
  - Optimize Ollama API calls and connection pooling
  - _Requirements: 3.1, 3.2_

- [x] 3.2 Write property test for chat response performance

  - **Property 3: Chat Response Performance**
  - **Validates: Requirements 3.1**

- [x] 3.3 Enhance Chat Error Handling and User Feedback

  - Add comprehensive error messages for chat failures
  - Implement retry mechanisms with exponential backoff
  - Display service status when Ollama is unavailable
  - Add chat mode switching optimization
  - _Requirements: 3.3, 3.4, 3.5, 8.1_

- [x]\* 3.4 Write property test for error logging completeness

  - **Property 8: Error Logging Completeness**
  - **Validates: Requirements 8.1, 8.2**

- [x] 4. Configuration and Dependencies

  - Add required dependencies for monitoring and WebSocket support
  - Create configuration files for dashboard settings
  - Update Docker configurations for new dependencies
  - _Requirements: All requirements (infrastructure support)_

- [x] 4.1 Add Required Dependencies

  - Add `psutil` for system monitoring to requirements files
  - Add `GPUtil` for GPU monitoring (optional dependency)
  - Add `websockets` for WebSocket support
  - Update `docker/Dockerfile.mcp` with new dependencies
  - _Requirements: 6.1, 6.2, 7.1_

- [x] 4.2 Create Dashboard Configuration

  - Create `config/dashboard_config.yaml` with WebSocket and monitoring settings
  - Add environment variables for feature toggles
  - Configure update intervals and connection parameters
  - Add GPU and temperature monitoring feature flags
  - _Requirements: 6.2, 7.1, 7.3_

- [x] 4.3 Update Docker Compose Configuration

  - Add environment variables for new monitoring features
  - Ensure proper service networking for WebSocket connections
  - Add health checks for new monitoring endpoints
  - _Requirements: All requirements (deployment support)_

- [x] 5. Testing and Validation

  - Implement comprehensive test suite for all new functionality
  - Create integration tests with live services
  - Add browser tests for WebSocket functionality
  - _Requirements: All requirements (quality assurance)_

- [x] 5.1 Create Integration Tests for WebSocket Functionality

  - Test WebSocket connections with live backend services
  - Validate real-time updates across all dashboard components
  - Test error scenarios and fallback mechanisms
  - Verify performance requirements under normal load
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 5.2 Create Browser Tests with Playwright

  - Test WebSocket functionality across different browsers
  - Validate real-time updates and UI responsiveness
  - Test error message display and user interactions
  - Verify mobile responsiveness of enhanced components
  - _Requirements: All requirements (cross-browser compatibility)_

- [x] 5.3 Create Performance Tests

  - Test chat response times under various load conditions
  - Validate WebSocket update latency requirements
  - Test system monitoring accuracy and performance
  - Verify database monitoring efficiency
  - _Requirements: 3.1, 6.1, 7.2_

- [x] 6. Checkpoint - Ensure All Tests Pass

  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Deployment and Documentation

  - Deploy enhanced dashboard to production server
  - Update documentation with new features and APIs
  - Create user guide for new dashboard capabilities
  - _Requirements: All requirements (production readiness)_

- [x] 7.1 Deploy to Production Server


  - Transfer updated code to NAS server at {{NAS_IP}}
  - Rebuild Docker containers with new dependencies
  - Verify all WebSocket endpoints are accessible
  - Test dashboard functionality in production environment
  - _Requirements: All requirements (production deployment)_

- [x] 7.2 Update Documentation

  - Update API documentation with new WebSocket endpoints
  - Document new monitoring capabilities and configuration options
  - Create troubleshooting guide for WebSocket issues
  - Update system requirements for GPU monitoring
  - _Requirements: All requirements (documentation)_

- [x] 7.3 Create User Guide

  - Document new dashboard features and capabilities
  - Create screenshots and usage examples
  - Explain real-time monitoring and alert systems
  - Provide configuration guidance for administrators
  - _Requirements: All requirements (user documentation)_

- [x] 8. Final Checkpoint - Complete System Verification



  - Ensure all tests pass, ask the user if questions arise.
