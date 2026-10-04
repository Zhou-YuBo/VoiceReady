CREATE TABLE project (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_uri TEXT NOT NULL,
    default_language TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE asset (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    asset_type TEXT NOT NULL CHECK (asset_type IN ('voice_audio', 'song_audio', 'model', 'other')),
    origin_type TEXT NOT NULL CHECK (origin_type IN ('source', 'derived', 'segment')),
    uri TEXT NOT NULL,
    display_name TEXT NOT NULL,
    sha256 TEXT,
    size_bytes INTEGER CHECK (size_bytes IS NULL OR size_bytes >= 0),
    duration_ms INTEGER CHECK (duration_ms IS NULL OR duration_ms >= 0),
    sample_rate INTEGER CHECK (sample_rate IS NULL OR sample_rate > 0),
    channels INTEGER CHECK (channels IS NULL OR channels > 0),
    language TEXT,
    speaker_id TEXT,
    is_readonly INTEGER NOT NULL DEFAULT 0 CHECK (is_readonly IN (0, 1)),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id, uri)
);

CREATE TABLE asset_relation (
    id TEXT PRIMARY KEY,
    parent_asset_id TEXT NOT NULL REFERENCES asset(id) ON DELETE RESTRICT,
    child_asset_id TEXT NOT NULL REFERENCES asset(id) ON DELETE RESTRICT,
    relation_type TEXT NOT NULL CHECK (
        relation_type IN (
            'derived_from', 'segment_of', 'separated_from',
            'denoised_from', 'resampled_from', 'normalized_from'
        )
    ),
    start_ms INTEGER CHECK (start_ms IS NULL OR start_ms >= 0),
    end_ms INTEGER CHECK (end_ms IS NULL OR end_ms >= 0),
    sequence_index INTEGER CHECK (sequence_index IS NULL OR sequence_index >= 0),
    parameters_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    CHECK (
        (start_ms IS NULL AND end_ms IS NULL)
        OR (start_ms IS NOT NULL AND end_ms IS NOT NULL AND end_ms > start_ms)
    ),
    CHECK (parent_asset_id <> child_asset_id),
    UNIQUE(parent_asset_id, child_asset_id, relation_type)
);

CREATE TABLE collection (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    purpose TEXT,
    language TEXT,
    speaker_id TEXT,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(project_id, name)
);

CREATE TABLE collection_asset (
    collection_id TEXT NOT NULL REFERENCES collection(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    included INTEGER NOT NULL DEFAULT 1 CHECK (included IN (0, 1)),
    inclusion_reason TEXT,
    exclusion_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(collection_id, asset_id)
);

CREATE TABLE text_source (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    source_type TEXT NOT NULL CHECK (source_type IN ('official', 'manual', 'external')),
    name TEXT NOT NULL,
    uri TEXT,
    content_sha256 TEXT,
    language TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE text_unit (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES text_source(id) ON DELETE CASCADE,
    sequence_index INTEGER NOT NULL CHECK (sequence_index >= 0),
    text TEXT NOT NULL,
    speaker_id TEXT,
    locator_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    UNIQUE(source_id, sequence_index)
);

CREATE TABLE speech_unit (
    id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    sequence_index INTEGER NOT NULL DEFAULT 0 CHECK (sequence_index >= 0),
    start_ms INTEGER CHECK (start_ms IS NULL OR start_ms >= 0),
    end_ms INTEGER CHECK (end_ms IS NULL OR end_ms >= 0),
    official_text TEXT,
    asr_text TEXT,
    final_text TEXT,
    official_text_unit_id TEXT REFERENCES text_unit(id) ON DELETE SET NULL,
    text_source_type TEXT CHECK (text_source_type IS NULL OR text_source_type IN ('official', 'manual', 'external')),
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK (
        review_status IN ('pending', 'ai_completed', 'human_approved', 'human_rejected', 'needs_revision')
    ),
    review_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (
        (start_ms IS NULL AND end_ms IS NULL)
        OR (start_ms IS NOT NULL AND end_ms IS NOT NULL AND end_ms > start_ms)
    ),
    UNIQUE(asset_id, sequence_index)
);

CREATE TABLE job (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    job_type TEXT NOT NULL CHECK (
        job_type IN (
            'import', 'probe', 'separate_vocals', 'denoise', 'dereverb',
            'resample', 'segment', 'asr', 'audio_analysis', 'export'
        )
    ),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    parameters_json TEXT NOT NULL DEFAULT '{}',
    error_message TEXT,
    log_uri TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);

CREATE TABLE job_asset (
    job_id TEXT NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    io_role TEXT NOT NULL CHECK (io_role IN ('input', 'output', 'reference')),
    sequence_index INTEGER NOT NULL DEFAULT 0 CHECK (sequence_index >= 0),
    PRIMARY KEY(job_id, asset_id, io_role)
);

CREATE TABLE review_task (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    review_type TEXT NOT NULL CHECK (
        review_type IN ('official_alignment', 'audio_quality', 'speaker_provenance', 'export_readiness')
    ),
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE review_item (
    id TEXT PRIMARY KEY,
    review_task_id TEXT NOT NULL REFERENCES review_task(id) ON DELETE CASCADE,
    asset_id TEXT NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    speech_unit_id TEXT REFERENCES speech_unit(id) ON DELETE CASCADE,
    ai_suggestion TEXT,
    human_decision TEXT CHECK (human_decision IS NULL OR human_decision IN ('approved', 'rejected', 'revise')),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'ai_completed', 'human_approved', 'human_rejected', 'needs_revision')
    ),
    reviewer TEXT,
    reviewed_at TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(review_task_id, speech_unit_id)
);

CREATE TABLE review_event (
    id TEXT PRIMARY KEY,
    review_item_id TEXT NOT NULL REFERENCES review_item(id) ON DELETE CASCADE,
    actor_kind TEXT NOT NULL CHECK (actor_kind IN ('ai', 'human', 'system')),
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX idx_asset_project ON asset(project_id);
CREATE INDEX idx_asset_relation_parent ON asset_relation(parent_asset_id);
CREATE INDEX idx_asset_relation_child ON asset_relation(child_asset_id);
CREATE INDEX idx_collection_asset_asset ON collection_asset(asset_id);
CREATE INDEX idx_text_unit_source ON text_unit(source_id, sequence_index);
CREATE INDEX idx_speech_unit_asset ON speech_unit(asset_id, sequence_index);
CREATE INDEX idx_job_project_status ON job(project_id, status);
CREATE INDEX idx_review_task_project_status ON review_task(project_id, status);
CREATE INDEX idx_review_item_task_status ON review_item(review_task_id, status);

CREATE TRIGGER asset_readonly_update
BEFORE UPDATE ON asset
WHEN OLD.is_readonly = 1
BEGIN
    SELECT RAISE(ABORT, 'source asset is read-only');
END;

CREATE TRIGGER segment_range_no_overlap_insert
BEFORE INSERT ON asset_relation
WHEN NEW.relation_type = 'segment_of'
 AND NEW.start_ms IS NOT NULL
 AND NEW.end_ms IS NOT NULL
 AND EXISTS (
    SELECT 1
    FROM asset_relation AS existing
    WHERE existing.relation_type = 'segment_of'
      AND existing.parent_asset_id = NEW.parent_asset_id
      AND existing.start_ms IS NOT NULL
      AND existing.end_ms IS NOT NULL
      AND NEW.start_ms < existing.end_ms
      AND existing.start_ms < NEW.end_ms
 )
BEGIN
    SELECT RAISE(ABORT, 'segment ranges overlap');
END;

CREATE TRIGGER segment_range_no_overlap_update
BEFORE UPDATE OF parent_asset_id, relation_type, start_ms, end_ms ON asset_relation
WHEN NEW.relation_type = 'segment_of'
 AND NEW.start_ms IS NOT NULL
 AND NEW.end_ms IS NOT NULL
 AND EXISTS (
    SELECT 1
    FROM asset_relation AS existing
    WHERE existing.id <> NEW.id
      AND existing.relation_type = 'segment_of'
      AND existing.parent_asset_id = NEW.parent_asset_id
      AND existing.start_ms IS NOT NULL
      AND existing.end_ms IS NOT NULL
      AND NEW.start_ms < existing.end_ms
      AND existing.start_ms < NEW.end_ms
 )
BEGIN
    SELECT RAISE(ABORT, 'segment ranges overlap');
END;
