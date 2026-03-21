DROP TABLE IF EXISTS hha_base_claim CASCADE;

create table hha_base_claim (
	id                            BIGINT GENERATED ALWAYS AS IDENTITY,
 
    -- ── TIME ────────────────────────────────────────────────────────────
    year                          SMALLINT        NOT NULL,
 
    -- ── PAYER ───────────────────────────────────────────────────────────
    ffs_ma                        VARCHAR(3)      NOT NULL,
 
    -- ── DISCHARGE ───────────────────────────────────────────────────────
    actual_discharge_setting      VARCHAR(20),
 
    -- ── HHA IDENTITY ────────────────────────────────────────────────────
    hha_ccn                       VARCHAR(10)     NOT NULL,
    hha_county                    VARCHAR(100),
    hha_state                     VARCHAR(50),
 
    -- ── REFERRAL SOURCE ─────────────────────────────────────────────────
    source                        VARCHAR(10),
    source_ccn                    VARCHAR(10),
    discharge_fac_ccn             VARCHAR(10),
 
    -- ── PATIENT ─────────────────────────────────────────────────────────
    patient_id                    VARCHAR(30),
 
    -- ── ACO ─────────────────────────────────────────────────────────────
    aco                           VARCHAR(10),
    aco_name                      VARCHAR(200),
 
    -- ── PATIENT GEOGRAPHY ───────────────────────────────────────────────
    patient_stcty                 VARCHAR(5),
    patient_fips                  VARCHAR(5),
    patient_county                VARCHAR(100),
    patient_state                 VARCHAR(50),
    patient_state_code            VARCHAR(2),
    patient_cbsa                  VARCHAR(100),        -- "Non Metropolitan" or CBSA name
 
    -- ── PDGM / CASE MIX ────────────────────────────────────────────────
    hhrg                          VARCHAR(5),          -- Full 5-digit PDGM code
    hhrg1                         VARCHAR(50),         -- Source & timing label
    hhrg2                         VARCHAR(50),         -- Clinical component label
    hhrg3                         VARCHAR(50),         -- Functional status label
    hhrg4                         VARCHAR(50),         -- Comorbidity level label
 
    -- ── MEDICARE ADVANTAGE ──────────────────────────────────────────────
    ma_plan_id                    VARCHAR(20),
    plan_name                     VARCHAR(200),
    parent_organization           VARCHAR(200),
    delivery_system               VARCHAR(50),
    product_type                  VARCHAR(50),
 
    -- ── FLAGS ───────────────────────────────────────────────────────────
    affiliate_flag                SMALLINT        DEFAULT 0,  -- Converted from Yes/No
    ip_network_leakage            SMALLINT        DEFAULT 0,
    ip_hha_timely_access_status   VARCHAR(10),
 
    -- ── PATIENT CHARACTERISTICS ─────────────────────────────────────────
    age_band                      VARCHAR(20),
    pdgm_weight                   NUMERIC(8,4),
    death_flag                    SMALLINT        DEFAULT 0,
    dual_flag                     SMALLINT        DEFAULT 0,
    risk_score                    NUMERIC(8,4),
 
    -- ── UTILIZATION ─────────────────────────────────────────────────────
    discharge_fac_days            INTEGER,
    discharge_fac_visits          INTEGER,
    hha_days                      INTEGER,
    hha_visits                    INTEGER,
    hha_alwd                      NUMERIC(12,2),
    admits                        INTEGER         DEFAULT 0,
 
    -- ── OUTCOMES ────────────────────────────────────────────────────────
    hospitalization_flag          SMALLINT        DEFAULT 0,
 
    -- ── PHYSICIAN / DRG ─────────────────────────────────────────────────
    source_npi                    VARCHAR(10),
    source_drg_cd                 VARCHAR(10),
 
    -- year MUST be in PK for partition routing
    PRIMARY KEY (id, year)
 
) PARTITION BY RANGE (year);

CREATE TABLE hha_base_claim_2022 PARTITION OF hha_base_claim
    FOR VALUES FROM (2022) TO (2023);

CREATE TABLE hha_base_claim_2023 PARTITION OF hha_base_claim
    FOR VALUES FROM (2023) TO (2024);

CREATE TABLE hha_base_claim_2024 PARTITION OF hha_base_claim
    FOR VALUES FROM (2024) TO (2025);

CREATE TABLE hha_base_claim_2025 PARTITION OF hha_base_claim
    FOR VALUES FROM (2025) TO (2026);

