"""Data dictionary for the published tables (outputs/*.csv) and the one-file download of all of them.

Only top-level CSV files in outputs/ are published. outputs/private/ (for example the private IMPLAN benchmark) and
any file whose name mentions IMPLAN are never included.
"""
import io
import zipfile
from datetime import date
from config import OUT

TABLES = {
    "acs_places.csv": "Population, age, income, home value and unemployment for the state, counties, planning regions, "
                      "legislative districts (level district), "
                      "peer states and the US (Census ACS 5-year); each estimate has a 90% margin of error (_moe).",
    "bds_counties.csv": "Firms, establishments, jobs, openings, closings and job creation by ND county and year (Census BDS).",
    "bds_firm_age.csv": "Firms, establishments and jobs by firm age, ND, peers and US (Census BDS).",
    "bds_states.csv": "Firms, establishments, jobs, openings, closings and job creation by state and year (Census BDS).",
    "bea_gdp.csv": "GDP by state and industry; measure 'current' (millions of current dollars) or 'real' (millions of "
                   "chained 2017 dollars) (BEA).",
    "bfs_monthly.csv": "Business applications by month, state and sector; sa = S (seasonally adjusted) or U (not) (Census BFS).",
    "cbp_sizes.csv": "Establishments by employment size class, county and sector (Census CBP).",
    "clusters.csv": "ND industries: location quotient against yearly job growth, with cluster position (IPBA from BLS QCEW).",
    "county_business.csv": "Employer establishments, employees, payroll and nonemployer businesses by county and sector "
                           "(Census CBP and Nonemployer Statistics); _k = thousands of dollars.",
    "diffusion.csv": "Diffusion index: share of ND indicators better than a year earlier, all indicators and timely "
                     "(monthly and quarterly) only (IPBA).",
    "diffusion_detail.csv": "Latest value and year-earlier value of each indicator in the diffusion index (IPBA).",
    "dynamics_growth.csv": "Long, medium and short-run yearly growth of key measures, ND and US (IPBA).",
    "dynamics_phases.csv": "Average yearly growth of key measures in each phase of ND's economy (IPBA).",
    "dynamics_series.csv": "Yearly series behind the evolving dynamics page (IPBA from public sources).",
    "economic_base.csv": "Export-oriented (economic base) jobs by industry, location-quotient method (IPBA from BLS QCEW).",
    "indicators.csv": "Business and innovation indicators by geography and date; definitions in indicators_catalog.csv.",
    "indicators_catalog.csv": "Name, theme, unit, frequency, direction and source of each indicator.",
    "io_calibration.csv": "Calibration of the FLQ delta parameter against EPA StateIO (IPBA input-output model).",
    "io_contribution.csv": "Economic contribution of each industry: direct, Type I and Type II output, jobs, labor income, "
                           "value added and state and local taxes; money in millions of dollars (IPBA model).",
    "io_industries.csv": "Model industries with US, ND and planning-region jobs, pay and productivity ratios.",
    "io_multipliers.csv": "Type I and Type II multipliers by place and industry, and effects per $1 million of sales (IPBA model).",
    "io_stateio_compare.csv": "IPBA Type I output multipliers next to EPA StateIO and US values.",
    "io_tax_ratios.csv": "Effective ND state and local tax ratios used for tax effects.",
    "io_validation.csv": "Validation checks of the IPBA input-output model against public benchmarks.",
    "outlook_backtest.csv": "Backtest errors of each outlook model (rolling origin).",
    "outlook_forecast.csv": "Actual values and statistical outlooks with 80% ranges (lo, hi); kind = actual or forecast.",
    "outlook_paths.csv": "Illustrative paths to 2030 under stated growth rates (not forecasts).",
    "patents_nd_owner.csv": "Utility patents with an ND inventor by year and owner type (USPTO PatentsView).",
    "patents_nd_region.csv": "Utility patents with an ND inventor by year, planning region and county (fractional counts).",
    "patents_state.csv": "Utility patents by state and year, and per 100,000 residents (USPTO PatentsView).",
    "pce_price_quarterly.csv": "Price indexes for personal consumption expenditures and GDP, quarterly, 2017 = 100 "
                               "(BEA NIPA Table 1.1.4).",
    "workforce_jolts.csv": "Job openings (thousands), openings, hires and quits rates (%), ND and US, monthly, "
                           "seasonally adjusted (BLS JOLTS state estimates).",
    "workforce_oews.csv": "Jobs, shares and median annual wages by major occupation group, ND and US, May estimates "
                          "(BLS OEWS).",
    "ipeds_completions.csv": "Degrees and certificates awarded (first majors) by ND institution, field and level, by "
                             "academic year ending (NCES IPEDS).",
    "ipeds_programs.csv": "Latest year's awards by program (6-digit CIP) and level: ND, NDUS and US (50 states and "
                          "DC) (NCES IPEDS).",
    "cip_soc_links.csv": "Programs (CIP 2020) linked to major occupation groups (SOC 2018), with the share of each "
                         "award counted for each group (NCES-BLS crosswalk; postsecondary teachers excluded).",
    "retail_gap.csv": "Retail and restaurant sales, expected sales from household income, pull factor and gap by "
                      "county, planning region and store type, 2022 (IPBA from the Census Economic Census and ACS).",
    "consumer_spending.csv": "Personal consumption expenditures per resident by category, ND, peer states and US, "
                             "current dollars (BEA SAPCE2); depth = indent level of the category.",
    "irs_soi.csv": "Individual income tax returns, adjusted gross income, returns with business (Schedule C) and farm "
                   "(Schedule F) income, by county, planning region and state, tax years (IRS Statistics of Income).",
    "trade_exports.csv": "Goods exports by state, $ millions: manufactured, non-manufactured, reexports and total; "
                         "months = 12 for a full year, fewer for year to date (Census, ZIP-code based origin of movement).",
    "trade_ag_exports.csv": "Estimated farm exports by state and commodity, $ millions, calendar years (USDA ERS).",
    "trade_products.csv": "Goods starting their export journey in North Dakota by HS 2-digit chapter, $ millions, year "
                          "to date (months) (Census API, state-based origin of movement).",
    "trade_destinations.csv": "Goods starting their export journey in North Dakota by destination country, $ millions, "
                              "year to date (months) (Census API, state-based origin of movement).",
    "sba_state.csv": "SBA 7(a) and 504 loans approved by project state (ND, peers, US), program and federal fiscal "
                     "year: loans, amount, jobs reported, loans to startups and charge-offs (SBA FOIA data).",
    "sba_county.csv": "SBA loans for North Dakota counties and planning regions over the latest 5 fiscal years, by "
                      "program; amounts withheld for groups with fewer than 3 loans.",
    "sba_industry.csv": "SBA loans for North Dakota projects by industry, program and fiscal year; amounts withheld "
                        "for groups with fewer than 3 loans.",
    "cost_business.csv": "Cost measures for ND, peers and US by year: rpp_* price parities (US = 100), elec_* "
                         "electricity (cents/kWh; _ytd = this year to date), gas_* natural gas ($/Mcf), pay_private "
                         "(QCEW $), tax_* state taxes per resident ($).",
    "outlook_sector.csv": "Private jobs by industry sector: actual quarters and the 4-quarter statistical outlook with "
                          "80% ranges (lo, hi); kind = actual or forecast.",
    "outlook_sector_meta.csv": "Sector outlook summary: model chosen, average jobs last 4 quarters and next 4 quarters, "
                               "80% range, backtest error, out-of-sample range coverage, withheld quarters estimated.",
    "target_industries.csv": "North Dakota's six targeted industries (ND Commerce definitions, IPBA NAICS codes) by year: establishments, jobs and pay in codes BLS publishes, location quotient, job change, withheld codes "
                             "(IPBA from BLS QCEW).",
    "target_industry_codes.csv": "The NAICS codes IPBA assigns to each targeted industry, with ND establishments, jobs, pay and location quotient in the headline year (BLS QCEW).",
    "freight_nd.csv": "Freight to, from, within and through North Dakota by flow, goods (SCTG 2-digit) and mode, 2017-2024 and FAF forecasts 2030-2050 (FHWA/BTS Freight Analysis Framework 5.7.1).",
    "freight_partners.csv": "North Dakota freight by flow and partner state or world region, 2017, 2024 and 2050 (FAF 5.7.1).",
    "freight_states.csv": "Freight starting and ending in each state and the US by year, 2017-2050 (FAF 5.7.1).",
    "target_occupations.csv": "Top occupations in each targeted industry in ND, estimated from ND jobs and national staffing patterns, with ND median wages (IPBA from BLS OEWS and QCEW).",
    "target_occ_groups.csv": "Occupation groups in each targeted industry (estimated ND jobs) and ND graduates linked to each group (IPBA from BLS OEWS, QCEW and NCES IPEDS).",
    "formd_states.csv": "New SEC Form D offerings by place, year and industry group: offerings, companies, amounts sought and reported sold, population (IPBA from SEC Form D data sets).",
    "formd_nd.csv": "North Dakota Form D offerings by year and industry group (IPBA from SEC Form D data sets).",
    "owners_demographics.csv": "Employer firms by majority owners' sex, ethnicity, race and veteran status, ND, peers and US, all industries and by sector, 2017 and 2023, as shares of classifiable firms with approximate 90% margins (IPBA from Census Annual Business Survey).",
    "innovation_scorecard.csv": "Innovation measures in five fields for ND, the peer states and the US, with ND's rank among the five states, ratio to the US and change (IPBA from NSF HERD, BERD and Federal Funds, BEA, PatentsView, SBIR.gov, Census BFS, BDS and ACS, SEC Form D, BLS QCEW and OEWS, NCES IPEDS).",
    "innovation_trends.csv": "Innovation measures by place and year: university and federal R&D, patents, SBIR/STTR dollars, high-propensity business applications, opening rate, young-firm jobs and Form D offerings (IPBA).",
    "survey_results.csv": "IPBA North Dakota Business Survey: weighted results by quarter for the state, size classes, "
                          "industry groups, East and West, and the 8 planning regions (last 4 quarters pooled), with 90% "
                          "margins of error; withheld where fewer than 30 businesses answered. test_data = True means "
                          "the survey has not been fielded and the numbers are made up (IPBA).",
    "survey_fielding.csv": "IPBA North Dakota Business Survey: invitations, responses and response rate by quarter, and "
                           "the check that weights add up to the County Business Patterns count of locations (IPBA).",
    "rd_states.csv": "Business R&D performed in each state (2023) and federal R&D obligations by state (FY2016-24), $ millions; US = 50 states and DC (NSF NCSES).",
    "survival_sector.csv": "New firms still operating 1, 3 and 5 years after birth, by state and sector, pooled over five "
                           "birth years (IPBA from Census BDS).",
    "survival_trend.csv": "New firms still operating 1, 3 and 5 years after birth, all industries, by birth year (IPBA "
                          "from Census BDS).",
    "owners_age.csv": "Owners of employer firms by age and by year they acquired the business, ND, peers and US, by "
                      "sector, with 90% margins (Census Annual Business Survey).",
    "owners_55plus.csv": "Owners aged 55 or older, % of owners, by place, year and sector, with 90% margins (IPBA from "
                         "Census ABS).",
    "target_industries_peers.csv": "ND Commerce's targeted industries measured the same way in ND and the peer states: "
                                   "jobs, location quotient, job change, pay, withheld codes (IPBA from BLS QCEW).",
    "sbir_states.csv": "SBIR/STTR awards, companies, dollars per resident and Phase I to II conversion, ND, peers and "
                       "US (IPBA from SBIR.gov).",
    "sbir_nd_agency.csv": "North Dakota SBIR/STTR awards by agency and phase (SBIR.gov).",
    "sbir_nd_region.csv": "North Dakota SBIR/STTR awards by planning region, from the award city (IPBA from SBIR.gov).",
    "case_va_freight.csv": "Case study: farm products leaving ND for other states and abroad by year, raw or processed, "
                           "tons and value (FAF 5.7.1).",
    "case_oil_counties.csv": "Case study: ND counties by share of private jobs in mining, oil and gas, and whether each is a core oil county (BLS QCEW).",
    "case_oil_quarterly.csv": "Case study: private jobs by quarter for the core oil counties and the rest of ND, with the WTI price and ND oil production (BLS QCEW, EIA).",
    "case_oil_annual.csv": "Case study: establishments, openings and closings by year, core oil counties and the rest of ND (Census BDS).",
    "case_oil_sales.csv": "Case study: taxable sales by quarter, core oil counties and the rest of ND (ND Tax Commissioner).",
    "case_oil_findings.csv": "Case study: key findings computed from the tables above, with their labels (IPBA).",
    "case_va_trend.csv": "Case study, value-added agriculture: jobs, pay and location quotient by year, with all ND "
                         "private jobs (BLS QCEW; IPBA coding of ND Commerce's definition).",
    "case_va_codes.csv": "Case study, value-added agriculture: food, beverage and fuel ethanol manufacturing (BLS QCEW).",
    "case_va_exports.csv": "Case study, value-added agriculture: estimated ND farm exports by commodity and year, "
                           "million current dollars (USDA ERS).",
    "case_va_findings.csv": "Case study, value-added agriculture: key findings with their labels (IPBA).",
    "case_adv_groups.csv": "Case study, advanced industries: advanced manufacturing and technology-based business by "
                           "year, with ND private pay (BLS QCEW; Brookings advanced industries).",
    "case_adv_codes.csv": "Case study, advanced industries: each industry code in the two groups (BLS QCEW).",
    "case_adv_patents.csv": "Case study, advanced industries: utility patents by first-named inventor's county and "
                            "planning region, complete grant years (PatentsView).",
    "case_adv_findings.csv": "Case study, advanced industries: key findings with their labels (IPBA).",
    "case_retail_counties.csv": "Case study, main street retail: pull factor, retail stores and residents by county, hub "
                                "or other county (Census Economic Census, CBP, NES, ACS).",
    "case_retail_sales.csv": "Case study, main street retail: taxable sales by quarter, hub counties and other counties "
                             "(ND Tax Commissioner).",
    "case_retail_findings.csv": "Case study, main street retail: key findings with their labels (IPBA).",
    "county_peers.csv": "For each ND county, the five most similar US counties outside ND (rank 1 = closest), the "
                        "distance on weighted z-scores and match quality (close, fair, loose).",
    "county_peer_profiles.csv": "Profiles of ND counties, their peers and the US county median: population, density, "
                                "age, income, unemployment, business density, pay, home value and industry mix (mix_ = "
                                "% of private jobs by NAICS sector).",
    "fiscal_outlook.csv": "North Dakota general fund revenue by source and biennium: actual, official forecast, IPBA "
                          "estimate and oil-price scenarios, $ millions (read from ND Fiscal and Economic Watch).",
    "outlook_region.csv": "Private jobs by planning region: actual quarters and the 4-quarter statistical outlook with "
                          "80% ranges (lo, hi); kind = actual or forecast.",
    "outlook_region_meta.csv": "Region outlook summary: model chosen, average private jobs last and next 4 quarters, 80% "
                               "range, backtest error and out-of-sample range coverage.",
    "laus_monthly.csv": "Labor force, unemployed and unemployment rate by county, planning region and state, monthly, "
                        "not seasonally adjusted (BLS Local Area Unemployment Statistics).",
    "energy_monthly.csv": "North Dakota crude oil production, the price ND producers received and the WTI oil price, monthly (EIA).",
    "population_annual.csv": "Resident population by geography and year, July 1 estimates (Census Population Estimates).",
    "qcew_annual.csv": "Establishments, jobs, wages, average pay and location quotients by area, year, ownership and "
                       "industry (BLS QCEW); own 0 = all, 5 = private.",
    "scorecard.csv": "ND and peer states on key measures, with ND's rank and, for survey measures, significance tests.",
    "shift_share.csv": "Shift-share of ND private job change by industry: national, industry mix and local parts (IPBA).",
    "taxable_sales_county.csv": "Taxable sales and purchases by county and filing quarter, current dollars (ND Tax "
                                "Commissioner). About half the base is reported by out-of-state and consolidated "
                                "filers and is not assigned to a county.",
    "taxable_sales_industry.csv": "Taxable sales and purchases by industry and filing quarter, current dollars (ND Tax Commissioner).",
}

COLUMNS = {
    # business support insights
    "births": "New firms (aged 0) in the birth years", "survivors": "Of those, firms still operating after the horizon",
    "horizon": "Years after birth", "cohort": "Year the firms were born", "cohort_from": "First birth year pooled",
    "cohort_to": "Last birth year pooled", "survival": "Firms still operating after the horizon, % of births",
    "sector_name": "NAICS sector name", "question": "ABS owner question (owner age, or year the owner acquired the business)",
    "owners": "Owners of respondent employer firms", "share_moe90": "90% margin of error of the share, percentage points",
    "share_55plus": "Owners aged 55 or older, % of owners reporting", "owners_55plus": "Owners aged 55 or older",
    "share_55plus_moe90": "90% margin of error of the 55-or-older share, points",
    "flag_withheld": "True when 25% or more of the group's establishments are in withheld codes",
    "pay_vs_us": "Average pay compared with the same codes in the US, %", "dollars": "Award dollars",
    "phase2": "Phase II awards", "awards_per_100k_yr": "Awards per 100,000 residents a year",
    "dollars_per_resident_yr": "Award dollars per resident a year", "year_from": "First year of the window",
    "year_to": "Last year of the window", "p1_firms": "Companies with a first Phase I award in the conversion window",
    "p2_firms": "Of those, companies with a Phase II award within 3 years",
    "conversion": "Phase I companies winning a Phase II within 3 years, %", "conv_from": "First year of the conversion window",
    "conv_to": "Last year of the conversion window", "agency": "Federal agency making the award",
    "occ_code": "SOC occupation code", "est_jobs": "Estimated ND jobs (national staffing pattern on ND jobs)",
    "share_of_group": "Share of the targeted industry's estimated jobs, %",
    "nd_median_wage": "ND median annual wage for the occupation, all industries ($)",
    "nd_jobs_all": "ND jobs in the occupation, all industries", "soc_major": "SOC major group (2-digit)",
    "rank": "Rank within the targeted industry", "oews_year": "OEWS May estimates year",
    "major_title": "SOC major group title", "nd_jobs_major": "ND jobs in the major group, all industries",
    "nd_awards_linked": "ND graduates a year linked to the major group (NCES-BLS crosswalk)",
    "awards_per_1k_jobs": "ND graduates linked a year per 1,000 ND jobs in the major group",
    "ipeds_year": "IPEDS completions year (academic year ending)", "offerings": "New Form D offerings",
    "companies": "Distinct issuing companies", "sold": "Amount sold as first reported ($)",
    "sought": "Total offering amount sought ($; indefinite left blank)",
    "operating": "True for operating companies (not pooled investment funds)",
    "dimension": "Owner characteristic (sex, ethnicity, race, veteran status)",
    "detail": "True for a detailed race (races can overlap)", "firms_rse": "Relative standard error of firms, %",
    "classified_firms": "Firms whose owners could be classified on this characteristic",
    "reliable": "True when the share rests on 20+ firms with a relative standard error of 50% or less",
    "measure": "Name of the measure", "nd_rank": "North Dakota's rank among the five states (1 = highest)",
    "states_ranked": "States with a value for the measure", "nd_vs_us": "North Dakota value divided by the US value",
    "nd_change_pct": "Change in North Dakota's value over the change period, %",
    "change_period": "Years of the change", "ND": "North Dakota", "MN": "Minnesota", "MT": "Montana",
    "SD": "South Dakota", "WY": "Wyoming", "US": "United States",
    "venture": "True for company-building raises (operating companies outside real estate and finance)",
    "population": "Residents (Census population estimates)",
    # case study
    "four_quarter_real": "Total of the last 4 quarters in dollars of the year to 2019 Q4 (GDP price index)",
    "kind": "Raw or processed farm products",
    "index": "Index (base period = 100, named on the page)", "mining_jobs": "Jobs in mining, oil and gas (NAICS 21)",
    "mining_published": "True when BLS published the county's mining figure",
    "mining_share": "Mining, oil and gas share of private jobs (0-1)", "core": "True for a core oil county",
    "avg4": "Average of the last 4 quarters", "yoy_pct": "Change from the same quarter a year earlier, %",
    "nd_crude_kbd": "ND crude oil production, thousand barrels a day", "wti_usd": "WTI crude oil price, $ a barrel",
    "entry_rate": "Establishment openings as % of average establishments",
    "exit_rate": "Establishment closings as % of average establishments",
    "four_quarter": "Total of the last 4 quarters", "key": "Finding identifier",
    "private_avg_pay": "Average annual pay, all ND private jobs, same year ($)",
    "va_jobs": "Value-added agriculture jobs (sum of published codes)", "va_avg_pay": "Value-added agriculture average pay ($)",
    "va_lq": "Value-added agriculture location quotient", "va_codes_withheld": "Value-added agriculture codes BLS withheld",
    "va_index": "Value-added agriculture jobs, index (first year = 100)",
    "private_index": "All ND private jobs, index (first year = 100)",
    "retail_sales_k": "Retail sales, 2022 Economic Census (thousand $)",
    "retail_expected_k": "Retail sales the county's share of ND household income predicts (thousand $)",
    "restaurant_pull_factor": "Pull factor for restaurants and bars (NAICS 722)",
    "retail_stores": "Retail establishments with employees, NAICS 44-45 (County Business Patterns)",
    "retail_nonemployers": "Retail businesses without employees, NAICS 44-45 (Nonemployer Statistics)",
    "stores_per_1000": "Retail establishments with employees per 1,000 residents",
    "counties": "Number of counties in the group with data",
    "scope": "Which counties are counted: all counties, or all except the oil case's core oil counties",
    # freight
    "flow": "Direction of the freight flow relative to North Dakota", "sctg2": "Goods code (SCTG 2-digit)",
    "mode": "Mode of transport on the US part of the trip",
    "tons_k": "Thousand short tons", "value_m": "Value, million 2017 dollars",
    "current_value_m": "Value, million current dollars (2017: 2017 dollars; blank for forecasts)",
    "tmiles_m": "Million ton-miles (US part of the trip)", "projected": "True for FAF forecast years (2030-2050)",
    "partner": "Other end of the flow: US state or world region", "tons_start_k": "Thousand tons starting in the place",
    "tons_end_k": "Thousand tons ending in the place", "value_start_m": "Value starting in the place, million 2017 $",
    "value_end_m": "Value ending in the place, million 2017 $",
    # targeted industries
    "group": "Targeted industry (ND Commerce's name)", "codes": "Number of NAICS codes in the group",
    "codes_present": "Codes with any ND establishments that year", "codes_withheld": "Codes BLS withheld for ND",
    "estabs_withheld": "Establishments in withheld codes", "estabs_withheld_share": "Share of the group's establishments in withheld codes (0-1)",
    "share_private_jobs": "Share of all ND private jobs (0-1)", "us_avg_pay": "US average annual pay in the same codes, dollars",
    "from_year": "Start year of the job change (same NAICS edition)", "growth_jobs_from": "Jobs at the start, codes published in both years",
    "growth_jobs_to": "Jobs at the end, same codes", "growth_codes": "Codes used for the job change",
    "headline": "True for the year the page shows (newest year with full detail)",
    "proxy": "True when the group is a proxy (no NAICS code matches the definition)",
    "commerce_definition": "ND Commerce's definition, quoted (Operation Intern Guidelines, 2025-27)",
    "ipba_codes": "How IPBA assigns industry codes to the definition", "naics_2017_code": "Matching NAICS 2017 code, used before 2022",
    "geo": "Two-letter state code, or US", "code": "Geography or industry code", "year": "Calendar year",
    "date": "First day of the month or quarter", "quarter": "First day of the quarter", "month": "First day of the month",
    "value": "Value of the measure (units in the table description or catalog)", "area": "BLS area code (state FIPS + 000, or county FIPS)",
    "industry": "NAICS sector code (10 = all industries)", "own": "Ownership: 0 all, 1-3 government, 5 private",
    "estabs": "Establishments (business locations)", "firms": "Firms", "emp": "Jobs (employment)", "jobs": "Jobs",
    "wages": "Total wages, dollars", "avg_pay": "Average annual pay per job, dollars",
    "lq_jobs": "Location quotient of jobs (US = 1)", "lq": "Location quotient of jobs (US = 1)",
    "lq_estabs": "Location quotient of establishments", "disclosed": "False when BLS withheld the value",
    "population": "Residents", "county": "County name", "region": "ND planning region", "name": "Name",
    "level": "Geography level", "sa": "Seasonal adjustment: S adjusted, U not adjusted", "series": "Series code",
    "naics_sector": "NAICS sector (TOTAL = all)", "lo": "Low end of the 80% range", "hi": "High end of the 80% range",
    "kind": "actual or forecast", "growth": "Yearly job growth, %", "quadrant": "Cluster position",
    "base_jobs": "Export-oriented jobs: jobs x (1 - 1/LQ) where LQ > 1", "start": "First year", "end": "Last year",
    "national": "Change if jobs grew at the US private rate", "industry_mix": "Change from the industry's US growth vs all US jobs",
    "local": "Change from local growth vs US industry growth", "change": "Actual change",
    "jobs_start": "Jobs in the first year", "jobs_end": "Jobs in the last year",
    "improving_share": "% of indicators better than a year earlier", "indicators": "Indicators counted",
    "timely_share": "% of monthly and quarterly indicators better than a year earlier",
    "timely_indicators": "Monthly and quarterly indicators counted", "patents": "Utility patents (fractional by inventor)",
    "per_100k": "Patents per 100,000 residents", "pce_price": "PCE price index (2017 = 100)",
    "gdp_price": "GDP price index (2017 = 100)", "labor_force": "Residents working or looking for work",
    "preliminary": "True when BLS marks the month preliminary", "nd_crude_kbd": "ND crude oil production, thousand barrels a day",
    "wti_usd": "WTI spot price, dollars a barrel", "nd_price_usd": "North Dakota crude oil first purchase price (paid to producers), dollars a barrel",
    "openings": "Job openings, thousands", "openings_rate": "Openings / (jobs + openings), %",
    "hires_rate": "Hires as a % of jobs", "quits_rate": "Quits as a % of jobs",
    "occupation": "Major occupation group (Standard Occupational Classification)", "nd_jobs": "ND jobs",
    "nd_share": "ND share of all jobs, %", "us_share": "US share of all jobs, %",
    "nd_median_wage": "ND median annual wage, dollars", "us_median_wage": "US median annual wage, dollars",
    "wage_ratio": "ND median wage / US median wage", "unitid": "IPEDS institution ID", "institution": "Institution name",
    "ndus": "True for North Dakota University System institutions",
    "us_jobs": "US jobs", "excluded_counties": "Counties left out of the region series (withheld by BLS in some quarters)", "excluded_share_pct": "Their share of the region's private jobs, latest published quarter, %", "biennium": "Two-year state budget period (July to June)",
    "value_m": "$ millions", "estimated_share": "Planning regions: % of the jobs figure estimated for withheld counties", "fips": "County FIPS code", "rank": "Peer rank (1 = most similar)",
    "peer_fips": "Peer county FIPS code", "peer": "Peer county and state", "distance": "Distance on weighted z-scores",
    "match": "Match quality: close, fair or loose", "state": "State postal code", "land_sqmi": "Land area, square miles",
    "median_income": "Median household income, dollars", "home_value": "Median home value, dollars",
    "private_jobs": "Private-sector jobs (County Business Patterns for peer profiles; BLS QCEW for the case study)", "estabs_per_1k": "Employer establishments per 1,000 residents",
    "nonemployers_per_1k": "Nonemployer businesses per 1,000 residents", "pay_per_job": "Annual payroll per private job, dollars",
    "employer_estabs_per_1k": "Employer establishments per 1,000 residents", "last_actual": "Latest quarter of data", "jobs_last_year": "Average jobs, last 4 quarters",
    "next_year": "Outlook: average jobs, next 4 quarters", "next_lo": "80% range, low (average of next 4 quarters)",
    "next_hi": "80% range, high (average of next 4 quarters)", "backtest_error_pct": "Average backtest error, %",
    "coverage_pct": "Share of past outcomes inside the 80% range, %", "coverage_tests": "Number of tested outcomes",
    "estimated_quarters": "Withheld quarters estimated for the series", "measure": "Measure name (see the table description)", "program": "SBA program (7A or 504; All = both)", "fy": "Federal fiscal year (October to September)",
    "loans": "Loans approved", "gross_m": "Amount approved, $ millions", "startups": "Loans to startups or businesses 2 years old or less",
    "chargeoff_loans": "Loans charged off", "chargeoff_m": "Amount charged off, $ millions",
    "withheld": "True when values are withheld (SBA: fewer than 3 loans; BLS: to protect an employer)", "period": "Fiscal years covered", "hs2": "Harmonized System chapter (2-digit)", "product": "Product group (HS chapter)",
    "country_code": "Census country code", "country": "Destination country", "months": "Months covered (12 = full year)",
    "manufactured": "Manufactured goods exports, $ millions", "non_manufactured": "Farm, mining and other raw goods exports, $ millions",
    "reexports": "Reexports of foreign goods, $ millions", "total": "Total goods exports, $ millions",
    "commodity": "Farm commodity group (USDA ERS) or goods (FAF, SCTG 2-digit name)", "line": "BEA table line number", "category": "Spending category",
    "depth": "Indent level of the category (0 = total)", "returns": "Individual income tax returns",
    "agi_k": "Adjusted gross income, thousands of dollars", "business_returns": "Returns with business income or loss",
    "business_income_k": "Business net income less loss, thousands of dollars",
    "farm_returns": "Returns with farm income or loss",
    "business_share": "Returns with business income, % of returns", "farm_share": "Farm returns, % of returns",
    "business_income_per_return": "Business net income per return with business income, dollars", "estab": "Stores (establishments)", "naics": "NAICS 2022 code of the store type", "store_type": "Store type",
    "sales_k": "Sales, thousands of dollars", "expected_k": "Expected sales from residents' income, thousands of dollars",
    "pull_factor": "Actual / expected sales (1 = balanced)", "gap_k": "Expected - actual, thousands of dollars (+ = leakage)",
    "estimated": "True when withheld county sales were estimated", "cip": "6-digit CIP program code (2020)", "title": "Program title",
    "soc_major": "2-digit SOC major occupation group code (2018)", "share": "Share of each award counted for the group",
    "nd_awards": "Awards at ND institutions", "ndus_awards": "Awards at NDUS institutions",
    "us_awards": "Awards at US institutions (50 states and DC)", "cip2": "2-digit CIP family code",
    "field": "Field of study (CIP family); in innovation_scorecard.csv, the field of innovation the measure belongs to", "awards": "Degrees and certificates awarded (first majors)",
    "nd_rank": "ND rank among the five states (1 = best)",
    "nd_rank_significant": "ND rank counting only states significantly better at 90%",
    "sampling_error": "True for survey (ACS) measures", "higher_is": "Whether a higher value is better",
    # geography and identifiers
    "geo_id": "Census geography identifier", "place": "Place: ND (statewide), a planning region or a county",
    "id": "Indicator or series identifier (see indicators_catalog.csv)", "sector": "NAICS sector code (total = all sectors)",
    "description": "Industry name as published by BEA", "measure": "Measure name, or for bea_gdp.csv 'current' or 'real'",
    "label": "Name of the series", "theme": "Theme the indicator belongs to", "indicator": "Indicator name",
    "owner": "Patent owner type (business or organization, government, individual, none recorded)", "check": "What is checked",
    "tax": "Tax", "model": "Outlook model", "series": "Series identifier",
    # ACS
    "median_age": "Median age of residents, years", "median_household_income": "Median household income, dollars",
    "per_capita_income": "Income per resident, dollars", "aggregate_income": "Total income of all residents, dollars",
    "median_home_value": "Median value of owner-occupied homes, dollars",
    "civilian_labor_force": "Residents 16 and over working or looking for work", "unemployed": "Residents looking for work",
    "unemployment_rate": "Unemployed as a % of the civilian labor force",
    "median_household_income_min": "Regions only: lowest county median household income in the region",
    "median_household_income_max": "Regions only: highest county median household income in the region",
    # BDS
    "estabs_entry": "Establishments opened during the year", "estabs_entry_rate": "Openings as a % of establishments",
    "estabs_exit": "Establishments closed during the year", "estabs_exit_rate": "Closings as a % of establishments",
    "job_creation_births": "Jobs created by newly opened establishments",
    "job_destruction_deaths": "Jobs lost at establishments that closed",
    "net_job_creation": "Jobs created minus jobs lost", "net_job_creation_rate": "Net job creation as a % of jobs",
    "age": "Firm age in years (Census BDS age class)", "young": "True for firms 0 to 5 years old",
    # CBP and Nonemployer
    "size": "Employment size class (employees per establishment)", "order": "Sort order of the size class",
    "employer_estabs": "Establishments with paid employees", "employees": "Paid employees in mid-March",
    "employee_noise": "Census noise flag for employees: G low, H moderate, J high (added to protect businesses)",
    "payroll_k": "Annual payroll, thousands of dollars", "nonemployers": "Businesses with no paid employees",
    "nonemployer_receipts_k": "Receipts of nonemployer businesses, thousands of dollars",
    # indicators and diffusion
    "unit": "Unit of the indicator", "freq": "Frequency: M monthly, Q quarterly, A annual",
    "higher_is_good": "True when a rise counts as an improvement", "format": "Display format of the value",
    "source": "Source agency and data set", "latest": "Date of the latest value",
    "year_earlier": "Value a year before the latest", "change_pct": "% change from a year earlier",
    "improving": "True when better than a year earlier", "timely": "True for monthly and quarterly indicators",
    # dynamics
    "latest_year": "Latest year of data", "long": "Long-run average yearly growth, %", "long_period": "Years of the long run",
    "medium": "Medium-run average yearly growth, %", "medium_period": "Years of the medium run",
    "short": "Latest yearly growth, %", "short_period": "Years of the latest change",
    "phase": "Phase of ND's economy", "years": "Years in the phase",
    # outlooks
    "path": "Growth path (not a forecast)", "growth_pct": "Yearly growth assumed on the path, %",
    "mean_error_pct": "Mean absolute error in backtests, % of actual", "median_error_pct": "Median absolute error in backtests, %",
    "origins": "Number of backtest starting points",
    # input-output model (money in millions of dollars)
    "output": "Output (sales) supported, $ millions", "labor_income": "Labor income supported, $ millions",
    "value_added": "Value added (GDP) supported, $ millions", "typeI_output": "Output supported without household spending (Type I), $ millions",
    "state_taxes": "State taxes supported, $ millions", "local_taxes": "Local taxes supported, $ millions",
    "output_musd": "Industry output in the place, $ millions", "ND_output_musd": "Industry output in ND, $ millions",
    "pay_ratio_ND": "ND average pay in the industry relative to the US", "productivity_ND": "ND output per job relative to the US",
    "IPBA": "IPBA model value", "StateIO": "EPA StateIO value", "US": "US value", "benchmark": "Benchmark value or range",
    "note": "Note", "delta": "FLQ delta parameter tried",
    "ND weighted mean Type I output multiplier": "IPBA mean Type I output multiplier, weighted by output",
    "StateIO weighted mean": "EPA StateIO mean Type I output multiplier, weighted by output",
    "mean difference": "IPBA minus StateIO, mean", "mean absolute difference": "Mean absolute difference, IPBA vs StateIO",
    "correlation": "Correlation of IPBA and StateIO multipliers across industries",
    "amount_musd": "Tax collected, $ millions", "base": "Base the tax is related to (household income, GDP, oil value)",
    "data_year": "Year of the tax data", "base_musd": "Size of the base, $ millions", "rate": "Tax / base (effective rate)",
    "pi_share_of_labor_income": "Personal income per dollar of labor income",
    "household_sales_share": "Share of sales tax paid by households",
    # patents and scorecard
    "patents_any_nd_inventor": "Patents with at least one ND inventor (whole counts)",
    "complete_year": "False when the year is not yet complete in the data", "period": "Period the measure covers",
    "ND": "North Dakota value", "MN": "Minnesota value", "MT": "Montana value", "SD": "South Dakota value",
    "WY": "Wyoming value",
    "rank_clear": "For survey estimates: False when ND's rank is within the margin of error of a neighboring state",
    "pop_25plus": "Adults 25 and older", "bachelors_plus": "Adults 25 and older with a bachelor's degree or higher",
    "bachelors_share": "% of adults 25 and older with a bachelor's degree or higher", "households": "Households",
    "broadband_households": "Households with a broadband internet subscription of any type",
    "broadband_share": "% of households with a broadband internet subscription",
    "domain_type": "Group the result describes: state, size, industry, area (East/West) or region_4q (planning region, "
                   "last 4 quarters pooled)",
    "domain": "Name of the group", "section": "Survey question group (for example Last 3 months, Constraints)",
    "stat": "net = net balance (% increase - % decrease); index = outlook index (-100 to +100); share = % of businesses; "
            "_emp = weighted by jobs",
    "moe": "90% margin of error (same units as the value)", "n": "Businesses answering",
    "suppressed": "True when withheld (fewer than 30 answers, or one business would carry over half the weight)",
    "test_data": "True when the numbers are made-up test data (survey not yet fielded)",
    "invited": "Businesses invited", "ineligible": "Invited businesses found closed or out of scope",
    "responses": "Completed responses", "panel_responses": "Responses from businesses that answered in an earlier quarter",
    "new_responses": "Responses from businesses answering for the first time",
    "response_rate": "Responses / (invited - ineligible), %",
    "weighted_total": "Sum of the weights (locations represented)",
    "frame_total": "County Business Patterns count of locations with employees (the weighting target)",
}

_SUFFIX = {"_type1": "Type I multiplier (suppliers only)", "_type2": "Type II multiplier (suppliers and household spending)",
           "_per_million_type2": "Type II effect per $1 million of new sales"}


def columns_note(col):
    if col.endswith("_moe"):
        return "90% margin of error of " + col[:-4].replace("_", " ")
    if col.endswith("_significant"):
        return f"{col.split('_')[0]} differs significantly from ND at 90%"
    if col in COLUMNS:
        return COLUMNS[col]
    for suf, case in (("_low", "low"), ("_high", "high")):
        if col.endswith(suf) and col[:-len(suf)] in ("jobs", "labor_income", "value_added", "output", "state_taxes",
                                                     "local_taxes"):
            return (f"{col[:-len(suf)].replace('_', ' ').capitalize()} supported, {case} case of the impact model's "
                    "range (local buying and household spending moved together)")
    if col.startswith("direct_"):
        return "In the industry itself: " + col[7:].replace("_", " ") + " ($ millions, except jobs)"
    if col.startswith("mix_"):
        return f"% of private jobs in NAICS sector {col[4:]} (County Business Patterns)"
    if col.startswith("jobs_"):
        return "Jobs in " + col[5:]
    for suf, text in _SUFFIX.items():
        if col.endswith(suf):
            return f"{col[:-len(suf)].replace('_', ' ').capitalize()}: {text}"
    return ""


def published():
    return sorted(f for f in OUT.glob("*.csv") if "implan" not in f.name.lower())


def dictionary():
    import pandas as pd
    rows = []
    for f in published():
        cols = pd.read_csv(f, nrows=0).columns
        for c in cols:
            rows.append({"file": f.name, "table": TABLES.get(f.name, ""), "column": c, "meaning": columns_note(c)})
    return pd.DataFrame(rows)


def zip_bytes(citation):
    """All published tables, the data dictionary and a short read-me, in one ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in published():
            z.write(f, f.name)
        z.writestr("data_dictionary.csv", dictionary().to_csv(index=False))
        z.writestr("README.txt", "ND Business and Innovation Watch: published data tables.\n\n"
                   f"Downloaded {date.today():%B %d, %Y}. Sources and dates are listed on the About the data page.\n"
                   "Withheld values are empty, not zero. Survey (ACS) estimates come with 90% margins of error.\n\n"
                   f"Suggested citation:\n{citation}\n")
    return buf.getvalue()
