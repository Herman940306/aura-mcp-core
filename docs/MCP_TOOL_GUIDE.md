# Aura_IA_MCP Tool Guide & Cheatsheet

This guide provides a comprehensive reference for all 47 tools available in the Aura_IA_MCP system. It is designed to be a "cheatsheet" for understanding the full capabilities of the system.

## 1. Health & Status Tools

*Tools for monitoring system health and service status.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`check_health`** | Check the health status of MCP backend services. | `check_health()`<br>Returns: `{"status": "ok", "services": {...}}` |
| **`get_system_status`** | Get comprehensive system status including all services. | `get_system_status()`<br>Returns: Detailed status of all components. |
| **`get_model_status`** | Get status of ML models (sentiment, semantic, etc.). | `get_model_status()`<br>Returns: Model load status and versions. |
| **`get_activity_stats`** | Get recent activity statistics from MCP. | `get_activity_stats()`<br>Returns: Usage counts, active sessions. |

## 2. Data Retrieval & Documentation

*Tools for accessing system information and documentation.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`get_documentation`** | Get documentation for a specific MCP topic. | `get_documentation(topic="command")`<br>**topic**: Topic to query (command, emotion, rank, github). |
| **`list_entities`** | List all available MCP entities/tools. | `list_entities()`<br>Returns: List of registered entities. |
| **`list_available_tools`** | List all available tools the AI assistant can use. | `list_available_tools()`<br>Returns: List of tool names and descriptions. |
| **`get_project_status`** | Get comprehensive project status from MASTER_PROJECT_STATUS.md. | `get_project_status(section="all")`<br>**section**: phases, milestones, architecture, all. |
| **`get_config`** | Get current MCP configuration settings. | `get_config(section="all")`<br>**section**: backend, gateway, rag, all. |

## 3. Command Execution & Operations

*Tools for executing system commands and operations.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`execute_command`** | Execute a safe shell command. | `execute_command(command="date")`<br>**command**: Safe command (echo, ls, pwd, whoami, date). |
| **`list_github_repos`** | List GitHub repositories (requires GITHUB_TOKEN). | `list_github_repos(per_page=5)`<br>**per_page**: Number of repos to list. |

## 4. AI & Machine Learning

*Tools for AI analysis and semantic processing.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`analyze_emotion`** | Analyze the emotional tone of text. | `analyze_emotion(text="I am happy")`<br>**text**: Input text to analyze. |
| **`semantic_rank`** | Rank candidates by semantic similarity to a query. | `semantic_rank(query="fruit", candidates=["apple", "car"])`<br>**query**: Search query.<br>**candidates**: List of strings to rank. |

## 5. RAG & Knowledge Base

*Tools for interacting with the Vector Database and Knowledge Base.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`semantic_search`** | Perform semantic search against the RAG knowledge base. | `semantic_search(query="deployment", collection="default", top_k=5)`<br>**query**: Search query.<br>**collection**: Target collection.<br>**top_k**: Number of results. |
| **`add_to_knowledge_base`** | Add a document or text to the RAG knowledge base. | `add_to_knowledge_base(content="...", metadata={...})`<br>**content**: Text content.<br>**metadata**: JSON metadata.<br>**collection**: Target collection. |
| **`list_collections`** | List all RAG collections and their document counts. | `list_collections()`<br>Returns: Collection names and stats. |

## 6. Debugging & Diagnostics

*Tools for troubleshooting and log analysis.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`get_recent_logs`** | Get recent log entries from MCP services. | `get_recent_logs(service="all", lines=20)`<br>**service**: backend, gateway, all.<br>**lines**: Number of lines. |
| **`diagnose_issue`** | Run diagnostic checks and suggest fixes. | `diagnose_issue(symptom="high latency")`<br>**symptom**: Description of the issue. |
| **`search_logs`** | Search logs using Loki log aggregation. | `search_logs(query="error", service="backend", level="error")`<br>**query**: LogQL query.<br>**service**: Service name.<br>**level**: Log level. |

## 7. Advanced Intelligence (Phase 4)

*Tools for complex reasoning, debates, and workflows.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`start_debate`** | Start a dual-model debate on a topic. | `start_debate(topic="AI Safety", proponent_stance="...", opponent_stance="...")`<br>**topic**: Debate topic.<br>**stances**: Arguments for each side. |
| **`get_debate_status`** | Get status/results of a debate. | `get_debate_status(debate_id="...")`<br>**debate_id**: ID of the debate. |
| **`create_workflow`** | Create a DAG workflow with tasks. | `create_workflow(workflow_name="...", tasks=[...])`<br>**tasks**: List of task objects with dependencies. |
| **`execute_workflow`** | Execute a previously created DAG workflow. | `execute_workflow(workflow_id="...")`<br>**workflow_id**: ID of the workflow. |
| **`visualize_dag`** | Generate a Mermaid diagram of a workflow DAG. | `visualize_dag(workflow_id="...")`<br>**workflow_id**: ID of the workflow. |
| **`evaluate_risk`** | Evaluate risk level of an operation. | `evaluate_risk(operation="file_write", context={...})`<br>**operation**: Operation name.<br>**context**: Operation details. |
| **`request_approval`** | Request approval for high-risk operations. | `request_approval(operation="...", reason="...", risk_level="high")`<br>**operation**: Operation name.<br>**reason**: Justification.<br>**risk_level**: Assessed risk. |

## 8. Role Engine (ARE+)

*Tools for role-based access control and capabilities.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`list_roles`** | List all available roles in the Role Taxonomy. | `list_roles()`<br>Returns: List of roles and descriptions. |
| **`get_role_capabilities`** | Get detailed capabilities for a specific role. | `get_role_capabilities(role_name="architect")`<br>**role_name**: Name of the role. |
| **`suggest_role`** | Suggest the best role for a given task. | `suggest_role(task_description="...", required_capabilities=[...])`<br>**task_description**: Task details. |
| **`check_permission`** | Check if a role has permission for an action. | `check_permission(role_name="...", action="read:config")`<br>**role_name**: Role name.<br>**action**: Permission string. |

## 9. Observability (Phase 5)

*Tools for metrics, traces, and monitoring.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`get_metrics`** | Get Prometheus metrics (requests, latency, errors). | `get_metrics(service="all", metric_type="all")`<br>**service**: Service name.<br>**metric_type**: requests, latency, errors. |
| **`query_traces`** | Query distributed traces from OpenTelemetry. | `query_traces(trace_id="...", service="...")`<br>**trace_id**: Specific trace ID.<br>**service**: Filter by service. |
| **`get_alerts`** | Get active Prometheus alerts. | `get_alerts(severity="critical")`<br>**severity**: info, warning, critical. |
| **`get_dashboard_url`** | Get URL to Grafana dashboard. | `get_dashboard_url(dashboard="overview")`<br>**dashboard**: overview, gateway, ml, rag. |

## 10. Futuristic Computing (Phase 6)

*Tools for green computing and secure enclaves.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`check_carbon_intensity`** | Check carbon intensity for green scheduling. | `check_carbon_intensity(region="US-CAL")`<br>**region**: Geographic region. |
| **`schedule_green_job`** | Schedule a job for carbon-efficient timing. | `schedule_green_job(job_name="...", priority="low", deadline_hours=24)`<br>**priority**: low, normal, high. |
| **`get_carbon_budget`** | Get current carbon budget usage. | `get_carbon_budget()`<br>Returns: Budget stats. |
| **`list_wasm_plugins`** | List available WASM sandbox plugins. | `list_wasm_plugins()`<br>Returns: List of plugins. |
| **`execute_wasm_plugin`** | Execute a WASM plugin in sandbox. | `execute_wasm_plugin(plugin_name="...", function="...", args={...})`<br>**plugin_name**: Plugin to run.<br>**function**: Function to call. |
| **`get_enclave_status`** | Get status of confidential computing enclaves. | `get_enclave_status()`<br>Returns: Enclave security status. |

## 11. Security Tools

*Tools for PII protection and auditing.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`check_pii`** | Check text for PII and optionally redact. | `check_pii(text="...", redact=True)`<br>**text**: Input text.<br>**redact**: Boolean flag. |
| **`audit_log`** | Add an entry to the security audit log. | `audit_log(action="...", details={...})`<br>**action**: Event name.<br>**details**: Event metadata. |
| **`get_security_audit`** | Retrieve recent security audit log entries. | `get_security_audit(limit=20, action_filter="...")`<br>**limit**: Max entries.<br>**action_filter**: Filter by action. |

## 12. Audio I/O (Phase 8.12)

*Tools for Speech-to-Text and Text-to-Speech.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`speech_to_text`** | Convert speech audio to text (Vosk). | `speech_to_text(audio_base64="...", sample_rate=16000)`<br>**audio_base64**: Base64 WAV data.<br>**sample_rate**: Hz (default 16000). |
| **`text_to_speech`** | Convert text to speech (Coqui). | `text_to_speech(text="...", speed=1.0)`<br>**text**: Text to speak.<br>**speed**: 0.5-2.0. |
| **`get_stt_status`** | Get STT service status. | `get_stt_status()`<br>Returns: Service health. |
| **`get_tts_status`** | Get TTS service status. | `get_tts_status()`<br>Returns: Service health. |

## 13. Role Engine Advanced (Future Enhancements)

*Advanced tools for role arbitration and simulation.*

| Tool Name | Description | Usage / Parameters |
| :--- | :--- | :--- |
| **`arbitrate_roles`** | Resolve disagreements between roles using weighted voting. | `arbitrate_roles(roles=["architect", "developer"], context="...")`<br>**roles**: List of roles involved.<br>**context**: Description of the conflict. |
| **`run_role_simulation`** | Run a simulation of role interactions for a scenario. | `run_role_simulation(scenario="code_review", roles=["architect", "developer"], steps=5)`<br>**scenario**: Name of the scenario.<br>**roles**: Participating roles.<br>**steps**: Number of interaction steps. |

---
*Generated on November 30, 2025 for Aura_IA_MCP V.1.8*
