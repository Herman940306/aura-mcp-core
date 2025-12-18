# Dashboard Fault Log - December 13, 2025

## Test Results Summary

### Backend API Tests (All PASS)

| Endpoint                              | Status  | Response                               |
| ------------------------------------- | ------- | -------------------------------------- |
| GET /healthz                          | ✅ PASS | `{"status":"live"}`                    |
| GET /readyz                           | ✅ PASS | `{"status":"ready","backend_ok":true}` |
| GET /v1/models/health                 | ✅ PASS | 5 models available                     |
| GET /v1/models/status                 | ✅ PASS | Mode mappings correct                  |
| GET /v1/dashboard/summary             | ✅ PASS | Returns data                           |
| GET /v1/debate/leaderboard            | ✅ PASS | 3 models with ELO                      |
| GET /api/governance/roles (9206)      | ✅ PASS | 9 roles returned                       |
| GET /api/governance/audit-logs (9206) | ✅ PASS | 50 events returned                     |
| POST /chat/send (9201)                | ✅ PASS | Backend accepts chat                   |

### Dashboard Frontend Issues (CRITICAL)

#### FAULT 1: Wrong Backend URL for Browser Access

- **File**: `dashboard/assets/app.js` line 6
- **Issue**: `ML_BACKEND_URL = 'http://localhost:9201'`
- **Problem**: Dashboard runs in browser, `localhost` refers to user's machine, not NAS
- **Fix**: Change to `http://192.168.1.134:9201`

#### FAULT 2: Chat Endpoint Mismatch

- **File**: `dashboard/assets/app.js` line 660
- **Issue**: Calls `${ML_BACKEND_URL}/chat/send`
- **Problem**: Chat should go through gateway at 9200, not ML backend at 9201
- **Fix**: Use `${API_URL}/v1/chat/smart` or keep ML backend but fix URL

#### FAULT 3: Health Check Uses localhost

- **File**: `dashboard/assets/app.js` line 323-330
- **Issue**: `checkAISystem()` fetches from `ML_BACKEND_URL` (localhost:9201)
- **Problem**: Browser can't reach localhost:9201 on NAS
- **Fix**: Use NAS IP address

#### FAULT 4: CORS Mode Prevents Status Detection

- **File**: `dashboard/assets/app.js` line 326
- **Issue**: `mode: 'no-cors'` prevents reading response
- **Problem**: Can't determine if backend is actually online
- **Fix**: Remove `no-cors` mode, backend should have CORS headers

## Fixes Applied

### ✅ FIXED: Backend URL Issues

- **File**: `dashboard/assets/app.js`
- **Fixed**: Changed `ML_BACKEND_URL` from `localhost:9201` to `192.168.1.134:9201`
- **Fixed**: Updated all monitoring endpoints to use NAS IP instead of localhost
- **Fixed**: Removed `no-cors` mode from health checks

### ✅ FIXED: JavaScript Errors

- **File**: `dashboard/assets/app.js`
- **Fixed**: Removed duplicate `const API_URL` declaration (line 1352)
- **Fixed**: Added missing `switchView(viewName)` function for navigation tabs

### 🔄 REMAINING: Chat Endpoint

- **Issue**: Chat still uses ML Backend `/chat/send` instead of Gateway `/v1/chat/smart`
- **Status**: Keeping current setup since ML Backend chat endpoint works

## Next Steps

1. Restart dashboard container: `sudo docker compose restart aura-ia-dashboard`
2. Clear browser cache and refresh dashboard
3. Test all functionality
