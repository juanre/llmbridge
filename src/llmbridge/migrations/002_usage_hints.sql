-- LLM Service Usage Hints/Model Selection Schema
-- Adds support for recommending models based on use cases

-- =====================================================
-- MODEL USAGE HINTS
-- =====================================================

-- Table to store which models are best for specific use cases
CREATE TABLE llmbridge.model_usage_hints (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('anthropic', 'openai', 'google', 'ollama')),
    use_case VARCHAR(50) NOT NULL CHECK (use_case IN (
        'deepest_model',      -- Best for complex reasoning/intelligence
        'largest_context',    -- Model with largest context window
        'largest_output',     -- Model with largest output capacity
        'best_vision',        -- Best for vision/image understanding
        'cheapest_good'       -- Best price/performance ratio
    )),
    model_id INTEGER REFERENCES llmbridge.llm_models(id),
    model_name VARCHAR(100) NOT NULL,  -- Store model_name for quick reference
    reasoning TEXT,  -- Why this model was selected for this use case
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Each provider can only have one model per use case
    CONSTRAINT model_usage_hints_unique UNIQUE (provider, use_case)
);

-- =====================================================
-- INDEXES
-- =====================================================

CREATE INDEX idx_model_usage_hints_provider ON llmbridge.model_usage_hints(provider);
CREATE INDEX idx_model_usage_hints_use_case ON llmbridge.model_usage_hints(use_case);
CREATE INDEX idx_model_usage_hints_model_id ON llmbridge.model_usage_hints(model_id);

-- =====================================================
-- TRIGGERS
-- =====================================================

-- Auto-update triggers
CREATE TRIGGER model_usage_hints_updated_at_trigger
BEFORE UPDATE ON llmbridge.model_usage_hints
FOR EACH ROW EXECUTE FUNCTION llmbridge.update_updated_at();

-- =====================================================
-- FUNCTIONS
-- =====================================================

-- Get the best model for a use case from a specific provider
CREATE OR REPLACE FUNCTION llmbridge.get_model_for_use_case(
    p_provider VARCHAR(50),
    p_use_case VARCHAR(50)
) RETURNS TABLE (
    model_id INTEGER,
    model_name VARCHAR(100),
    display_name VARCHAR(255),
    description TEXT,
    reasoning TEXT,
    max_context INTEGER,
    max_output_tokens INTEGER,
    dollars_per_million_tokens_input NUMERIC(12, 6),
    dollars_per_million_tokens_output NUMERIC(12, 6)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        m.id as model_id,
        m.model_name,
        m.display_name,
        m.description,
        h.reasoning,
        m.max_context,
        m.max_output_tokens,
        m.dollars_per_million_tokens_input,
        m.dollars_per_million_tokens_output
    FROM llmbridge.model_usage_hints h
    JOIN llmbridge.llm_models m ON h.model_id = m.id
    WHERE h.provider = p_provider
        AND h.use_case = p_use_case
        AND m.inactive_from IS NULL;  -- Only return active models
END;
$$ LANGUAGE plpgsql;

-- Get all models recommended for a specific use case across all providers
CREATE OR REPLACE FUNCTION llmbridge.get_all_models_for_use_case(
    p_use_case VARCHAR(50)
) RETURNS TABLE (
    provider VARCHAR(50),
    model_id INTEGER,
    model_name VARCHAR(100),
    display_name VARCHAR(255),
    description TEXT,
    reasoning TEXT,
    max_context INTEGER,
    max_output_tokens INTEGER,
    dollars_per_million_tokens_input NUMERIC(12, 6),
    dollars_per_million_tokens_output NUMERIC(12, 6)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        h.provider,
        m.id as model_id,
        m.model_name,
        m.display_name,
        m.description,
        h.reasoning,
        m.max_context,
        m.max_output_tokens,
        m.dollars_per_million_tokens_input,
        m.dollars_per_million_tokens_output
    FROM llmbridge.model_usage_hints h
    JOIN llmbridge.llm_models m ON h.model_id = m.id
    WHERE h.use_case = p_use_case
        AND m.inactive_from IS NULL  -- Only return active models
    ORDER BY h.provider;
END;
$$ LANGUAGE plpgsql;

-- Get all usage hints for a specific provider
CREATE OR REPLACE FUNCTION llmbridge.get_provider_usage_hints(
    p_provider VARCHAR(50)
) RETURNS TABLE (
    use_case VARCHAR(50),
    model_id INTEGER,
    model_name VARCHAR(100),
    display_name VARCHAR(255),
    reasoning TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        h.use_case,
        m.id as model_id,
        m.model_name,
        m.display_name,
        h.reasoning
    FROM llmbridge.model_usage_hints h
    JOIN llmbridge.llm_models m ON h.model_id = m.id
    WHERE h.provider = p_provider
        AND m.inactive_from IS NULL  -- Only return active models
    ORDER BY h.use_case;
END;
$$ LANGUAGE plpgsql;

-- Refresh usage hints for a provider (called during model refresh)
CREATE OR REPLACE FUNCTION llmbridge.refresh_usage_hints(
    p_provider VARCHAR(50),
    p_hints JSONB
) RETURNS VOID AS $$
DECLARE
    v_use_case VARCHAR(50);
    v_model_name VARCHAR(100);
    v_reasoning TEXT;
    v_model_id INTEGER;
BEGIN
    -- Delete existing hints for this provider
    DELETE FROM llmbridge.model_usage_hints WHERE provider = p_provider;

    -- Insert new hints
    FOR v_use_case IN SELECT jsonb_object_keys(p_hints) LOOP
        v_model_name := p_hints->v_use_case->>'model_id';
        v_reasoning := p_hints->v_use_case->>'reasoning';

        -- Find the model ID
        SELECT id INTO v_model_id
        FROM llmbridge.llm_models
        WHERE provider = p_provider
            AND model_name = v_model_name
            AND inactive_from IS NULL
        LIMIT 1;

        IF v_model_id IS NOT NULL THEN
            INSERT INTO llmbridge.model_usage_hints (
                provider, use_case, model_id, model_name, reasoning
            ) VALUES (
                p_provider, v_use_case, v_model_id, v_model_name, v_reasoning
            );
        END IF;
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- VIEWS
-- =====================================================

-- View combining models with their usage hints
CREATE OR REPLACE VIEW llmbridge.models_with_usage_hints AS
SELECT
    m.*,
    ARRAY_AGG(
        DISTINCT jsonb_build_object(
            'use_case', h.use_case,
            'reasoning', h.reasoning
        )
    ) FILTER (WHERE h.use_case IS NOT NULL) as usage_hints
FROM llmbridge.llm_models m
LEFT JOIN llmbridge.model_usage_hints h ON m.id = h.model_id
WHERE m.inactive_from IS NULL
GROUP BY m.id;

-- =====================================================
-- COMMENTS
-- =====================================================

COMMENT ON TABLE llmbridge.model_usage_hints IS 'Stores which models are best suited for specific use cases';
COMMENT ON COLUMN llmbridge.model_usage_hints.use_case IS 'The use case this model is recommended for';
COMMENT ON COLUMN llmbridge.model_usage_hints.reasoning IS 'Explanation of why this model was selected for this use case';
COMMENT ON FUNCTION llmbridge.get_model_for_use_case IS 'Get the best model for a specific use case from a provider';
COMMENT ON FUNCTION llmbridge.get_all_models_for_use_case IS 'Get recommended models for a use case across all providers';
COMMENT ON FUNCTION llmbridge.refresh_usage_hints IS 'Update usage hints during model refresh';
