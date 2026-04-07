# Bulk-fill AI Column Intelligence for mv_hha_final_inhome (126 columns).
# Run via: odoo-bin shell -c odoo.conf -d odoo_db < this_file.py

TABLE_NAME = 'mv_hha_final_inhome'

# -- Column Intelligence Map ------------------------------------------
# Keys = column_name in the schema source
# Values = dict of fields to write on dashboard.schema.column

COLUMN_MAP = {

    # ===================================================================
    # IDENTIFIERS
    # ===================================================================
    'hha_ccn': {
        'display_name': 'CMS Certification Number',
        'column_role': 'identifier',
        'is_filterable': True, 'is_measure': False, 'is_dimension': False,
        'description': 'Unique 6-digit CMS ID per Medicare-certified HHA. Primary key for linking claims, cost reports, and quality data.',
        'domain_notes': 'First 2 digits = state code. Primary join key across datasets.',
    },
    'hha_npi': {
        'display_name': 'National Provider Identifier',
        'column_role': 'identifier',
        'is_filterable': True, 'is_measure': False, 'is_dimension': False,
        'description': 'Unique 10-digit HIPAA provider ID used across all payers (Medicare, Medicaid, commercial).',
        'domain_notes': 'Stays with provider across ownership changes. Used for billing and referral tracking.',
    },
    'cms_certification_number': {
        'display_name': 'CMS Certification Number (Alt)',
        'column_role': 'identifier',
        'is_filterable': False, 'is_measure': False, 'is_dimension': False,
        'description': 'Alternate CCN representation that may include leading zeros or format variations.',
        'domain_notes': 'May differ from hha_ccn formatting. Use hha_ccn as primary key.',
    },
    'hha_id': {
        'display_name': 'Agency Internal ID',
        'column_role': 'identifier',
        'is_filterable': False, 'is_measure': False, 'is_dimension': False,
        'description': 'System-generated internal identifier for the HHA.',
    },
    'hha_id_owner': {
        'display_name': 'Owner Internal ID',
        'column_role': 'identifier',
        'is_filterable': True, 'is_measure': False, 'is_dimension': False,
        'description': 'Parent organization identifier. Agencies under the same ownership share this ID.',
        'domain_notes': 'Use for portfolio rollup analysis across agencies in same group.',
    },
    'left_right_hha_ccn': {
        'display_name': 'Left/Right HHA CCN',
        'column_role': 'identifier',
        'is_filterable': False, 'is_measure': False, 'is_dimension': False,
        'description': 'Data linkage auxiliary key for pipeline joins.',
        'domain_notes': 'Internal pipeline use only. Not for display or analytics.',
    },
    'right_hha_ccn': {
        'display_name': 'Right HHA CCN',
        'column_role': 'identifier',
        'is_filterable': False, 'is_measure': False, 'is_dimension': False,
        'description': 'Secondary CCN reference for join operations between datasets.',
        'domain_notes': 'Internal pipeline use only. Not for display or analytics.',
    },

    # ===================================================================
    # DIMENSIONS -- Agency Identity
    # ===================================================================
    'hha_brand_name': {
        'display_name': 'Agency Brand Name',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Consumer-facing brand name. Chains share brand across multiple CCNs (e.g., Amedisys, LHC Group).',
        'domain_notes': 'Use for GROUP BY to see portfolio-level aggregates.',
    },
    'hha_name': {
        'display_name': 'Agency Legal Name',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Official CMS-registered legal name of the HHA.',
    },
    'hha_dba': {
        'display_name': 'Agency DBA Name',
        'column_role': 'dimension',
        'is_filterable': False, 'is_dimension': True, 'is_measure': False,
        'description': 'Trade or operating name that may differ from legal entity name.',
    },
    'hha_name_owner': {
        'display_name': 'Owner Legal Name',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Legal name of the parent organization or holding company.',
    },
    'hha_dba_owner': {
        'display_name': 'Owner DBA Name',
        'column_role': 'dimension',
        'is_filterable': False, 'is_dimension': True, 'is_measure': False,
        'description': 'Trade name of the ownership entity.',
    },

    # ===================================================================
    # DIMENSIONS -- Location
    # ===================================================================
    'hha_state': {
        'display_name': 'State Name',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Full U.S. state name where HHA is located and licensed.',
        'domain_notes': 'Dataset filtered to 5 states: California, Florida, Illinois, Pennsylvania, Texas.',
    },
    'hha_state_cd': {
        'display_name': 'State Code',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Two-letter USPS state abbreviation (TX, CA, FL, IL, PA).',
    },
    'hha_county': {
        'display_name': 'County Name',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'County where HHA is located (INITCAP formatted). Critical for competitive analysis.',
        'domain_notes': 'Referral patterns and payer mix vary significantly at county level.',
    },
    'hha_city': {
        'display_name': 'City Name',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'City of HHA office location. Service area extends beyond office city.',
    },
    'hha_address': {
        'display_name': 'Street Address',
        'column_role': 'dimension',
        'is_filterable': False, 'is_dimension': False, 'is_measure': False,
        'description': 'Physical street address of HHA office as registered with CMS.',
    },
    'hha_zip': {
        'display_name': 'ZIP Code',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': '5-digit ZIP code. Stored as BIGINT -- leading zeros may be lost.',
        'domain_notes': "Use LPAD(hha_zip::text, 5, '0') for display formatting (New England ZIPs).",
    },
    'hha_fips': {
        'display_name': 'FIPS County Code',
        'column_role': 'identifier',
        'is_filterable': False, 'is_dimension': False, 'is_measure': False,
        'description': '5-digit FIPS code (2-digit state + 3-digit county). Federal geographic standard.',
        'domain_notes': 'Use for joining Census Bureau demographic/socioeconomic data.',
    },
    'hha_cbsa': {
        'display_name': 'CBSA Code',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Core-Based Statistical Area (metro/micro). Used by CMS for wage index adjustments.',
        'domain_notes': 'Higher-cost CBSAs receive higher HH PPS payment adjustments.',
    },

    # ===================================================================
    # DIMENSIONS -- Time & Segment
    # ===================================================================
    'year': {
        'display_name': 'Reporting Year',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Calendar year (2022-2025). CMS data reported Jan 1 - Dec 31.',
        'domain_notes': '2025 may be partial year or projected.',
    },
    'ffs_ma': {
        'display_name': 'Payer Segment (FFS/MA)',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Fee-For-Service (FFS) vs Medicare Advantage (MA). Critical segmentation.',
        'domain_notes': 'Always filter or segment by this. FFS and MA have very different utilization patterns. MA data only available for 2022-2023.',
    },

    # ===================================================================
    # DIMENSIONS -- Quality & Clinical
    # ===================================================================
    'hha_rating': {
        'display_name': 'CMS Star Rating',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'CMS Quality of Patient Care Star Rating (1-5 stars). Based on 7 OASIS quality measures.',
        'domain_notes': 'Published on CMS Care Compare. Primary factor in hospital/physician referral decisions.',
    },

    # ===================================================================
    # DIMENSIONS -- BD Priority Tiers
    # ===================================================================
    'bd_priority_tier_overall': {
        'display_name': 'BD Priority Overall',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Overall BD priority: High/Moderate/Low. Primary sales targeting field.',
        'domain_notes': 'Derived from composite_score. High = most attractive targets.',
    },
    'bd_priority_frequency': {
        'display_name': 'BD Priority Frequency',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'BD priority based on visit frequency/volume (H/M/L).',
    },
    'bd_priority_intensity': {
        'display_name': 'BD Priority Intensity',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'BD priority based on therapy visits per admission (H/M/L).',
    },
    'bd_priority_stability': {
        'display_name': 'BD Priority Stability',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'BD priority based on therapy share consistency over time (H/M/L).',
        'domain_notes': 'Less stable agencies = more receptive to outsourced therapy partnerships.',
    },
    'priority_group': {
        'display_name': 'Priority Group',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Sales targeting tier: Tier 1 / Tier 2 / Watchlist.',
        'domain_notes': 'Tier 1 = High overall priority AND 2025 admits above state median. Tier 2 = High+below median OR Moderate+above median. Watchlist = all others.',
    },

    # ===================================================================
    # DIMENSIONS -- Service Offerings
    # ===================================================================
    'offers_nursing_care_services': {
        'display_name': 'Offers Nursing Care',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Whether agency offers skilled nursing (Yes/No).',
        'domain_notes': 'Virtually all Medicare-certified HHAs offer nursing.',
    },
    'offers_physical_therapy_services': {
        'display_name': 'Offers PT Services',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Whether agency offers physical therapy (Yes/No).',
    },
    'offers_occupational_therapy_services': {
        'display_name': 'Offers OT Services',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Whether agency offers occupational therapy (Yes/No).',
    },
    'offers_speech_pathology_services': {
        'display_name': 'Offers SLP Services',
        'column_role': 'dimension',
        'is_filterable': True, 'is_dimension': True, 'is_measure': False,
        'description': 'Whether agency offers speech-language pathology (Yes/No).',
        'domain_notes': 'Least common therapy discipline. Competitive advantage for stroke/neuro referrals.',
    },

    # ===================================================================
    # DIMENSIONS -- Contact Info
    # ===================================================================
    'hha_auth_person': {
        'display_name': 'Authorized Person',
        'column_role': 'dimension',
        'is_filterable': False, 'is_dimension': False, 'is_measure': False,
        'description': 'Agency administrator/CEO/owner designated as CMS authorized representative.',
        'domain_notes': 'Key BD outreach contact -- decision-maker for partnerships.',
    },
    'hha_auth_person_desgn': {
        'display_name': 'Auth Person Title',
        'column_role': 'dimension',
        'is_filterable': False, 'is_dimension': False, 'is_measure': False,
        'description': 'Title/role: Administrator, CEO, Owner, Director of Nursing.',
    },
    'hha_auth_person_tele': {
        'display_name': 'Auth Person Phone',
        'column_role': 'dimension',
        'is_filterable': False, 'is_dimension': False, 'is_measure': False,
        'description': 'Direct phone number for the authorized representative.',
        'domain_notes': 'Key BD outreach field -- direct line to decision-makers.',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- Volume (Current Year)
    # ===================================================================
    'hha_days': {
        'display_name': 'Total HH Days',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total calendar days of home health care across all episodes in the reporting year.',
    },
    'hha_visits': {
        'display_name': 'Total Skilled Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total billable skilled visits across all disciplines. Denominator for therapy_share.',
        'domain_notes': 'This is the denominator for therapy_share calculation.',
    },
    'hha_admits': {
        'display_name': 'Total Admissions',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total new patient admissions (starts of care) or 30-day period initiations.',
        'domain_notes': 'Primary volume metric. Denominator for visits_per_admit and therapy_visits_per_admit.',
    },
    'deaths': {
        'display_name': 'Deaths During Episodes',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Patients who died while receiving home health services.',
        'domain_notes': 'High ratio to admits may indicate hospice-transition or end-of-life population.',
    },
    'duals': {
        'display_name': 'Dual-Eligible Beneficiaries',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Patients enrolled in both Medicare and Medicaid. Lower income, higher acuity.',
        'domain_notes': 'High proportion correlates with higher resource utilization and complex social needs.',
    },
    'timely_status': {
        'display_name': 'Timely Initiation Count',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Episodes where care started within CMS-mandated 48-hour timeframe.',
        'domain_notes': 'One of 7 CMS Star Rating measures. Near-100% compliance needed for top ratings.',
    },
    'ip_flag': {
        'display_name': 'Institutional Admissions',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Patients admitted from hospital/SNF/IRF/LTCH (within 14 days prior to SOC).',
        'domain_notes': 'PDGM case-mix variable. Institutional admissions carry higher case-mix weights.',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- Visit Counts by Discipline
    # ===================================================================
    'nur_visit': {
        'display_name': 'Nursing Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Skilled nursing visits (RN/LPN). Includes assessments, med management, wound care.',
        'domain_notes': 'Typically highest-volume discipline in home health.',
    },
    'ot_visit': {
        'display_name': 'OT Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Occupational therapy visits. Focuses on ADLs, home safety, functional independence.',
    },
    'pt_visit': {
        'display_name': 'PT Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Physical therapy visits. Mobility, strength, balance, gait, fall prevention.',
        'domain_notes': 'Often highest-volume therapy discipline.',
    },
    'aid_visit': {
        'display_name': 'Aide Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Home health aide visits. Personal care, light housekeeping, supervised exercises.',
        'domain_notes': 'Must be under RN or therapist supervision.',
    },
    'slp_visit': {
        'display_name': 'SLP Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Speech-language pathology visits. Swallowing, speech, cognitive-linguistic impairments.',
        'domain_notes': 'Least common therapy. Critical for stroke, TBI, and neurological populations.',
    },
    'rsn_visit': {
        'display_name': 'Restorative Nursing Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Restorative nursing visits. Structured exercises to maintain functional abilities.',
    },
    'oth_visit': {
        'display_name': 'Other Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Visits outside standard disciplines. May include Medical Social Services (MSS).',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- Service Units by Discipline
    # ===================================================================
    'tot_srvc_unit': {
        'display_name': 'Total Service Units',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate 15-minute service units across all disciplines.',
        'domain_notes': 'More granular resource measure than visit counts -- captures visit duration.',
    },
    'nur_srvc_unit': {
        'display_name': 'Nursing Service Units',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': '15-minute nursing units. Higher units per visit = longer, more complex encounters.',
    },
    'ot_srvc_unit': {
        'display_name': 'OT Service Units',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': '15-minute OT units.',
    },
    'pt_srvc_unit': {
        'display_name': 'PT Service Units',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': '15-minute PT units.',
    },
    'aid_srvc_unit': {
        'display_name': 'Aide Service Units',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': '15-minute aide units. Typically higher per-visit counts (longer duration).',
    },
    'slp_srvc_unit': {
        'display_name': 'SLP Service Units',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': '15-minute SLP units.',
    },
    'rsn_srvc_unit': {
        'display_name': 'Restorative Nursing Units',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': '15-minute restorative nursing units.',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- Year-Over-Year Visits
    # ===================================================================
    'visits_2022': {
        'display_name': 'Total Visits 2022',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total skilled visits CY2022.',
    },
    'visits_2023': {
        'display_name': 'Total Visits 2023',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total skilled visits CY2023.',
    },
    'visits_2024': {
        'display_name': 'Total Visits 2024',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total skilled visits CY2024.',
    },
    'visits_2025': {
        'display_name': 'Total Visits 2025',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total skilled visits CY2025 (may be partial year).',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- Year-Over-Year Admits
    # ===================================================================
    'admits_2022': {
        'display_name': 'Admissions 2022',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total admissions/SOCs CY2022.',
    },
    'admits_2023': {
        'display_name': 'Admissions 2023',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total admissions CY2023.',
    },
    'admits_2024': {
        'display_name': 'Admissions 2024',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total admissions CY2024.',
    },
    'admits_2025': {
        'display_name': 'Admissions 2025',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total admissions CY2025.',
        'domain_notes': 'Used in Priority Group calculation vs state_median.',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- Year-Over-Year Therapy Visits
    # ===================================================================
    'therapy_visits_2022': {
        'display_name': 'Therapy Visits 2022',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'PT+OT+SLP visits CY2022.',
    },
    'therapy_visits_2023': {
        'display_name': 'Therapy Visits 2023',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'PT+OT+SLP visits CY2023.',
    },
    'therapy_visits_2024': {
        'display_name': 'Therapy Visits 2024',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'PT+OT+SLP visits CY2024.',
    },
    'therapy_visits_2025': {
        'display_name': 'Therapy Visits 2025',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'PT+OT+SLP visits CY2025.',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- State-Level Benchmarks
    # ===================================================================
    'state_hha_admits': {
        'display_name': 'State Total Admissions',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate admissions across all HHAs in same state/year/segment.',
        'domain_notes': 'State-level benchmark. Use for market share calculation.',
    },
    'state_hha_visits': {
        'display_name': 'State Total Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate visits across all HHAs in state/year/segment.',
    },
    'state_nur': {
        'display_name': 'State Nursing Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate nursing visits at state level.',
    },
    'state_ot': {
        'display_name': 'State OT Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate OT visits at state level.',
    },
    'state_pt': {
        'display_name': 'State PT Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate PT visits at state level.',
    },
    'state_slp': {
        'display_name': 'State SLP Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate SLP visits at state level.',
    },
    'state_therapy_visits': {
        'display_name': 'State Therapy Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate therapy visits (OT+PT+SLP) at state level.',
    },
    'state_hha_count': {
        'display_name': 'State HHA Count',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Distinct Medicare-certified HHAs in state/year/segment.',
        'domain_notes': 'Market density indicator.',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- County-Level Benchmarks
    # ===================================================================
    'county_hha_admits': {
        'display_name': 'County Total Admissions',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate admissions in same county/year/segment.',
        'domain_notes': 'Most relevant competitive benchmark -- referrals are highly localized.',
    },
    'county_hha_visits': {
        'display_name': 'County Total Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate visits at county level.',
    },
    'county_nur': {
        'display_name': 'County Nursing Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate nursing visits at county level.',
    },
    'county_ot': {
        'display_name': 'County OT Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate OT visits at county level.',
    },
    'county_pt': {
        'display_name': 'County PT Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate PT visits at county level.',
    },
    'county_slp': {
        'display_name': 'County SLP Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate SLP visits at county level.',
    },
    'county_therapy_visits': {
        'display_name': 'County Therapy Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate therapy visits (OT+PT+SLP) at county level.',
    },
    'county_hha_count': {
        'display_name': 'County HHA Count',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Distinct HHAs in county. Market competition indicator.',
        'domain_notes': '2-3 HHAs = low competition; 50+ = highly competitive (e.g., Harris County TX, LA County CA).',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- National-Level Benchmarks
    # ===================================================================
    'nation_hha_admits': {
        'display_name': 'National Total Admissions',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate admissions across all HHAs nationally for year/segment.',
        'domain_notes': 'Broadest benchmark context.',
    },
    'nation_hha_visits': {
        'display_name': 'National Total Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate visits nationally.',
    },
    'nation_nur': {
        'display_name': 'National Nursing Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate nursing visits nationally.',
    },
    'nation_ot': {
        'display_name': 'National OT Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate OT visits nationally.',
    },
    'nation_pt': {
        'display_name': 'National PT Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate PT visits nationally.',
    },
    'nation_slp': {
        'display_name': 'National SLP Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate SLP visits nationally.',
    },
    'nation_therapy_visits': {
        'display_name': 'National Therapy Visits',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Aggregate therapy visits (OT+PT+SLP) nationally.',
    },
    'nation_hha_count': {
        'display_name': 'National HHA Count',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Total Medicare-certified HHAs nationally.',
        'domain_notes': 'Approximately 11,000+ certified HHAs in the US.',
    },

    # ===================================================================
    # ADDITIVE MEASURES -- Rankings (integer, but treated as measures)
    # ===================================================================
    'therapy_rank_in_county': {
        'display_name': 'Therapy Rank in County',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Rank by therapy share within county (1=highest therapy share).',
        'domain_notes': 'Do not SUM or AVG ranks. Use for display and sorting only.',
        'never_avg': True,
    },
    'stability_rank_in_county': {
        'display_name': 'Stability Rank in County',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Rank by stability factor within county (1=most stable).',
        'domain_notes': 'Do not SUM or AVG ranks. Use for display and sorting only.',
        'never_avg': True,
    },
    'intensity_rank_in_county': {
        'display_name': 'Intensity Rank in County',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Rank by therapy visits per admission within county (1=highest intensity).',
        'domain_notes': 'Do not SUM or AVG ranks. Use for display and sorting only.',
        'never_avg': True,
    },
    'overall_rank_in_county': {
        'display_name': 'Overall Rank in County',
        'column_role': 'additive_measure',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Rank by composite score within county (1=top BD target).',
        'domain_notes': 'Do not SUM or AVG ranks. Use for display and sorting only.',
        'never_avg': True,
    },

    # ===================================================================
    # PRE-COMPUTED RATES (never_avg = True automatically)
    # ===================================================================
    'therapy_share': {
        'display_name': 'Therapy Share',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Proportion of total visits that are therapy (PT+OT+SLP). E.g., 0.42 = 42%.',
        'domain_notes': 'NEVER AVG. Recompute as SUM(pt_visit+ot_visit+slp_visit)/SUM(hha_visits). Post-PDGM: >60% attracts CMS audit scrutiny; very low = under-serving patients.',
    },
    'therapy_share_2022': {
        'display_name': 'Therapy Share 2022',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Therapy share for CY2022.',
        'domain_notes': 'NEVER AVG. Pre-computed rate.',
    },
    'therapy_share_2023': {
        'display_name': 'Therapy Share 2023',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Therapy share for CY2023.',
        'domain_notes': 'NEVER AVG. Pre-computed rate.',
    },
    'therapy_share_2024': {
        'display_name': 'Therapy Share 2024',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Therapy share for CY2024.',
        'domain_notes': 'NEVER AVG. Pre-computed rate.',
    },
    'therapy_share_2025': {
        'display_name': 'Therapy Share 2025',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Therapy share for CY2025.',
        'domain_notes': 'NEVER AVG. Pre-computed rate. Trending YoY reveals utilization shifts.',
    },
    'therapy_visits_per_ad_2022': {
        'display_name': 'Therapy Visits/Admit 2022',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Average therapy visits per admission CY2022. Measures therapy intensity.',
        'domain_notes': 'NEVER AVG. Recompute as SUM(therapy_visits)/SUM(admits) if aggregating.',
    },
    'therapy_visits_per_ad_2023': {
        'display_name': 'Therapy Visits/Admit 2023',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Therapy intensity CY2023.',
        'domain_notes': 'NEVER AVG. Pre-computed rate.',
    },
    'therapy_visits_per_ad_2024': {
        'display_name': 'Therapy Visits/Admit 2024',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Therapy intensity CY2024.',
        'domain_notes': 'NEVER AVG. Pre-computed rate.',
    },
    'therapy_visits_per_ad_2025': {
        'display_name': 'Therapy Visits/Admit 2025',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Therapy intensity CY2025.',
        'domain_notes': 'NEVER AVG. Pre-computed rate.',
    },
    'visits_per_ad_2022': {
        'display_name': 'Visits/Admit 2022',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Average total visits per admission CY2022. Overall care intensity.',
        'domain_notes': 'NEVER AVG. Recompute as SUM(visits)/SUM(admits) if aggregating.',
    },
    'visits_per_ad_2023': {
        'display_name': 'Visits/Admit 2023',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Overall care intensity CY2023.',
        'domain_notes': 'NEVER AVG. Pre-computed rate.',
    },
    'visits_per_ad_2024': {
        'display_name': 'Visits/Admit 2024',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Overall care intensity CY2024.',
        'domain_notes': 'NEVER AVG. Pre-computed rate.',
    },
    'visits_per_ad_2025': {
        'display_name': 'Visits/Admit 2025',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Overall care intensity CY2025.',
        'domain_notes': 'NEVER AVG. Pre-computed rate.',
    },
    'pdgm_weight': {
        'display_name': 'PDGM Case-Mix Weight',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Resource utilization multiplier for 30-day HH period. 432 case-mix groups.',
        'domain_notes': 'NEVER AVG across agencies. Higher weight = more complex patients. Multiplied by base payment rate for reimbursement.',
    },
    'risk_score': {
        'display_name': 'HCC Risk Score',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'CMS-HCC risk adjustment score predicting healthcare costs. 1.0 = average.',
        'domain_notes': 'NEVER AVG across agencies. >1.0 = sicker population; <1.0 = healthier. Contextualizes utilization levels.',
    },

    # ===================================================================
    # PRE-COMPUTED RATES -- Stability & Scoring
    # ===================================================================
    'std': {
        'display_name': 'Therapy Share Std Dev',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Standard deviation of therapy share across reporting periods.',
        'domain_notes': 'NEVER AVG. Higher = more volatile therapy utilization. Used to compute stability_factor.',
    },
    'mean': {
        'display_name': 'Therapy Share Mean',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Arithmetic average of therapy share across available years.',
        'domain_notes': 'NEVER AVG. Used with std to compute stability_factor (mean/std).',
    },
    'stability_factor': {
        'display_name': 'Stability Factor',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Therapy share consistency over time (mean/std). Higher = more stable.',
        'domain_notes': 'NEVER AVG. Low stability = practice patterns in flux = more receptive to partnerships = BD opportunity.',
    },
    'state_median': {
        'display_name': 'State Median Admits',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Median admits across all HHAs in the state. Threshold for Priority Group.',
        'domain_notes': 'NEVER AVG. Used to classify Tier 1 vs Tier 2: admits_2025 > state_median = above median.',
    },
    'composite_score': {
        'display_name': 'Composite Score',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Weighted blend of therapy share, stability, and intensity rankings.',
        'domain_notes': 'NEVER AVG. Higher = more attractive BD target. Drives bd_priority_tier_overall.',
    },
    'therapy_share_percentile': {
        'display_name': 'Therapy Share Percentile',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Percentile rank of therapy share vs all agencies. 0.90 = higher than 90%.',
        'domain_notes': 'NEVER AVG.',
    },
    'stability_percentile': {
        'display_name': 'Stability Percentile',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Percentile rank of stability factor. Higher = more stable.',
        'domain_notes': 'NEVER AVG.',
    },
    'intensity_percentile': {
        'display_name': 'Intensity Percentile',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Percentile rank of therapy visits per admission.',
        'domain_notes': 'NEVER AVG.',
    },
    'overall_share_percentile': {
        'display_name': 'Overall Percentile',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'Percentile rank of composite score vs all agencies.',
        'domain_notes': 'NEVER AVG.',
    },

    # ===================================================================
    # PRE-COMPUTED RATES -- Benchmark Rates
    # ===================================================================
    'state_therapy_share': {
        'display_name': 'State Therapy Share',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'State-level therapy share benchmark: (state OT+PT+SLP) / state total visits.',
        'domain_notes': 'NEVER AVG. State benchmark for comparing individual agency therapy share.',
    },
    'state_visits_per_admit': {
        'display_name': 'State Visits/Admit',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'State-level average visits per admission benchmark.',
        'domain_notes': 'NEVER AVG. State benchmark for comparing agency care intensity.',
    },
    'county_therapy_share': {
        'display_name': 'County Therapy Share',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'County-level therapy share benchmark.',
        'domain_notes': 'NEVER AVG. Most meaningful competitive comparison -- practice patterns vary by local market.',
    },
    'county_visits_per_admit': {
        'display_name': 'County Visits/Admit',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'County-level visits per admission benchmark.',
        'domain_notes': 'NEVER AVG. Tightest benchmark for comparing against immediate competitors.',
    },
    'nation_therapy_share': {
        'display_name': 'National Therapy Share',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'National-level therapy share benchmark.',
        'domain_notes': 'NEVER AVG. Broadest benchmark, independent of local market dynamics.',
    },
    'nation_visits_per_admit': {
        'display_name': 'National Visits/Admit',
        'column_role': 'pre_computed_rate',
        'is_measure': True, 'is_dimension': False, 'is_filterable': False,
        'description': 'National-level visits per admission benchmark.',
        'domain_notes': 'NEVER AVG. Broadest intensity benchmark.',
    },
}


# -- Main Execution ---------------------------------------------------

source = env['dashboard.schema.source'].search(
    [('table_name', '=', TABLE_NAME)], limit=1
)
if not source:
    print(f"ERROR: Schema source '{TABLE_NAME}' not found. Run 'Discover Materialized Views' first.")
else:
    updated = 0
    skipped = 0
    missing = []

    for col in source.column_ids:
        if col.column_name in COLUMN_MAP:
            vals = COLUMN_MAP[col.column_name].copy()
            # pre_computed_rate auto-sets never_avg via onchange,
            # but shell scripts don't trigger onchange, so set it explicitly
            if vals.get('column_role') == 'pre_computed_rate':
                vals.setdefault('never_avg', True)
            col.write(vals)
            updated += 1
        else:
            skipped += 1
            missing.append(col.column_name)

    env.cr.commit()
    print(f"\nDone! Updated {updated}/{updated + skipped} columns in '{TABLE_NAME}'.")
    if missing:
        print(f"Skipped {skipped} columns not in mapping: {missing}")
    print("Column intelligence has been filled successfully.")
