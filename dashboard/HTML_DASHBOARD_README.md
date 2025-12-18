# Aura IA MCP Documentation

## What is MCP?

The **Model Context Protocol (MCP)** is an open standard from Anthropic that lets AI assistants securely connect to external data sources, tools, and services. It acts as a universal bridge between AI models and the systems they need—databases, APIs, file systems, and custom business logic—reducing custom integration overhead and making assistants more capable.

Aura IA MCP implements this protocol to expose a rich suite of intelligent tools for analysis, semantic search, ML insights, workflow orchestration, and more. Requests flow through the MCP Gateway to specialized backend services, each optimized for a specific task (emotion analysis, RLHF predictions, vector queries, etc.). The result is an enterprise-grade AI experience with observability, security, and extensibility built in.

---

## MCP Tool Reference (76 Tools, 14 Categories)

### Core Gateway Tools (12)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Health Check | `ide_agents_health()` | Diagnostics: status, version, flags.<br>*Example:* `→ {"status": "ok", "version": "2.0"}` |
| Liveness Probe | `ide_agents_healthz()` | Kubernetes liveness probe.<br>*Example:* `→ {"status": "live"}` |
| Readiness Probe | `ide_agents_readyz()` | Readiness with backend connectivity.<br>*Example:* `→ {"status": "ready", "backend_ok": true}` |
| Metrics Snapshot | `ide_agents_metrics_snapshot()` | Current Prometheus metrics.<br>*Example:* Returns request counts/latencies. |
| Run Command | `ide_agents_run_command(command, payload)` | Execute backend command.<br>*Example:* `(command="echo hello")` |
| List Entities | `ide_agents_list_entities()` | List backend entity mappings.<br>*Example:* Registered entities list. |
| Fetch Documentation | `ide_agents_fetch_doc(topic)` | Documentation snippet by topic.<br>*Example:* `(topic="security")` |
| Consolidated Command | `ide_agents_command(action, command)` | run | dry_run | explain.<br>*Example:* `(action="run", command="date")` |
| Catalog Access | `ide_agents_catalog(action, topic)` | list_entities | get_doc.<br>*Example:* `(action="get_doc", topic="rank")` |
| Resource Access | `ide_agents_resource(method, name)` | Read-only resources.<br>*Example:* `(method="get", name="config")` |
| Prompt Access | `ide_agents_prompt(method, name)` | Workflow prompts.<br>*Example:* `(method="get", name="code_review")` |
| Server Instructions | `ide_agents_server_instructions()` | Server instructions + version.<br>*Example:* Returns instruction set. |

### ML Intelligence Tools (15)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Emotion Analysis | `ide_agents_ml_analyze_emotion(text)` | Analyze emotional tone.<br>*Example:* `(text="Great work!")` → `{ "mood": "positive" }` |
| Get Predictions | `ide_agents_ml_get_predictions(user_id)` | Predictive suggestions.<br>*Example:* `(user_id="dev1")` |
| Learning Insights | `ide_agents_ml_get_learning_insights(user_id)` | Learning analytics.<br>*Example:* Returns patterns/insights. |
| Reasoning Analysis | `ide_agents_ml_analyze_reasoning(command)` | Reasoning steps & safety.<br>*Example:* `(command="delete data")` |
| Personality Profile | `ide_agents_ml_get_personality_profile()` | Current AI personality.<br>*Example:* `{ "tone": "professional" }` |
| Adjust Personality | `ide_agents_ml_adjust_personality(mood, tone)` | Adjust mood/tone.<br>*Example:* `(mood="engaged", tone="casual")` |
| System Status | `ide_agents_ml_get_system_status()` | ML engines status.<br>*Example:* `{ "emotion": "active" }` |
| Calibrate Confidence | `ide_agents_ml_calibrate_confidence(raw_score)` | Calibrate confidence.<br>*Example:* `(raw_score=0.85)` → `0.78` |
| RLHF Ranking | `ide_agents_ml_rank_predictions_rlhf(user_id, candidates)` | Rank predictions via RLHF.<br>*Example:* Ranked candidate list. |
| Record Outcome | `ide_agents_ml_record_prediction_outcome(prediction_id, user_accepted)` | Record RLHF feedback.<br>*Example:* `(prediction_id="p1", user_accepted=true)` |
| Calibration Metrics | `ide_agents_ml_get_calibration_metrics()` | Brier/ROC metrics.<br>*Example:* `{ "brier_score": 0.23 }` |
| RLHF Metrics | `ide_agents_ml_get_rlhf_metrics()` | Acceptance rate & reward.<br>*Example:* `{ "acceptance_rate": 0.61 }` |
| Behavioral Baseline | `ide_agents_ml_behavioral_baseline_check(user_id)` | Baseline deviation.<br>*Example:* Deviation score/anomalies. |
| Auto Adaptation | `ide_agents_ml_trigger_auto_adaptation(reason)` | Trigger auto-adaptation.<br>*Example:* `(reason="feedback")` |
| ULTRA Dashboard | `ide_agents_ml_get_ultra_dashboard()` | Comprehensive ML dashboard.<br>*Example:* Calibration, RLHF, engines. |

### GitHub Integration Tools (3)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| List Repos | `ide_agents_github_repos(visibility, limit)` | List repos with filters.<br>*Example:* `(visibility="private", limit=10)` |
| Rank Repos | `ide_agents_github_rank_repos(query, top)` | Semantic ranking of repos.<br>*Example:* `(query="ML projects", top=5)` |
| Rank All | `ide_agents_github_rank_all(query, state)` | Rank repos/issues/PRs.<br>*Example:* `(query="bugs", state="open")` |

### ULTRA Semantic Tools (2)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| ULTRA Rank | `ide_agents_ultra_rank(query, candidates)` | Semantic rank candidates.<br>*Example:* `(query="ML framework", candidates=["PyTorch","React"])` |
| ULTRA Calibrate | `ide_agents_ultra_calibrate(scores)` | Calibrate confidence scores.<br>*Example:* `(scores=[0.9,0.7,0.5])` |

### Debate Engine Tools (4)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Start Debate | `ide_agents_debate_start(topic, rounds)` | Start debate session.<br>*Example:* `(topic="AI Ethics", rounds=3)` |
| Submit Argument | `ide_agents_debate_submit(debate_id, role, argument)` | Submit debate argument.<br>*Example:* `(debate_id="d1", role="proponent")` |
| Judge Debate | `ide_agents_debate_judge(debate_id, criteria)` | Judge and score debate.<br>*Example:* Returns winner/scores. |
| Debate History | `ide_agents_debate_history(debate_id)` | Get debate history/results.<br>*Example:* Transcript and outcome. |

### DAG Workflow Tools (3)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Create DAG | `ide_agents_dag_create(name, tasks, dependencies)` | Create DAG workflow.<br>*Example:* `(name="pipeline", tasks=[...])` |
| Execute DAG | `ide_agents_dag_execute(workflow_id, inputs)` | Execute workflow.<br>*Example:* `(workflow_id="wf1")` |
| Visualize DAG | `ide_agents_dag_visualize(workflow_id, format)` | Mermaid/ASCII diagram.<br>*Example:* `(format="mermaid")` |

### Risk & Approval Tools (3)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Analyze Risk | `ide_agents_risk_analyze(operation, context)` | Assess risk level.<br>*Example:* `(operation="delete_data")` → `{"risk":"high"}` |
| Route Risk | `ide_agents_risk_route(operation, risk_level)` | Route to handler/approval.<br>*Example:* Routes based on risk. |
| Risk History | `ide_agents_risk_history(limit)` | Past risk assessments.<br>*Example:* `(limit=20)` |

### Role Engine Tools (5)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| List Roles | `ide_agents_role_list(category)` | List available roles.<br>*Example:* Role taxonomy. |
| Get Role | `ide_agents_role_get(role_name)` | Role details/capabilities.<br>*Example:* `(role_name="architect")` |
| Check Permission | `ide_agents_role_check(role_name, permission)` | Verify permission.<br>*Example:* `(role="admin", permission="write:config")` |
| Assign Role | `ide_agents_role_assign(role_name, context_id)` | Assign role to context.<br>*Example:* `(role_name="developer", context_id="ctx1")` |
| Evaluate Role | `ide_agents_role_evaluate(task_description)` | Best role for task.<br>*Example:* `(task="design API")` |

### RAG Vector Database Tools (5)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| RAG Query | `ide_agents_rag_query(query, collection, top_k)` | Semantic KB search.<br>*Example:* `(query="deployment", top_k=5)` |
| RAG Upsert | `ide_agents_rag_upsert(content, metadata, collection)` | Add/update document.<br>*Example:* `(content="...", metadata={...})` |
| RAG Delete | `ide_agents_rag_delete(document_id, collection)` | Delete document.<br>*Example:* `(document_id="doc1")` |
| RAG Search | `ide_agents_rag_search(query, filters, top_k)` | Search with filters.<br>*Example:* `(filters={"category":"docs"})` |
| RAG Status | `ide_agents_rag_status()` | RAG service status/stats.<br>*Example:* Collection counts. |

### Ollama LLM Tools (5)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Consult LLM | `ollama_consult(prompt, model, temperature)` | Chat with local LLMs.<br>*Example:* `(prompt="Explain REST", model="llama3")` |
| List Models | `ollama_list_models()` | List available models.<br>*Example:* `→ ["llama3", "codellama", "mistral"]` |
| Pull Model | `ollama_pull_model(model)` | Download model.<br>*Example:* `(model="codellama:13b")` |
| Model Info | `ollama_model_info(model)` | Model metadata.<br>*Example:* `(model="llama3")` |
| Ollama Health | `ollama_health()` | Ollama service health.<br>*Example:* `→ {"status":"ok"}` |

### Security & Audit Tools (4)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Security Anomalies | `ide_agents_security_anomalies(window_seconds)` | Anomalies in window.<br>*Example:* `(window_seconds=3600)` |
| Reload Config | `ide_agents_reload()` | Reload caches/thresholds.<br>*Example:* Refresh configs. |
| Check PII | `check_pii(text, redact)` | PII check/redact.<br>*Example:* `(text="email@test.com", redact=true)` |
| Security Audit | `get_security_audit(limit, action_filter)` | Audit log entries.<br>*Example:* `(limit=20)` |

### Audio I/O Tools (5)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Speech to Text | `speech_to_text(audio_base64, sample_rate)` | Audio → text (Vosk).<br>*Example:* `(audio_base64="...")` |
| Text to Speech | `text_to_speech(text, speed)` | Text → audio (Coqui).<br>*Example:* `(text="Welcome", speed=1.0)` |
| STT Status | `get_stt_status()` | STT service status.<br>*Example:* `{ "status": "ready" }` |
| TTS Status | `get_tts_status()` | TTS service status.<br>*Example:* `{ "status": "ready" }` |
| Audio Health | `audio_health()` | Combined audio health.<br>*Example:* `{ "stt": "ok", "tts": "ok" }` |

### Futuristic Computing Tools (6)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Carbon Intensity | `check_carbon_intensity(region)` | Carbon intensity for region.<br>*Example:* `(region="US-CAL")` |
| Schedule Green Job | `schedule_green_job(job_name, priority, deadline)` | Carbon-efficient scheduling.<br>*Example:* `(priority="low", deadline_hours=24)` |
| Carbon Budget | `get_carbon_budget()` | Carbon budget usage.<br>*Example:* `{ "used":45, "remaining":55 }` |
| List WASM Plugins | `list_wasm_plugins()` | Available WASM plugins.<br>*Example:* Plugin catalog. |
| Execute WASM | `execute_wasm_plugin(plugin_name, function, args)` | Secure WASM execution.<br>*Example:* `(plugin_name="calc", function="add")` |
| Enclave Status | `get_enclave_status()` | Confidential enclave status.<br>*Example:* `{ "enclave":"active" }` |

### Observability Tools (4)

| Tool | Function Name | Description & Example |
|:-----|:--------------|:----------------------|
| Get Metrics | `get_metrics(service, metric_type)` | Prometheus metrics snapshot.<br>*Example:* `(service="gateway", metric_type="latency")` |
| Query Traces | `query_traces(trace_id, service, limit)` | Jaeger trace queries.<br>*Example:* `(service="ml-backend", limit=10)` |
| Get Alerts | `get_alerts(severity)` | Prometheus alerts.<br>*Example:* `(severity="critical")` |
| Dashboard URL | `get_dashboard_url(dashboard)` | Grafana dashboard links.<br>*Example:* `(dashboard="overview")` |

---

*Aura IA MCP v2.0 — Enterprise AI Infrastructure*
