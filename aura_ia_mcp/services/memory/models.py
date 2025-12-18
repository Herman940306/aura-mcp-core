"""
Aura IA Memory Database Models

SQLAlchemy ORM models for the persistent memory system.
Covers: Chat, Tasks, Learning, Media, Smart Home, Debates
"""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


# =============================================================================
# CORE INTERACTION TABLES
# =============================================================================


class ChatLog(Base):
    """All conversations across all chat modes."""

    __tablename__ = "chat_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(String(100), index=True)
    chat_mode = Column(
        String(20), nullable=False, index=True
    )  # concierge, chat, mcp_command, debug
    model_used = Column(String(50))
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text)
    tokens_used = Column(Integer)
    response_time_ms = Column(Integer)
    sentiment = Column(String(20))  # positive, neutral, negative
    topics = Column(JSONB)  # ['coding', 'entertainment', 'smart_home']
    context_retrieved = Column(Boolean, default=False)
    context_ids = Column(JSONB)  # IDs of context records used

    __table_args__ = (
        Index("idx_chat_user_time", "user_id", "timestamp"),
        Index("idx_chat_mode_time", "chat_mode", "timestamp"),
    )


class Task(Base):
    """Tasks, reminders, and scheduled items."""

    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    user_id = Column(String(100), index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    status = Column(
        String(20), default="pending", index=True
    )  # pending, in_progress, completed, cancelled
    priority = Column(
        String(10), default="medium"
    )  # low, medium, high, urgent
    due_date = Column(DateTime)
    completed_at = Column(DateTime)
    source = Column(String(20))  # user, ai_suggested, automation
    related_chat_id = Column(String(36), ForeignKey("chat_logs.id"))
    tags = Column(JSONB)
    recurrence = Column(JSONB)  # For recurring tasks

    __table_args__ = (Index("idx_task_status_due", "status", "due_date"),)


class ReasoningTrace(Base):
    """Model reasoning and decision logs for learning."""

    __tablename__ = "reasoning_traces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    model_id = Column(String(50), index=True)
    task_type = Column(String(50))  # recommendation, prediction, decision
    input_context = Column(Text)
    reasoning_steps = Column(JSONB)  # Step-by-step thinking
    conclusion = Column(Text)
    confidence = Column(Float)
    outcome_verified = Column(Boolean, default=False)
    actual_outcome = Column(Text)
    feedback = Column(Text)
    accuracy_score = Column(Float)  # Calculated after verification


class CodingSession(Base):
    """Development work tracking."""

    __tablename__ = "coding_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    user_id = Column(String(100), index=True)
    project_name = Column(String(200))
    language = Column(String(50))
    files_modified = Column(JSONB)
    errors_encountered = Column(JSONB)
    errors_resolved = Column(JSONB)
    code_snippets = Column(JSONB)
    ai_assists = Column(Integer, default=0)
    productivity_score = Column(Float)
    duration_minutes = Column(Integer)


class ToolCall(Base):
    """MCP tool usage tracking."""

    __tablename__ = "tool_calls"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    tool_name = Column(String(100), nullable=False, index=True)
    tool_category = Column(String(50))  # ml, github, rag, audio, etc.
    parameters = Column(JSONB)
    result_summary = Column(Text)
    success = Column(Boolean)
    error_message = Column(Text)
    execution_time_ms = Column(Integer)
    triggered_by = Column(String(20))  # user, automation, scheduled
    related_chat_id = Column(String(36), ForeignKey("chat_logs.id"))
    model_used = Column(String(50))

    __table_args__ = (Index("idx_tool_name_time", "tool_name", "timestamp"),)


# =============================================================================
# ENTERTAINMENT & MEDIA TABLES
# =============================================================================


class MediaWatchHistory(Base):
    """Movies, shows, and content watched."""

    __tablename__ = "media_watch_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(String(100), index=True)
    media_type = Column(
        String(20), nullable=False
    )  # movie, series, documentary, anime
    title = Column(String(500), nullable=False)
    tmdb_id = Column(Integer, index=True)
    imdb_id = Column(String(20))
    year = Column(Integer)
    genres = Column(JSONB)
    duration_minutes = Column(Integer)
    watched_duration_minutes = Column(Integer)
    completion_percent = Column(Float)
    rating_user = Column(Float)  # User's 1-10 rating
    rating_imdb = Column(Float)
    rating_predicted = Column(Float)  # AI's prediction before watching
    watch_context = Column(
        JSONB
    )  # {'time': 'evening', 'day': 'saturday', 'mood': 'relaxed'}
    device = Column(String(50))  # living_room_tv, bedroom, mobile
    with_users = Column(JSONB)  # ['user_a', 'user_b']

    __table_args__ = (Index("idx_media_user_time", "user_id", "timestamp"),)


class MediaPreference(Base):
    """Learned media preferences per user."""

    __tablename__ = "media_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), nullable=False, index=True)
    preference_type = Column(
        String(30), nullable=False
    )  # genre, actor, director, decade, mood
    preference_value = Column(String(200), nullable=False)
    affinity_score = Column(Float)  # -1.0 to 1.0 (hate to love)
    sample_size = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow)
    confidence = Column(Float)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "preference_type",
            "preference_value",
            name="uq_user_pref",
        ),
        Index("idx_pref_user_type", "user_id", "preference_type"),
    )


class MediaRecommendation(Base):
    """AI-generated recommendations and their outcomes."""

    __tablename__ = "media_recommendations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(100), index=True)
    media_type = Column(String(20))
    title = Column(String(500), nullable=False)
    tmdb_id = Column(Integer)
    reason = Column(Text)  # "Based on your love of Interstellar and Sci-Fi"
    confidence = Column(Float)
    status = Column(
        String(20), default="pending"
    )  # pending, accepted, rejected, watched
    user_feedback = Column(Text)
    prediction_accuracy = Column(Float)  # After watching


class DownloadQueue(Base):
    """Automated media downloads."""

    __tablename__ = "download_queue"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    created_at = Column(DateTime, default=datetime.utcnow)
    media_type = Column(String(20))
    title = Column(String(500), nullable=False)
    tmdb_id = Column(Integer)
    quality = Column(String(10), default="1080p")
    status = Column(
        String(20), default="queued", index=True
    )  # queued, downloading, completed, failed
    triggered_by = Column(String(30))  # user, ai_recommendation, new_release
    priority = Column(Integer, default=5)
    download_started = Column(DateTime)
    download_completed = Column(DateTime)
    file_path = Column(String(1000))
    file_size_mb = Column(Integer)


class MediaPattern(Base):
    """Viewing patterns by time/context."""

    __tablename__ = "media_patterns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), index=True)
    pattern_type = Column(
        String(30)
    )  # time_of_day, day_of_week, seasonal, mood
    pattern_key = Column(String(50))  # friday_evening, winter, stressed
    preferred_genres = Column(JSONB)
    preferred_duration = Column(String(20))  # short, medium, long
    avg_sessions_per_week = Column(Float)
    confidence = Column(Float)
    last_analyzed = Column(DateTime)


# =============================================================================
# SMART HOME & IoT TABLES
# =============================================================================


class DeviceRegistry(Base):
    """All smart home devices."""

    __tablename__ = "device_registry"

    device_id = Column(String(100), primary_key=True)
    device_name = Column(String(200), nullable=False)
    device_type = Column(
        String(50), nullable=False, index=True
    )  # light, thermostat, sensor, switch, camera
    location = Column(String(100), index=True)  # living_room, bedroom, kitchen
    manufacturer = Column(String(100))
    model = Column(String(100))
    protocol = Column(String(30))  # zigbee, zwave, wifi, matter
    capabilities = Column(
        JSONB
    )  # ['on_off', 'dimming', 'color', 'temperature']
    integration = Column(String(50))  # home_assistant, smartthings, native
    added_at = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime)
    is_online = Column(Boolean, default=True)

    states = relationship("DeviceState", back_populates="device")


class DeviceState(Base):
    """Historical device state changes (time series)."""

    __tablename__ = "device_states"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    device_id = Column(
        String(100),
        ForeignKey("device_registry.device_id"),
        nullable=False,
        index=True,
    )
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    state = Column(JSONB, nullable=False)  # {'on': true, 'brightness': 80}
    triggered_by = Column(String(30))  # user, automation, schedule, ai

    device = relationship("DeviceRegistry", back_populates="states")

    __table_args__ = (
        Index("idx_device_state_time", "device_id", "timestamp"),
    )


class AutomationRule(Base):
    """Learned and manual automation rules."""

    __tablename__ = "automation_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    trigger_type = Column(String(30))  # time, state, presence, ai_learned
    trigger_conditions = Column(JSONB)
    actions = Column(JSONB)
    is_ai_learned = Column(Boolean, default=False)
    confidence = Column(Float)
    times_executed = Column(Integer, default=0)
    last_executed = Column(DateTime)
    user_approved = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class EnergyUsage(Base):
    """Power consumption tracking."""

    __tablename__ = "energy_usage"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    device_id = Column(String(100), ForeignKey("device_registry.device_id"))
    power_watts = Column(Float)
    energy_kwh = Column(Float)
    cost_estimate = Column(Float)
    hour_of_day = Column(Integer)
    day_of_week = Column(Integer)


class PresencePattern(Base):
    """User presence/location patterns."""

    __tablename__ = "presence_patterns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), index=True)
    date = Column(DateTime, index=True)
    hour = Column(Integer)
    location = Column(String(30))  # home, away, work, unknown
    room = Column(String(50))  # If home, which room
    confidence = Column(Float)
    detection_method = Column(
        String(30)
    )  # phone_wifi, motion_sensor, calendar, manual


class ComfortPreference(Base):
    """Temperature, lighting preferences by context."""

    __tablename__ = "comfort_preferences"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), index=True)
    context = Column(String(30))  # sleeping, working, relaxing, exercising
    time_range = Column(String(20))  # morning, afternoon, evening, night
    season = Column(String(10))  # summer, winter, spring, fall
    preferred_temp_c = Column(Float)
    preferred_humidity = Column(Float)
    preferred_lighting = Column(String(20))  # bright, dim, warm, cool
    preferred_brightness = Column(Integer)
    sample_size = Column(Integer, default=0)
    confidence = Column(Float)
    last_updated = Column(DateTime)


# =============================================================================
# USER PROFILES & LEARNING TABLES
# =============================================================================


class UserProfile(Base):
    """Household member profiles."""

    __tablename__ = "user_profiles"

    user_id = Column(String(100), primary_key=True)
    name = Column(String(100), nullable=False)
    role = Column(String(20))  # admin, adult, child, guest
    created_at = Column(DateTime, default=datetime.utcnow)
    preferences = Column(JSONB)
    voice_profile_id = Column(String(100))
    face_profile_id = Column(String(100))
    wake_time_weekday = Column(String(10))  # "07:00"
    wake_time_weekend = Column(String(10))
    sleep_time_weekday = Column(String(10))
    sleep_time_weekend = Column(String(10))
    is_active = Column(Boolean, default=True)


class BehavioralPattern(Base):
    """Detected user behavior patterns."""

    __tablename__ = "behavioral_patterns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(100), index=True)
    pattern_name = Column(
        String(100)
    )  # morning_routine, bedtime_routine, movie_night
    detected_at = Column(DateTime, default=datetime.utcnow)
    pattern_definition = Column(JSONB)
    frequency = Column(String(20))  # daily, weekdays, weekends, weekly
    confidence = Column(Float)
    times_observed = Column(Integer, default=0)
    last_observed = Column(DateTime)
    suggested_automation_id = Column(String(36))
    is_verified = Column(Boolean, default=False)


class PredictionLog(Base):
    """AI predictions and their accuracy."""

    __tablename__ = "prediction_log"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    prediction_type = Column(
        String(50), index=True
    )  # movie_rating, presence, comfort, behavior
    prediction_target = Column(String(200))
    predicted_value = Column(Text)
    confidence = Column(Float)
    actual_value = Column(Text)
    accuracy = Column(Float)
    model_used = Column(String(50))
    features_used = Column(JSONB)
    verified_at = Column(DateTime)


class FeedbackLoop(Base):
    """User corrections to improve AI."""

    __tablename__ = "feedback_loop"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user_id = Column(String(100), index=True)
    feedback_type = Column(
        String(30)
    )  # correction, preference, approval, rejection
    context = Column(Text)
    original_action = Column(Text)
    user_correction = Column(Text)
    applied = Column(Boolean, default=False)
    impact_score = Column(Float)
    related_prediction_id = Column(String(36))


# =============================================================================
# DEBATE & LEARNING ENGINE TABLES
# =============================================================================


class ModelLeaderboard(Base):
    """Model performance tracking with ELO ratings."""

    __tablename__ = "model_leaderboard"

    model_id = Column(String(50), primary_key=True)
    model_name = Column(String(100), nullable=False)
    model_size = Column(String(20))  # small, medium, large
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    draws = Column(Integer, default=0)
    current_streak = Column(
        Integer, default=0
    )  # positive = wins, negative = losses
    best_win_streak = Column(Integer, default=0)
    elo_rating = Column(Integer, default=1200)
    total_debates = Column(Integer, default=0)
    specialty = Column(String(50))  # reasoning, coding, quick_tasks
    last_debate_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Stats by category
    wins_reasoning = Column(Integer, default=0)
    wins_coding = Column(Integer, default=0)
    wins_tool_calling = Column(Integer, default=0)


class DebateHistory(Base):
    """Full debate logs with outcomes."""

    __tablename__ = "debate_history"

    debate_id = Column(String(36), primary_key=True, default=generate_uuid)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    topic = Column(Text, nullable=False)
    topic_category = Column(
        String(50)
    )  # reasoning, coding, prediction, tool_calling
    topic_source = Column(
        String(50)
    )  # recent_chat, prediction_error, scheduled

    model_a_id = Column(
        String(50), ForeignKey("model_leaderboard.model_id"), nullable=False
    )
    model_b_id = Column(
        String(50), ForeignKey("model_leaderboard.model_id"), nullable=False
    )

    winner_id = Column(
        String(50), ForeignKey("model_leaderboard.model_id")
    )  # NULL = draw
    margin_of_victory = Column(Float)  # 0.0 to 1.0

    model_a_score = Column(Float)
    model_b_score = Column(Float)
    model_a_elo_before = Column(Integer)
    model_b_elo_before = Column(Integer)
    model_a_elo_change = Column(Integer)
    model_b_elo_change = Column(Integer)

    model_a_arguments = Column(JSONB)
    model_b_arguments = Column(JSONB)

    judge_reasoning = Column(Text)
    key_learnings = Column(JSONB)
    applied_to_system = Column(Boolean, default=False)
    debate_duration_seconds = Column(Integer)
    rounds = Column(Integer)


class MotivationTrigger(Base):
    """Motivational messages based on debate outcomes."""

    __tablename__ = "motivation_triggers"

    trigger_id = Column(String(36), primary_key=True, default=generate_uuid)
    model_id = Column(
        String(50), ForeignKey("model_leaderboard.model_id"), nullable=False
    )
    trigger_type = Column(
        String(30), nullable=False
    )  # streak, rivalry, comeback, milestone, underdog
    message = Column(Text, nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    used_in_prompt = Column(Boolean, default=False)
    related_debate_id = Column(
        String(36), ForeignKey("debate_history.debate_id")
    )

    # =============================================================================
    # INDEXES FOR COMMON QUERIES
    # =============================================================================

    # Additional indexes defined in __table_args__ above
    message = Column(Text, nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow)
    used_in_prompt = Column(Boolean, default=False)
    related_debate_id = Column(
        String(36), ForeignKey("debate_history.debate_id")
    )


# =============================================================================
# INDEXES FOR COMMON QUERIES
# =============================================================================

# Additional indexes defined in __table_args__ above
