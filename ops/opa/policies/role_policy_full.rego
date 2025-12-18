package mcp.authz

default allow = false

# action call: {"action":"call_tool","roles":["..."], "tool_required":["R1","R2"], "actor":"agent-x","risk":0.3}

allow {
  input.action == "call_tool"
  not forbidden_role_prefix(input.roles)
  some r
  r := input.roles[_]
  input.tool_required[_] == r
}

forbidden_role_prefix(roles) {
  some i
  p := input.forbidden_prefixes[_]
  roles[i] == rp
  startswith(lower(rp), lower(p))
}
