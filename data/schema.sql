-- SQLite Database Schema for KlipHowl Marketing & Prospecting
-- Path: data/marketing.db

PRAGMA foreign_keys = ON;

-- 1. Channels / Prospects Table
CREATE TABLE IF NOT EXISTS channels (
    channel_id TEXT PRIMARY KEY,               -- YouTube Channel ID (e.g. UC_x5XG1OV2P6uZZ5FSM9Ttw)
    title TEXT NOT NULL,                       -- Channel Display Name
    handle TEXT,                               -- e.g. @bytebytego
    custom_url TEXT,                           -- Full YouTube URL
    subscriber_count INTEGER DEFAULT 0,
    video_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    country TEXT,
    description TEXT,
    primary_email TEXT,                        -- Target business email address
    email_source TEXT,                         -- 'yt_description', 'about_page', 'github', 'twitter', 'website', 'manual'
    twitter_url TEXT,
    github_url TEXT,
    website_url TEXT,
    niche_category TEXT,                       -- 'system_design', 'devops', 'web_dev', 'algorithms', etc.
    animation_style_notes TEXT,                -- 'excalidraw sketches', 'manim animations', 'slides', etc.
    status TEXT DEFAULT 'discovered',          -- 'discovered', 'qualified', 'disqualified', 'in_outreach', 'responded', 'customer'
    qualification_notes TEXT,                  -- Reason for acceptance/rejection
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Videos Table (Context & video references for personalization)
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,                 -- YouTube Video ID
    channel_id TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMP,
    view_count INTEGER DEFAULT 0,
    description TEXT,
    visual_topic_concept TEXT,                 -- e.g. "Explains Redis Pub/Sub with box diagrams"
    sample_clip_idea TEXT,                     -- Idea for what KlipHowl could animate for them
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels (channel_id) ON DELETE CASCADE
);

-- 3. Outreach Campaigns Table
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,              -- e.g. 'camp_system_design_nov2026'
    name TEXT NOT NULL,
    description TEXT,
    target_niche TEXT,
    status TEXT DEFAULT 'active',              -- 'draft', 'active', 'completed', 'paused'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Outreach Emails Table (Drafts and Sent Messages)
CREATE TABLE IF NOT EXISTS outreach_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id TEXT NOT NULL,
    campaign_id TEXT,
    recipient_email TEXT NOT NULL,
    subject_line TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    referenced_video_id TEXT,
    personalized_hook TEXT,
    call_to_action TEXT,
    status TEXT DEFAULT 'draft',               -- 'draft', 'ready_for_review', 'approved', 'sent', 'replied', 'bounced', 'opted_out'
    draft_file_path TEXT,                      -- Path to local markdown draft: 'outreach/drafts/bytebytego.md'
    sent_at TIMESTAMP,
    replied_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (channel_id) REFERENCES channels (channel_id) ON DELETE CASCADE,
    FOREIGN KEY (campaign_id) REFERENCES campaigns (campaign_id) ON DELETE SET NULL,
    FOREIGN KEY (referenced_video_id) REFERENCES videos (video_id) ON DELETE SET NULL
);

-- 5. Interaction / Activity Logs
CREATE TABLE IF NOT EXISTS interaction_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    outreach_email_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,                  -- 'draft_created', 'edited', 'sent', 'reply_received', 'follow_up_scheduled'
    details TEXT,
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (outreach_email_id) REFERENCES outreach_emails (id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_channels_status ON channels(status);
CREATE INDEX IF NOT EXISTS idx_channels_email ON channels(primary_email);
CREATE INDEX IF NOT EXISTS idx_emails_status ON outreach_emails(status);
CREATE INDEX IF NOT EXISTS idx_videos_channel ON videos(channel_id);
