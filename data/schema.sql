-- SQLite Database Schema for KlipHowl Marketing & Prospecting
-- Path: data/marketing.db

PRAGMA foreign_keys = ON;

-- Drop previous view/tables if migrating in dev
DROP TABLE IF EXISTS interaction_logs;
DROP TABLE IF EXISTS outreach_emails;
DROP TABLE IF EXISTS campaigns;
DROP TABLE IF EXISTS videos;
DROP VIEW IF EXISTS channels;
DROP TABLE IF EXISTS channels;
DROP TABLE IF EXISTS prospects;

-- 1. Prospects / Channels Table
CREATE TABLE IF NOT EXISTS prospects (
    id TEXT PRIMARY KEY,                       -- Unique identifier: channel ID (UC...) or handle slug (yt:@caleb, x:brymstudio)
    title TEXT NOT NULL,                       -- Display name or Channel title
    handle TEXT,                               -- Handle e.g. @calebwritescode or @brymstudio
    custom_url TEXT,                           -- Full YouTube or X URL
    sample_video_url TEXT,                     -- Specific YouTube video URL found during research
    prospect_type TEXT DEFAULT 'youtuber',     -- 'youtuber', 'creator', 'video_editor', 'business_agency', 'other'
    size_tier TEXT,                            -- 'Big (20m subs)', '124k subs', 'Small', etc.
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
    match_level TEXT DEFAULT 'medium',         -- 'low', 'medium', 'high', 'very_high'
    status TEXT DEFAULT 'discovered',          -- 'discovered', 'qualified', 'disqualified', 'in_outreach', 'responded', 'customer'
    outreached INTEGER DEFAULT 0,              -- 0 = No, 1 = Yes
    outreach_date TIMESTAMP,
    response_status TEXT DEFAULT 'none',       -- 'none', 'interested', 'not_interested', 'ghosted'
    signed_up INTEGER DEFAULT 0,               -- 0 = No, 1 = Yes
    free_credits_given INTEGER DEFAULT 0,      -- Number of complimentary credits
    raw_notes TEXT,                            -- Any manual notes from research
    qualification_notes TEXT,                  -- Reason for acceptance/rejection
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Backwards-compatible view so any query referencing 'channels' continues to work seamlessly
CREATE VIEW IF NOT EXISTS channels AS 
SELECT 
    id AS channel_id,
    title,
    handle,
    custom_url,
    subscriber_count,
    video_count,
    view_count,
    country,
    description,
    primary_email,
    email_source,
    twitter_url,
    github_url,
    website_url,
    niche_category,
    animation_style_notes,
    status,
    qualification_notes,
    created_at,
    updated_at
FROM prospects;

-- 2. Videos Table (Context & video references for personalization)
CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,                 -- YouTube Video ID
    prospect_id TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMP,
    view_count INTEGER DEFAULT 0,
    description TEXT,
    visual_topic_concept TEXT,                 -- e.g. "Explains Redis Pub/Sub with box diagrams"
    sample_clip_idea TEXT,                     -- Idea for what KlipHowl could animate for them
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prospect_id) REFERENCES prospects (id) ON DELETE CASCADE
);

-- 3. Outreach Campaigns Table
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,              -- e.g. 'camp_tech_explainers_wave1'
    name TEXT NOT NULL,
    description TEXT,
    target_niche TEXT,
    status TEXT DEFAULT 'active',              -- 'draft', 'active', 'completed', 'paused'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Outreach Emails Table (Drafts and Sent Messages)
CREATE TABLE IF NOT EXISTS outreach_emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id TEXT NOT NULL,
    campaign_id TEXT,
    recipient_email TEXT NOT NULL,
    subject_line TEXT NOT NULL,
    body_markdown TEXT NOT NULL,
    referenced_video_id TEXT,
    personalized_hook TEXT,
    call_to_action TEXT,
    status TEXT DEFAULT 'draft',               -- 'draft', 'ready_for_review', 'approved', 'sent', 'replied', 'bounced', 'opted_out'
    draft_file_path TEXT,                      -- Path to local markdown draft: 'outreach/drafts/caleb_writes_code.md'
    sent_at TIMESTAMP,
    replied_at TIMESTAMP,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prospect_id) REFERENCES prospects (id) ON DELETE CASCADE,
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
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_prospects_match ON prospects(match_level);
CREATE INDEX IF NOT EXISTS idx_prospects_email ON prospects(primary_email);
CREATE INDEX IF NOT EXISTS idx_emails_status ON outreach_emails(status);
CREATE INDEX IF NOT EXISTS idx_videos_prospect ON videos(prospect_id);
