"""
Aura IA Database Schema

SQL schema for PostgreSQL 16. Covers:
- Conversations and messages
- Model rankings with ELO
- Debate history and rounds
- Learning events

Version: 1.0.0
"""

SCHEMA_VERSION = "1.0.0"

SCHEMA_SQL = """
-- =============================================================================
-- AURA IA DATABASE SCHEMA v1.0.0
-- PostgreSQL 16
-- =============================================================================

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version VARCHAR(20) PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT NOW(),
    description TEXT
);

-- =============================================================================
-- CONVERSATIONS & MESSAGES
-- =============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    mode VARCHAR(20) NOT NULL,  -- chat, concierge, mcp_command, debug, debate
    model_used VARCHAR(50),
    title VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_mode ON conversations(mode);
CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- user, assistant, system
    content TEXT NOT NULL,
    model_used VARCHAR(50),
    tokens_used INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);

-- =============================================================================
-- MODEL RANKINGS (ELO SYSTEM)
-- =============================================================================

CREATE TABLE IF NOT EXISTS model_rankings (
    model_name VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    elo_rating INTEGER DEFAULT 1500,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    total_debates INTEGER DEFAULT 0,
    current_streak INTEGER DEFAULT 0,  -- positive = wins, negative = losses
    best_streak INTEGER DEFAULT 0,
    specialty VARCHAR(50),  -- reasoning, coding, tool_calling
    ram_gb FLOAT DEFAULT 4.0,
    context_window INTEGER DEFAULT 4096,
    last_debate_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- =============================================================================
-- DEBATES
-- =============================================================================

CREATE TABLE IF NOT EXISTS debates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT NOT NULL,
    topic_category VARCHAR(50),  -- reasoning, coding, philosophy, strategy
    model_a VARCHAR(50) NOT NULL REFERENCES model_rankings(model_name),
    model_b VARCHAR(50) NOT NULL REFERENCES model_rankings(model_name),
    judge_model VARCHAR(50),
    winner VARCHAR(50) REFERENCES model_rankings(model_name),  -- NULL = draw
    elo_change_a INTEGER DEFAULT 0,
    elo_change_b INTEGER DEFAULT 0,
    elo_before_a INTEGER,
    elo_before_b INTEGER,
    score_a FLOAT,
    score_b FLOAT,
    verdict TEXT,
    scheduled_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'pending',  -- pending, running, completed, cancelled
    total_rounds INTEGER DEFAULT 3,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_debates_status ON debates(status);
CREATE INDEX IF NOT EXISTS idx_debates_completed ON debates(completed_at DESC);
CREATE INDEX IF NOT EXISTS idx_debates_model_a ON debates(model_a);
CREATE INDEX IF NOT EXISTS idx_debates_model_b ON debates(model_b);

CREATE TABLE IF NOT EXISTS debate_rounds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    debate_id UUID NOT NULL REFERENCES debates(id) ON DELETE CASCADE,
    round_number INTEGER NOT NULL,
    round_type VARCHAR(20) NOT NULL,  -- opening, rebuttal, closing
    model_name VARCHAR(50) NOT NULL REFERENCES model_rankings(model_name),
    argument TEXT NOT NULL,
    score FLOAT,
    tokens_used INTEGER,
    latency_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_debate_rounds_debate ON debate_rounds(debate_id);
CREATE INDEX IF NOT EXISTS idx_debate_rounds_model ON debate_rounds(model_name);

-- =============================================================================
-- LEARNING EVENTS
-- =============================================================================

CREATE TABLE IF NOT EXISTS learning_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,  -- debate_outcome, user_feedback, prediction_result
    model_name VARCHAR(50),
    context TEXT,
    outcome TEXT,
    feedback_score FLOAT,  -- -1.0 to 1.0
    applied BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_learning_events_type ON learning_events(event_type);
CREATE INDEX IF NOT EXISTS idx_learning_events_model ON learning_events(model_name);
CREATE INDEX IF NOT EXISTS idx_learning_events_created ON learning_events(created_at DESC);

-- =============================================================================
-- ROUTING HISTORY
-- =============================================================================

CREATE TABLE IF NOT EXISTS routing_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_preview VARCHAR(200),
    detected_mode VARCHAR(20) NOT NULL,
    selected_model VARCHAR(50) NOT NULL,
    confidence FLOAT,
    reasoning TEXT,
    keywords TEXT[],
    is_fallback BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_routing_history_mode ON routing_history(detected_mode);
CREATE INDEX IF NOT EXISTS idx_routing_history_model ON routing_history(selected_model);
CREATE INDEX IF NOT EXISTS idx_routing_history_created ON routing_history(created_at DESC);

-- =============================================================================
-- MEDIA DOWNLOADS (Recommendation System Phase 1)
-- =============================================================================

CREATE TABLE IF NOT EXISTS media_downloads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    media_type VARCHAR(20) NOT NULL,  -- movie, series, anime
    tmdb_id INTEGER,
    tvdb_id INTEGER,
    year INTEGER,
    genres TEXT[],  -- array of genres
    rating FLOAT,
    overview TEXT,
    poster_url TEXT,
    requested_by VARCHAR(50) DEFAULT 'dashboard',
    source VARCHAR(20) DEFAULT 'mcp',  -- mcp, sonarr, radarr, manual
    added_to_library BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_media_downloads_type ON media_downloads(media_type);
CREATE INDEX IF NOT EXISTS idx_media_downloads_genres ON media_downloads USING GIN(genres);
CREATE INDEX IF NOT EXISTS idx_media_downloads_created ON media_downloads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_media_downloads_tmdb ON media_downloads(tmdb_id);

-- =============================================================================
-- INITIAL DATA
-- =============================================================================

-- Insert default model rankings
INSERT INTO model_rankings (model_name, display_name, elo_rating, specialty, ram_gb, context_window)
VALUES 
    ('phi3.5:3.8b', 'Phi-3.5 Mini', 1500, 'quick_tasks', 3.0, 4096),
    ('llama3.1:8b', 'Llama 3.1 8B', 1500, 'reasoning', 5.0, 128000),
    ('qwen2.5-coder:7b', 'Qwen 2.5 Coder', 1500, 'coding', 5.0, 32768),
    ('deepseek-r1:8b', 'DeepSeek R1 8B', 1500, 'reasoning', 5.0, 65536)
ON CONFLICT (model_name) DO NOTHING;

-- Record schema version
INSERT INTO schema_version (version, description)
VALUES ('1.0.0', 'Initial schema: conversations, messages, model_rankings, debates, learning_events, routing_history')
ON CONFLICT (version) DO NOTHING;

INSERT INTO schema_version (version, description)
VALUES ('1.1.0', 'Added media_downloads table for recommendation system')
ON CONFLICT (version) DO NOTHING;
"""
