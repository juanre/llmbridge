-- Fix division by zero error in get_usage_stats function

-- Drop and recreate the function with proper null handling
DROP FUNCTION IF EXISTS get_usage_stats(VARCHAR(255), VARCHAR(255), INTEGER);

CREATE OR REPLACE FUNCTION get_usage_stats(
    p_origin VARCHAR(255),
    p_id_at_origin VARCHAR(255),
    p_days INTEGER DEFAULT 30
) RETURNS TABLE (
    total_calls BIGINT,
    total_tokens BIGINT,
    total_cost DECIMAL(12, 8),
    avg_cost_per_call DECIMAL(12, 8),
    most_used_model VARCHAR(100),
    success_rate DECIMAL(5, 4),
    avg_response_time_ms INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(*)::BIGINT as total_calls,
        COALESCE(SUM(ac.total_tokens), 0)::BIGINT as total_tokens,
        COALESCE(SUM(ac.estimated_cost), 0) as total_cost,
        CASE
            WHEN COUNT(*) > 0 THEN (SUM(ac.estimated_cost) / COUNT(*))
            ELSE 0::DECIMAL
        END as avg_cost_per_call,
        (
            SELECT model_name
            FROM llm_api_calls
            WHERE origin = p_origin AND id_at_origin = p_id_at_origin
                AND called_at >= CURRENT_DATE - INTERVAL '1 day' * p_days
            GROUP BY model_name
            ORDER BY COUNT(*) DESC
            LIMIT 1
        ) as most_used_model,
        CASE
            WHEN COUNT(*) > 0 THEN (COUNT(*) FILTER (WHERE ac.status = 'success')::DECIMAL / COUNT(*))
            ELSE 0::DECIMAL
        END as success_rate,
        AVG(ac.response_time_ms)::INTEGER as avg_response_time_ms
    FROM llm_api_calls ac
    WHERE ac.origin = p_origin
        AND ac.id_at_origin = p_id_at_origin
        AND ac.called_at >= CURRENT_DATE - INTERVAL '1 day' * p_days;
END;
$$ LANGUAGE plpgsql;
