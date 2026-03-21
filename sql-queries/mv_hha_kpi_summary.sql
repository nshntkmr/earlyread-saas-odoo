CREATE MATERIALIZED VIEW mv_hha_kpi_summary AS
SELECT
    ROW_NUMBER() OVER ()                            AS id,
 
    -- ── DIMENSIONS (grain) ──────────────────────────────────────────────
    hha_ccn,
    year,
    ffs_ma,
    hha_state,
    hha_county,
 
    -- ── VOLUME METRICS ──────────────────────────────────────────────────
    -- Tile 1: Total Admits
    SUM(admits)                                     AS total_admits,
    COUNT(DISTINCT patient_id)                      AS unique_patients,
    COUNT(*)                                        AS episode_count,
 
    -- ── CENSUS / LOS METRICS ────────────────────────────────────────────
    -- Tile 2: ADC = total_hha_days / days_in_period (period calc is widget-side)
    SUM(hha_days)                                   AS total_hha_days,
    SUM(hha_visits)                                 AS total_hha_visits,
    AVG(hha_days)::NUMERIC(8,2)                     AS avg_hha_days,
    AVG(hha_visits)::NUMERIC(8,2)                   AS avg_hha_visits,
 
    -- ── REVENUE METRICS ─────────────────────────────────────────────────
    -- Tile 5: Revenue (Allowed Amount)
    SUM(hha_alwd)                                   AS total_hha_alwd,
    AVG(hha_alwd)::NUMERIC(12,2)                    AS avg_hha_alwd,
 
    -- ── CASE MIX / ACUITY ──────────────────────────────────────────────
    AVG(pdgm_weight)::NUMERIC(8,4)                  AS avg_pdgm_weight,
    AVG(risk_score)::NUMERIC(8,4)                   AS avg_risk_score,
 
    -- ── OUTCOME METRICS ─────────────────────────────────────────────────
    -- Tile 6: Rehospitalization Rate = hospitalization_count / episode_count × 100
    SUM(hospitalization_flag)                        AS hospitalization_count,
    ROUND(100.0 * SUM(hospitalization_flag) /
        NULLIF(COUNT(*), 0), 2)                     AS hospitalization_rate,
 
    -- Mortality
    SUM(death_flag)                                 AS death_count,
    ROUND(100.0 * SUM(death_flag) /
        NULLIF(COUNT(*), 0), 2)                     AS mortality_rate,
 
    -- Dual-eligible
    SUM(dual_flag)                                  AS dual_eligible_count,
    ROUND(100.0 * SUM(dual_flag) /
        NULLIF(COUNT(*), 0), 2)                     AS dual_eligible_pct,
 
    -- ── TIMELY ACCESS (conditional aggregation — IP source only) ────────
    -- Tile 4: Timely Access % = ip_timely_count / ip_referral_count × 100
    --
    -- Only IP (inpatient hospital) referrals have timely access status.
    -- FILTER clause avoids adding `source` to the grain.
    --
    -- ip_referral_count: IP episodes where timely status was recorded
    -- ip_timely_count:   IP episodes where status = 'TIMELY'
    -- ip_late_count:     IP episodes where status = 'LATE'
    -- ip_roc_count:      IP episodes that are Resumptions of Care
    COUNT(*) FILTER (
        WHERE source = 'IP'
          AND ip_hha_timely_access_status IS NOT NULL
    )                                               AS ip_referral_count,
 
    COUNT(*) FILTER (
        WHERE source = 'IP'
          AND ip_hha_timely_access_status = 'TIMELY'
    )                                               AS ip_timely_count,
 
    COUNT(*) FILTER (
        WHERE source = 'IP'
          AND ip_hha_timely_access_status = 'LATE'
    )                                               AS ip_late_count,
 
    COUNT(*) FILTER (
        WHERE source = 'IP'
          AND ip_hha_timely_access_status = 'ROC'
    )                                               AS ip_roc_count,
 
    -- Pre-computed timely access percentage (convenience column)
    ROUND(
        100.0 * COUNT(*) FILTER (
            WHERE source = 'IP'
              AND ip_hha_timely_access_status = 'TIMELY'
        ) / NULLIF(
            COUNT(*) FILTER (
                WHERE source = 'IP'
                  AND ip_hha_timely_access_status IS NOT NULL
            ), 0
        ), 2
    )                                               AS timely_access_pct,
 
    -- ── IP ADMITS (for market share denominator at county level) ────────
    -- Total IP-source admits — useful for Timely Access tile denominator
    SUM(admits) FILTER (WHERE source = 'IP')        AS ip_admits
 
FROM hha_base_claim
GROUP BY hha_ccn, year, ffs_ma, hha_state, hha_county;