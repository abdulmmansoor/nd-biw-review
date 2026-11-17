"""Step: businesses by county and industry - employer establishments (CBP) and nonemployer businesses (NES).

 - County Business Patterns (CBP): establishments with paid employees, mid-March employment and annual
   payroll ($1,000). Since 2017 Census adds noise instead of withholding cells; the noise flag is kept
   (G = under 2%, H = 2-5%, J = 5% or more).
 - Nonemployer Statistics (NES): businesses with no paid employees (mostly self-employed) and their
   receipts ($1,000). Cells flagged 'S' do not meet publication standards and stay blank.
Both come from Census bulk county files (no key), released once a year, kept in data/raw.
Writes outputs/county_business.csv (one row per county x sector, plus 'total') and cbp_sizes.csv
(establishments by employee-size class).
"""
import zipfile
import pandas as pd
from config import CBP_URL, CBP_YEAR, COUNTIES, COUNTY_REGION, NES_URL, NES_YEAR, OUT, RAW, SECTORS
from fetch import get, is_zip, vintage

CBP_CODES = {"------": "total", **{(k.split("-")[0] + "----"): k for k in SECTORS}}
NES_CODES = {"00": "total", **{k: k for k in SECTORS}}


def zipped_csv(url, path):
    z = zipfile.ZipFile(get(url, path, check=is_zip, timeout=600))
    return pd.read_csv(z.open(z.namelist()[0]), dtype=str)


SIZES = {"n<5": "1-4", "n5_9": "5-9", "n10_19": "10-19", "n20_49": "20-49", "n50_99": "50-99",
         "n100_249": "100-249", "n250_499": "250-499", "n500_999": "500-999", "n1000": "1,000+"}


def cbp_raw():
    yy = str(CBP_YEAR)[2:]
    d = zipped_csv(CBP_URL.format(y=CBP_YEAR, yy=yy), RAW / "cbp" / f"cbp{yy}co.zip")
    return d[(d.fipstate == "38") & d.naics.isin(CBP_CODES)].copy()


def sizes():
    """Employer establishments by number of employees ('N' in the file means none in that class)."""
    d = cbp_raw()
    t = d.melt(id_vars=["fipscty", "naics"], value_vars=list(SIZES), var_name="cls", value_name="estabs")
    t["estabs"] = pd.to_numeric(t.estabs, errors="coerce").fillna(0)
    return pd.DataFrame({"county": t.fipscty.map(COUNTIES).fillna("Statewide, county not known"),
                         "sector": t.naics.map(CBP_CODES), "size": t.cls.map(SIZES), "order": t.cls.map(list(SIZES).index),
                         "estabs": t.estabs})


def cbp():
    d = cbp_raw()
    return pd.DataFrame({"cty": d.fipscty, "sector": d.naics.map(CBP_CODES),
                         "employer_estabs": pd.to_numeric(d.est), "employees": pd.to_numeric(d.emp),
                         "employee_noise": d.emp_nf, "payroll_k": pd.to_numeric(d.ap)})


def nes():
    yy = str(NES_YEAR)[2:]
    d = zipped_csv(NES_URL.format(y=NES_YEAR, yy=yy), RAW / "nes" / f"nonemp{yy}co.zip")
    d = d[(d.ST == "38") & d.NAICS.isin(NES_CODES)].copy()
    bad = d.ESTAB_F.fillna("").eq("S")
    out = pd.DataFrame({"cty": d.CTY, "sector": d.NAICS.map(NES_CODES), "nonemployers": pd.to_numeric(d.ESTAB),
                        "nonemployer_receipts_k": pd.to_numeric(d.RCPTOT)})
    out.loc[bad.values, ["nonemployers", "nonemployer_receipts_k"]] = float("nan")
    return out


def build():
    t = cbp().merge(nes(), on=["cty", "sector"], how="outer")
    t["county"] = t.cty.map(COUNTIES).fillna("Statewide, county not known")   # CBP county 999
    t["region"] = t.county.map(COUNTY_REGION).fillna("")
    return t.drop(columns="cty").sort_values(["county", "sector"])


def main():
    global CBP_YEAR, NES_YEAR
    CBP_YEAR = vintage("cbp", CBP_YEAR, lambda y: CBP_URL.format(y=y, yy=str(y)[2:]))
    NES_YEAR = vintage("nes", NES_YEAR, lambda y: NES_URL.format(y=y, yy=str(y)[2:]))
    t = build()
    t.to_csv(OUT / "county_business.csv", index=False)
    sizes().to_csv(OUT / "cbp_sizes.csv", index=False)
    print(f"    CBP {CBP_YEAR} + NES {NES_YEAR}: {len(t)} county-sector rows")
    return {"cbp": {"name": "County Business Patterns", "publisher": "U.S. Census Bureau",
                    "url": "https://www.census.gov/programs-surveys/cbp.html", "period": str(CBP_YEAR),
                    "latest": str(CBP_YEAR)},
            "nes": {"name": "Nonemployer Statistics", "publisher": "U.S. Census Bureau",
                    "url": "https://www.census.gov/programs-surveys/nonemployer-statistics.html",
                    "period": str(NES_YEAR), "latest": str(NES_YEAR)}}


if __name__ == "__main__":
    main()
