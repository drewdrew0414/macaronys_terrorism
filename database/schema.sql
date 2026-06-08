-- Macaronys Assignment Backend PostgreSQL schema
-- Designed from mysql.sql, adapted for PostgreSQL and the FastAPI backend.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS school_classes (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    class_key VARCHAR(20) NOT NULL UNIQUE,
    grade INTEGER CHECK (grade IS NULL OR (grade >= 1 AND grade <= 12)),
    room INTEGER CHECK (room IS NULL OR (room >= 1 AND room <= 99)),
    label VARCHAR(60) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    name VARCHAR(40) NOT NULL,
    role VARCHAR(16) NOT NULL DEFAULT 'student' CHECK (role IN ('student', 'teacher')),
    is_graduated BOOLEAN NOT NULL DEFAULT FALSE,
    birth_date DATE NOT NULL,
    class_id TEXT REFERENCES school_classes(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    source_type VARCHAR(32) NOT NULL CHECK (
        source_type IN ('chat', 'txt', 'pdf', 'audio', 'discord')
    ),
    title VARCHAR(255) NOT NULL,
    storage_path TEXT,
    mime_type VARCHAR(120),
    file_size INTEGER CHECK (file_size IS NULL OR file_size >= 0),
    raw_text TEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'processing', 'done', 'failed')
    ),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assignment_candidates (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    subject VARCHAR(120),
    due_at TIMESTAMPTZ,
    submit_method VARCHAR(255),
    source_quote TEXT,
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (
        confidence >= 0 AND confidence <= 1
    ),
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'accepted', 'rejected', 'merged')
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assignments (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    class_id TEXT REFERENCES school_classes(id) ON DELETE SET NULL,
    creator_id TEXT REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    subject VARCHAR(120),
    due_at TIMESTAMPTZ NOT NULL,
    context TEXT,
    submit_method VARCHAR(255),
    submit_link TEXT,
    reference_link TEXT,
    is_contest BOOLEAN NOT NULL DEFAULT FALSE,
    is_exam BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    is_ended BOOLEAN NOT NULL DEFAULT FALSE,
    priority VARCHAR(32) NOT NULL DEFAULT 'normal',
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'in_progress', 'done', 'paused')
    ),
    source_id TEXT REFERENCES sources(id) ON DELETE SET NULL,
    source_quote TEXT,
    notification_scope VARCHAR(40),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE assignments ADD COLUMN IF NOT EXISTS class_id TEXT REFERENCES school_classes(id) ON DELETE SET NULL;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS creator_id TEXT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS context TEXT;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS submit_link TEXT;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS reference_link TEXT;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS is_contest BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS is_exam BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS is_ended BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE assignments ADD COLUMN IF NOT EXISTS end_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS ai_jobs (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    job_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'queued' CHECK (
        status IN ('queued', 'claimed', 'running', 'completed', 'failed')
    ),
    prompt TEXT NOT NULL,
    result_text TEXT,
    error_message TEXT,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    locked_by VARCHAR(120),
    locked_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notification_rules (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    offset_minutes INTEGER NOT NULL CHECK (offset_minutes >= 0),
    channel VARCHAR(32) NOT NULL DEFAULT 'app' CHECK (channel IN ('app', 'discord')),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    quiet_start TIME,
    quiet_end TIME,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    assignment_id TEXT NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL CHECK (channel IN ('app', 'discord')),
    scheduled_at TIMESTAMPTZ NOT NULL,
    sent_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'sending', 'sent', 'failed', 'skipped')
    ),
    message TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS discord_guilds (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    guild_id TEXT NOT NULL UNIQUE,
    default_channel_id TEXT,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS discord_user_links (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    guild_id TEXT NOT NULL,
    discord_user_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    display_name VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, discord_user_id),
    UNIQUE (guild_id, user_id)
);

CREATE TABLE IF NOT EXISTS discord_channel_mappings (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    guild_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    class_id TEXT NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    channel_key VARCHAR(40),
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, channel_id)
);

CREATE TABLE IF NOT EXISTS discord_moderation_logs (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    guild_id TEXT NOT NULL,
    channel_id TEXT,
    actor_discord_user_id TEXT NOT NULL,
    action VARCHAR(64) NOT NULL,
    target TEXT,
    details TEXT,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS clubs (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    guild_id TEXT NOT NULL,
    name VARCHAR(80) NOT NULL,
    description TEXT,
    owner_discord_user_id TEXT NOT NULL,
    category_id TEXT,
    text_channel_id TEXT,
    voice_channel_id TEXT,
    admin_role_id TEXT,
    member_role_id TEXT,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, name)
);

CREATE TABLE IF NOT EXISTS club_members (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    club_id TEXT NOT NULL REFERENCES clubs(id) ON DELETE CASCADE,
    discord_user_id TEXT NOT NULL,
    display_name VARCHAR(120),
    member_role VARCHAR(16) NOT NULL DEFAULT 'member' CHECK (member_role IN ('admin', 'member')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (club_id, discord_user_id)
);

CREATE TABLE IF NOT EXISTS voice_rooms (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    guild_id TEXT NOT NULL,
    channel_id TEXT NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    owner_discord_user_id TEXT NOT NULL,
    allowed_user_ids TEXT,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS command_logs (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    guild_id TEXT,
    channel_id TEXT,
    actor_discord_user_id TEXT NOT NULL,
    actor_name VARCHAR(120),
    command VARCHAR(64) NOT NULL,
    options TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'failure')),
    detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clubs_guild_id ON clubs(guild_id);
CREATE INDEX IF NOT EXISTS idx_club_members_club_id ON club_members(club_id);
CREATE INDEX IF NOT EXISTS idx_voice_rooms_channel_id ON voice_rooms(channel_id);
CREATE INDEX IF NOT EXISTS idx_command_logs_created_at ON command_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_command_logs_actor ON command_logs(actor_discord_user_id);

DROP TRIGGER IF EXISTS trg_clubs_updated_at ON clubs;
CREATE TRIGGER trg_clubs_updated_at
BEFORE UPDATE ON clubs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS team_projects (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    maker_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assignment_id TEXT REFERENCES assignments(id) ON DELETE SET NULL,
    class_id TEXT REFERENCES school_classes(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    context TEXT NOT NULL,
    max_members INTEGER NOT NULL CHECK (max_members > 0),
    status VARCHAR(32) NOT NULL DEFAULT 'recruiting' CHECK (
        status IN ('recruiting', 'in_progress', 'completed', 'cancelled')
    ),
    text_channel_id VARCHAR(120),
    voice_channel_id VARCHAR(120),
    team_role_id VARCHAR(120),
    team_category_id VARCHAR(120),
    recruitment_message_id VARCHAR(120),
    notification_scope VARCHAR(40),
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS team_project_members (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    project_id TEXT NOT NULL REFERENCES team_projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(40),
    status VARCHAR(32) NOT NULL DEFAULT 'joined' CHECK (
        status IN ('joined', 'cancelled', 'removed')
    ),
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS peer_reviews (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    project_id TEXT NOT NULL REFERENCES team_projects(id) ON DELETE CASCADE,
    target_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    writer_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
    reason TEXT,
    position VARCHAR(40) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (target_id <> writer_id),
    UNIQUE (project_id, target_id, writer_id)
);

CREATE INDEX IF NOT EXISTS idx_school_classes_key ON school_classes(class_key);
CREATE INDEX IF NOT EXISTS idx_users_class_id ON users(class_id);
CREATE INDEX IF NOT EXISTS idx_sources_created_at ON sources(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_assignment_candidates_source_id ON assignment_candidates(source_id);
CREATE INDEX IF NOT EXISTS idx_assignment_candidates_status ON assignment_candidates(status);
CREATE INDEX IF NOT EXISTS idx_assignments_class_id ON assignments(class_id);
CREATE INDEX IF NOT EXISTS idx_assignments_creator_id ON assignments(creator_id);
CREATE INDEX IF NOT EXISTS idx_assignments_due_at ON assignments(due_at);
CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status);
CREATE INDEX IF NOT EXISTS idx_ai_jobs_status_created_at ON ai_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_ai_jobs_source_id ON ai_jobs(source_id);
CREATE INDEX IF NOT EXISTS idx_notifications_schedule ON notifications(status, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_discord_user_links_user_id ON discord_user_links(user_id);
CREATE INDEX IF NOT EXISTS idx_discord_channel_mappings_class_id ON discord_channel_mappings(class_id);
CREATE INDEX IF NOT EXISTS idx_discord_moderation_logs_created_at ON discord_moderation_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_team_projects_status ON team_projects(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_team_project_members_project ON team_project_members(project_id, status);
CREATE INDEX IF NOT EXISTS idx_peer_reviews_project ON peer_reviews(project_id);
CREATE INDEX IF NOT EXISTS idx_peer_reviews_target ON peer_reviews(target_id);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_assignments_updated_at ON assignments;
CREATE TRIGGER trg_assignments_updated_at
BEFORE UPDATE ON assignments
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_notification_rules_updated_at ON notification_rules;
CREATE TRIGGER trg_notification_rules_updated_at
BEFORE UPDATE ON notification_rules
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_discord_user_links_updated_at ON discord_user_links;
CREATE TRIGGER trg_discord_user_links_updated_at
BEFORE UPDATE ON discord_user_links
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_discord_channel_mappings_updated_at ON discord_channel_mappings;
CREATE TRIGGER trg_discord_channel_mappings_updated_at
BEFORE UPDATE ON discord_channel_mappings
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_team_projects_updated_at ON team_projects;
CREATE TRIGGER trg_team_projects_updated_at
BEFORE UPDATE ON team_projects
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS team_join_requests (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    project_id TEXT NOT NULL REFERENCES team_projects(id) ON DELETE CASCADE,
    requester_discord_user_id TEXT NOT NULL,
    requester_display_name VARCHAR(120),
    reason TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer_discord_user_id TEXT,
    approval_message_id VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (project_id, requester_discord_user_id)
);
CREATE INDEX IF NOT EXISTS idx_join_requests_project ON team_join_requests(project_id, status);

CREATE TABLE IF NOT EXISTS registrations (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    guild_id TEXT NOT NULL,
    discord_user_id TEXT NOT NULL,
    display_name VARCHAR(120),
    name VARCHAR(40) NOT NULL,
    birth_date_str VARCHAR(20) NOT NULL,
    class_key VARCHAR(20) NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    reviewer_discord_user_id TEXT,
    approval_message_id VARCHAR(120),
    reject_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (guild_id, discord_user_id)
);

CREATE TABLE IF NOT EXISTS votes (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    guild_id TEXT NOT NULL,
    channel_id TEXT,
    creator_discord_user_id TEXT NOT NULL,
    question TEXT NOT NULL,
    is_anonymous BOOLEAN NOT NULL DEFAULT TRUE,
    ends_at TIMESTAMPTZ,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    message_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vote_choices (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
    label VARCHAR(80) NOT NULL,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS vote_responses (
    id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
    vote_id TEXT NOT NULL REFERENCES votes(id) ON DELETE CASCADE,
    choice_id TEXT NOT NULL REFERENCES vote_choices(id) ON DELETE CASCADE,
    discord_user_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (vote_id, discord_user_id)
);

CREATE INDEX IF NOT EXISTS idx_registrations_guild ON registrations(guild_id, status);
CREATE INDEX IF NOT EXISTS idx_votes_guild ON votes(guild_id, is_closed);
CREATE INDEX IF NOT EXISTS idx_vote_choices_vote ON vote_choices(vote_id);
CREATE INDEX IF NOT EXISTS idx_vote_responses_vote ON vote_responses(vote_id);
