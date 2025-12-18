# Dashboard Fixes (V.1.9.5 Feedback)

*Status: Collecting Feedback*

## Visual/UI Issues

- [ ] FIX ALIGNMENT (CSS/Layout issue)
  - Panel `#panel-ai` columns not evenly spaced; metrics compress left/right edges.
  - Inconsistent padding inside `.widget-panel-header` vs body; top bar feels detached.
  - Badge sizing visually overpowering (height vs surrounding text baseline).
  - Duplicate CSS declarations causing override noise (e.g. repeated `display: none` / `display: block`).
- [ ] SHOWS ERROR (Visible error state on UI)
  - Need screenshot reference: user reported generic error block (cause unknown yet).
- [ ] DAG GRAPH EMPTY (Panel shows no rendered graph)
  - `renderDagGraph()` targets `#dag-viz` but panel markup for `#panel-dag` missing child container.
  - Mermaid init runs; likely DOM element absent ⇒ silent no-op.
  - Need to verify if CSS hides graph (e.g., height:0 / overflow) once container added.

## Functional Issues

- [ ] NO CONNECTION? (Dashboard header shows offline/checking)
  - `#ai-status` remains `OFFLINE` despite backend healthy; likely fetch failure or stale status update logic.
  - Possible missing interval refresh or promise rejection not handled.
- [ ] NOT WORKING, NO FEEDBACK TEXT (Chat input or status text missing)
  - Status/feedback region not updating after actions; confirm DOM id mismatch or missing innerText assignment.
- [ ] BACKEND OFFLINE INDICATOR (System status corner shows Offline)
 	- Element `#backend-status` dot animates with `var(--danger)` even when backend expected up.
 	- `checkAISystem()` uses `fetch(ML_BACKEND_URL/health)`; need to confirm endpoint returns 200 & CORS accessible.
 	- Possible mismatch: backend may expose `/api/healthz` or different path; hardcoded `/health` causing false offline.
 	- Silent failure path sets offline without logging; add console trace later.
 	- Self-test now: run in DevTools `fetch('http://localhost:9201/health').then(r=>console.log(r.status)).catch(e=>console.error(e))`.
 	- If status not 200 or blocked, capture response headers & adjust endpoint during fix phase.
- [ ] MONITOR LINKS NOT CLICKABLE (Prometheus / Jaeger / Qdrant icons unresponsive)
 	- User click yields no new tab/window; `onclick="window.open(url,'_blank')"` present.
 	- Possible VS Code Simple Browser popup restriction or overlay intercepting clicks (z-index layer over `.widget-icon`).
 	- Check for covering element: DevTools → `document.elementFromPoint(x,y)` over icon center.
 	- Verify pointer events: `getComputedStyle(el).pointerEvents` should be `auto`.
 	- Self-test: Run `window.open('http://localhost:9090','_blank')` manually; if blocked, need in-app navigation fallback.
 	- Status dots remain in `checking` state (e.g., `#prometheus-dot`, `#jaeger-dot`); confirm fetch logic sets class to `online`/`offline`.
 	- Add console trace later in `checkMonitoringTools()` for each endpoint result.
- [ ] NO AUDIO ACCESS (Microphone permission denied)
 	- `toggleSpeechRecognition()` throws permission error → inline chat message shows ❌ Microphone access denied.
 	- Likely VS Code Simple Browser sandbox denies `getUserMedia` until explicit user grant (or unsupported context).
 	- Need graceful detection: feature check `navigator.mediaDevices && MediaRecorder` and permissions API.
 	- Enhance error handling: differentiate NotAllowedError vs NotFoundError vs SecurityError.
 	- Provide UI fallback: disable mic button, show tooltip "Microphone unavailable" and instructions.
 	- Self-test: DevTools `navigator.mediaDevices.getUserMedia({audio:true}).then(()=>console.log('ok')).catch(e=>console.log(e.name,e.message))`.
 	- Add logging + badge state (e.g., add small status near chat input) when audio service unreachable.

## Styling/Specific Observations

- Repeated universal `* { margin:0; padding:0; box-sizing:border-box; }` blocks increase CSS cascade noise.
- `.widget-panel.visible` duplicates `display: block;`.
- Potential overuse of multiple `max-width` declarations; verify single source of truth.
- Consider normalizing vertical rhythm (consistent 16px / 20px spacing scale).

*(Waiting for user input – say "IM DONE" to proceed to fix phase)*
