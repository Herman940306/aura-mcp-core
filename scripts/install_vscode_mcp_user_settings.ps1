param(
  [string]$ServerUrl = "http://localhost:9200",
  [string]$Profile = "Code - Insiders"
)

Write-Host "Installing Aura IA MCP server config into VS Code user settings ($Profile)..." -ForegroundColor Cyan

$settingsDir = Join-Path $env:APPDATA "$Profile\User"
$settingsPath = Join-Path $settingsDir "settings.json"

if (!(Test-Path $settingsDir)) { New-Item -ItemType Directory -Path $settingsDir -Force | Out-Null }

# Load existing settings or initialize
if (Test-Path $settingsPath) {
  try { $settings = Get-Content $settingsPath -Raw | ConvertFrom-Json -ErrorAction Stop }
  catch { $settings = @{} }
}
else {
  $settings = @{}
}

if (-not $settings.mcpServers) { $settings | Add-Member -NotePropertyName mcpServers -NotePropertyValue (@{}) }

$entry = @{
  transport   = @{ type = 'sse'; url = $ServerUrl }
  autoApprove = @(
    'ide_agents_health',
    'ide_agents_catalog',
    'ide_agents_resource',
    'ide_agents_prompt',
    'ide_agents_github_repos',
    'ide_agents_github_rank_repos',
    'ide_agents_github_rank_all'
  )
}

$settings.mcpServers.'aura-ia-mcp' = $entry

# Backup then write
if (Test-Path $settingsPath) { Copy-Item $settingsPath "$settingsPath.bak" -Force }
$json = $settings | ConvertTo-Json -Depth 12
Set-Content -Path $settingsPath -Value $json -Encoding UTF8

Write-Host "Updated: $settingsPath" -ForegroundColor Green
Write-Host "VS Code Insiders will now auto-connect to Aura IA MCP at $ServerUrl (SSE)." -ForegroundColor Green
