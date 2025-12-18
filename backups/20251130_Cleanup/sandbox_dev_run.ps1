Param(
  [int]$Port = 9200
)
$env:AURA_SAFE_MODE = "true"
python -m uvicorn aura_ia_mcp.main:app --host 0.0.0.0 --port $Port --reload
