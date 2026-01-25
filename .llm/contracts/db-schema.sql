-- Database schema for agentic policy analytics platform
-- Designed for reproducibility, auditability, and multi-agent coordination

-- Runs: top-level analytics execution records
CREATE TABLE runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query TEXT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'queued',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  started_at TIMESTAMP WITH TIME ZONE,
  completed_at TIMESTAMP WITH TIME ZONE,
  error_message TEXT,
  metadata JSONB DEFAULT '{}'::jsonb
);

-- Events: ReAct events emitted by agents (thought, action, observation, decision)
CREATE TABLE events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  agent VARCHAR(32) NOT NULL,
  event_type VARCHAR(32) NOT NULL,
  content JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  sequence INT NOT NULL
);

CREATE INDEX idx_events_run_id ON events(run_id);
CREATE INDEX idx_events_created_at ON events(created_at);

-- Plans: coordinator's proposed execution plan (human-reviewable)
CREATE TABLE plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,
  coordinator_reasoning TEXT,
  proposed_sources TEXT[],
  proposed_metrics TEXT[],
  proposed_analysis JSONB,
  status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  reviewed_at TIMESTAMP WITH TIME ZONE,
  reviewed_by VARCHAR(255),
  review_notes TEXT
);

-- Datasets: normalized, cleaned datasets persisted during extraction
CREATE TABLE datasets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  source_name VARCHAR(255) NOT NULL,
  format VARCHAR(32),
  row_count INT,
  column_names TEXT[],
  schema_json JSONB,
  data_path VARCHAR(1024),
  fetch_timestamp TIMESTAMP WITH TIME ZONE,
  validation_errors JSONB,
  cleaning_log JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_datasets_run_id ON datasets(run_id);

-- Insights: structured findings from analytics agent
CREATE TABLE insights (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  finding TEXT NOT NULL,
  confidence FLOAT NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
  evidence JSONB,
  sources UUID[],
  charts JSONB,
  limitations TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_insights_run_id ON insights(run_id);
CREATE INDEX idx_insights_confidence ON insights(confidence DESC);

-- Reports: final exported artifacts
CREATE TABLE reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,
  title VARCHAR(255),
  content_markdown TEXT,
  content_json JSONB,
  export_format VARCHAR(32),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  exported_by VARCHAR(255)
);

-- LLM Calls: log for observability (optional, for debugging)
CREATE TABLE llm_calls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id UUID REFERENCES runs(id) ON DELETE SET NULL,
  agent VARCHAR(32),
  model VARCHAR(128),
  provider VARCHAR(32),
  prompt_tokens INT,
  completion_tokens INT,
  total_cost NUMERIC(10, 6),
  latency_ms INT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_llm_calls_run_id ON llm_calls(run_id);
CREATE INDEX idx_llm_calls_created_at ON llm_calls(created_at);
