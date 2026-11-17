"""Shared settings: folders, geography, industry codes and source addresses.

All sources are free public files that need no API key. The Census API (api.census.gov) now asks
for a key, so Census data come from the Census bulk download site (www2.census.gov) instead.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"        # downloads exactly as received (never edited)
LIVE = ROOT / "data" / "live"      # short-lived cache of files that change often
OUT = ROOT / "outputs"             # tidy tables the dashboard reads
for _d in (RAW, LIVE, OUT):
    _d.mkdir(parents=True, exist_ok=True)

USER_AGENT = "ND-Business-Innovation-Watch/0.1 (IPBA research dashboard)"

# ---------------------------------------------------------------- geography
STATE_FIPS = "38"
PEERS = {"ND": "38", "MN": "27", "MT": "30", "SD": "46", "WY": "56"}       # postal code -> state FIPS
PEER_NAMES = {"ND": "North Dakota", "MN": "Minnesota", "MT": "Montana", "SD": "South Dakota",
              "WY": "Wyoming", "US": "United States"}

COUNTIES = {
    "001": "Adams", "003": "Barnes", "005": "Benson", "007": "Billings", "009": "Bottineau", "011": "Bowman",
    "013": "Burke", "015": "Burleigh", "017": "Cass", "019": "Cavalier", "021": "Dickey", "023": "Divide",
    "025": "Dunn", "027": "Eddy", "029": "Emmons", "031": "Foster", "033": "Golden Valley", "035": "Grand Forks",
    "037": "Grant", "039": "Griggs", "041": "Hettinger", "043": "Kidder", "045": "LaMoure", "047": "Logan",
    "049": "McHenry", "051": "McIntosh", "053": "McKenzie", "055": "McLean", "057": "Mercer", "059": "Morton",
    "061": "Mountrail", "063": "Nelson", "065": "Oliver", "067": "Pembina", "069": "Pierce", "071": "Ramsey",
    "073": "Ransom", "075": "Renville", "077": "Richland", "079": "Rolette", "081": "Sargent", "083": "Sheridan",
    "085": "Sioux", "087": "Slope", "089": "Stark", "091": "Steele", "093": "Stutsman", "095": "Towner",
    "097": "Traill", "099": "Walsh", "101": "Ward", "103": "Wells", "105": "Williams",
}

# The eight North Dakota planning regions (regional councils), named after their hub city.
# Not the same as the SBDC center areas, which group some counties differently.
REGIONS = {
    "Region 1 (Williston)": ["Divide", "McKenzie", "Williams"],
    "Region 2 (Minot)": ["Bottineau", "Burke", "McHenry", "Mountrail", "Pierce", "Renville", "Ward"],
    "Region 3 (Devils Lake)": ["Benson", "Cavalier", "Eddy", "Ramsey", "Rolette", "Towner"],
    "Region 4 (Grand Forks)": ["Grand Forks", "Nelson", "Pembina", "Walsh"],
    "Region 5 (Fargo)": ["Cass", "Ransom", "Richland", "Sargent", "Steele", "Traill"],
    "Region 6 (Jamestown)": ["Barnes", "Dickey", "Foster", "Griggs", "LaMoure", "Logan", "McIntosh", "Stutsman", "Wells"],
    "Region 7 (Bismarck)": ["Burleigh", "Emmons", "Grant", "Kidder", "McLean", "Mercer", "Morton", "Oliver",
                            "Sheridan", "Sioux"],
    "Region 8 (Dickinson)": ["Adams", "Billings", "Bowman", "Dunn", "Golden Valley", "Hettinger", "Slope", "Stark"],
}
COUNTY_REGION = {c: r for r, cs in REGIONS.items() for c in cs}

# ---------------------------------------------------------------- industries (NAICS 2-digit sectors)
SECTORS = {
    "11": "Agriculture, forestry, fishing and hunting", "21": "Mining, quarrying, and oil and gas extraction",
    "22": "Utilities", "23": "Construction", "31-33": "Manufacturing", "42": "Wholesale trade",
    "44-45": "Retail trade", "48-49": "Transportation and warehousing", "51": "Information",
    "52": "Finance and insurance", "53": "Real estate and rental and leasing",
    "54": "Professional, scientific, and technical services", "55": "Management of companies and enterprises",
    "56": "Administrative and support and waste management", "61": "Educational services",
    "62": "Health care and social assistance", "71": "Arts, entertainment, and recreation",
    "72": "Accommodation and food services", "81": "Other services (except public administration)",
}
SHORT = {
    "11": "Agriculture", "21": "Mining, oil and gas", "22": "Utilities", "23": "Construction",
    "31-33": "Manufacturing", "42": "Wholesale trade", "44-45": "Retail trade", "48-49": "Transportation",
    "51": "Information", "52": "Finance and insurance", "53": "Real estate", "54": "Professional services",
    "55": "Management of companies", "56": "Admin and support", "61": "Education", "62": "Health care",
    "71": "Arts and recreation", "72": "Accommodation and food", "81": "Other services",
}

# ---------------------------------------------------------------- source addresses (no key needed)
BFS_URL = "https://www.census.gov/econ/bfs/csv/bfs_monthly.csv"
BDS_YEAR = 2023
BDS_BASE = "https://www2.census.gov/programs-surveys/bds/tables/time-series/{y}/"
QCEW_URL = "https://data.bls.gov/cew/data/api/{y}/a/area/{area}.csv"
QCEW_FIRST_YEAR = 2015
BEA_URL = "https://apps.bea.gov/regional/zip/{}.zip"
ACS_YEAR = 2024                     # 5-year estimates 2020-2024
ACS_URL = ("https://www2.census.gov/programs-surveys/acs/summary_file/{y}/table-based-SF/data/5YRData/"
           "acsdt5y{y}-{t}.dat")
ACS_TABLES = ["b01003", "b01002", "b19013", "b19301","b19313", "b25077", "b23025", "b15003", "b28002"]
CBP_YEAR = 2023
CBP_URL = "https://www2.census.gov/programs-surveys/cbp/datasets/{y}/cbp{yy}co.zip"
NES_YEAR = 2024
NES_URL = "https://www2.census.gov/programs-surveys/nonemployer-statistics/datasets/{y}/historical-datasets/nonemp{yy}co.zip"
TAXABLE_SALES_URL = "https://www.tax.nd.gov/sites/default/files/documents/Data/taxable-sales-and-purchases-excel.xlsx"
