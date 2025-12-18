# Phase 7: Frontend Evolution - Implementation Plan

## Objective

Upgrade the Aura_IA_MCP Dashboard to a professional, "Dark Kiro IDE" themed monitoring and interaction center, fully integrated with the backend services.

## Goals

1. **Visual Upgrade**: Implement the design from `docs/dashboard_design_guide.md`.
    - Static activity items (no flashing).
    - Correct color palette (Dark Mode + Cyan/Purple accents).
    - Responsive layout with Sidebar, Main Content, Chat Bar, and Footer.
2. **Deep Integration (Step 3)**:
    - **Real-time Streaming**: Implement WebSocket client for debate streaming and live updates.
    - **Graph Visualization**: Visualize DAG execution (potentially using React Flow if complexity demands).
    - **Metrics**: Embed Grafana charts or custom visualizations for system stats.
3. **Chat Interface**:
    - Functional chat bar to send commands to the agent.
    - Display agent responses in the main content area or a dedicated chat panel.
4. **Asset Management**:
    - Integrate user-provided Logo.
    - Ensure correct favicon and static assets.

## Architecture Decision

- **Framework**: Start with Vanilla HTML/JS/CSS for simplicity and speed.
- **Migration Trigger**: If state management (DAGs, complex chat, real-time streams) becomes unmanageable, **migrate to React/Vue** immediately.

## Steps

### 1. Asset Setup

- [x] Create `dashboard/assets/` directory.
- [x] Import User Logo (`AuraIA New Logo (1).jpg` - Purple/Cyan gradient, dark theme).

### 2. Dashboard Refactoring

- [x] Refactor `dashboard/mcp_monitor_dashboard.html` (or create `index.html`) to match the Design Guide.
- [x] Extract CSS to `dashboard/assets/style.css`.
- [x] Extract JS to `dashboard/assets/app.js`.

### 3. Deep Backend Integration

- [ ] **WebSockets**: Implement client for real-time debate streaming.
- [x] **Metrics**: Connect to `http://localhost:9200` (MCP), `9206` (Role Engine), and `9201` (ML) for live stats.
- [x] **Visualization**: Add DAG execution graph (using a lightweight library first, e.g., Cytoscape.js or Mermaid, before jumping to React Flow).

### 4. Chat Implementation

- [x] Implement `sendMessage()` function in `app.js`.
- [ ] Connect to the LLM/Agent endpoint.

### 5. Docker Update

- [x] Verify `docker/Dockerfile.dashboard` serves the new static files correctly (likely using Nginx or a simple Python server).

### 6. Verification

- [x] Manual check of the UI.
- [x] Automated test `tests/test_phase7_frontend.py` to verify endpoint availability and content presence.

## Pre-Rebuild Checklist

Before final Docker rebuild for production:

- [ ] **Move Docker Data to SSD**: Relocate Docker disk image to `F:\MCP_Aura_IA` for faster startup
  - Docker Desktop → Settings → Resources → Advanced → "Disk image location" → `F:\MCP_Aura_IA`
  - This will dramatically reduce the 98% HDD spike during container startup
- [ ] Verify all local tests pass
- [ ] Confirm canonical ports (9200-9206) are correctly mapped

## User Action Required

- Please provide the **Aura_IA Logo** (SVG preferred, or PNG).
- Please confirm if the **Color Scheme** provided in the Design Guide is the final one, or if you have specific hex codes to override.
