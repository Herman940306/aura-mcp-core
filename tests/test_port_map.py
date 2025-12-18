from aura_ia_mcp.core.config import get_settings


def test_port_constants_present():
    s = get_settings()
    assert s.PORT_ROOT == 9200
    assert s.PORT_LLM_PROXY == 9201
    assert s.PORT_EMBEDDING == 9202
    assert s.PORT_RAG == 9203
    assert s.PORT_ROLE_ENGINE == 9204
    assert s.PORT_RESERVED_1 == 9205
    assert s.PORT_RESERVED_2 == 9206
