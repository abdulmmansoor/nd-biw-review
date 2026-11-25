"""Step: data for IPBA's input-output model (all public, no key).

 - BEA input-output accounts, summary level (71 industries), Make and Use tables before redefinitions, producers'
   prices. "Before redefinitions" matches the establishment-based industries of QCEW and BEA GDP. Newest year from
   the BEA Data API (src/bea_io_api.py; free key); without a key, or if the API fails, BEA's bulk file
   (AllTablesIO.zip), which BEA stopped updating in September 2024 (tables through 2023). The model year (IO_YEAR)
   is the year of the tables used, and the jobs, pay and GDP inputs follow it.
 - Jobs by model industry for the US and North Dakota: BLS QCEW, 3-digit NAICS, all ownerships, in the model year.
   ND cells BLS does not disclose are filled from the 2-digit sector total minus disclosed industries, split by County
   Business Patterns shares. Industries that share a 3-digit code (e.g. 3361-3363 and 3364-3369) are split with US
   4-digit QCEW shares.
 - Jobs for the 8 planning regions: the state figure for each model industry, shared out to counties with a key:
   QCEW county private jobs by 3-digit NAICS (withheld cells estimated from the county's sector total), QCEW county
   government jobs (government), BEA county farm employment (farms), and transportation jobs (railroads).
   Region = sum of its counties.
 - Productivity: ND output per job is the US figure times ND's GDP per job relative to the US in the matching BEA
   GDP-by-state line. Labor income per job is the US compensation per job times ND's relative QCEW pay.
 - EPA StateIO two-region North Dakota model (2023) for the cross-check, read with the `rdata` package.
Writes outputs/io_industries.csv (one row per model industry: codes, names, jobs by place, coefficients) and keeps
the raw files in data/raw and data/live.
"""
import zipfile
import numpy as np
import pandas as pd
from config import BEA_URL, COUNTIES, COUNTY_REGION, LIVE, OUT, RAW, REGIONS
from fetch import get, is_zip

IO_YEAR = 2023                      # set by tables(): the year of the BEA tables in use
ZIP_YEAR = 2023                     # last year in the bulk file (frozen by BEA in September 2024)
STATEIO_YEAR = 2023                 # EPA StateIO release used for the cross-check
IO_SOURCE = "bulk file"
_TABLES = {}
IO_ZIP = "https://apps.bea.gov/industry/iTables%20Static%20Files/AllTablesIO.zip"
USE = "IOUse_Before_Redefinitions_PRO_1997-{y}_Summary.xlsx"
MAKE = "IOMake_Before_Redefinitions_PRO_1997-{y}_Summary.xlsx"
STATEIO = "https://dmap-data-commons-ord.s3.amazonaws.com/stateio/{}"
STATEIO_FILES = ["TwoRegion_Summary_DomesticUse_pecan_{y}_0.4.0.rds", "TwoRegion_Summary_Make_pecan_{y}_0.4.0.rds",
                 "TwoRegion_Summary_IndustryOutput_pecan_{y}_0.4.0.rds"]

# Model industry -> (QCEW 3-digit NAICS 2022 codes, CBP 3-digit NAICS 2017 codes, BEA GDP-by-state line class,
#                    US 4-digit split codes when a 3-digit code feeds several model industries)
G = "gov"
MAP = {
    "111CA": (["111", "112"], [], "111-112"), "113FF": (["113", "114", "115"], ["113", "114", "115"], "113-115"),
    "211": (["211"], ["211"], "211"), "212": (["212"], ["212"], "212"), "213": (["213"], ["213"], "213"),
    "22": (["221"], ["221"], "22"), "23": (["236", "237", "238"], ["236", "237", "238"], "23"),
    "321": (["321"], ["321"], "321"), "327": (["327"], ["327"], "327"), "331": (["331"], ["331"], "331"),
    "332": (["332"], ["332"], "332"), "333": (["333"], ["333"], "333"), "334": (["334"], ["334"], "334"),
    "335": (["335"], ["335"], "335"), "3361MV": (["336"], ["336"], "3361-3363", ["3361", "3362", "3363"]),
    "3364OT": (["336"], ["336"], "3364-3366,3369", ["3364", "3365", "3366", "3369"]),
    "337": (["337"], ["337"], "337"), "339": (["339"], ["339"], "339"), "311FT": (["311", "312"], ["311", "312"], "311-312"),
    "313TT": (["313", "314"], ["313", "314"], "313-314"), "315AL": (["315", "316"], ["315", "316"], "315-316"),
    "322": (["322"], ["322"], "322"), "323": (["323"], ["323"], "323"), "324": (["324"], ["324"], "324"),
    "325": (["325"], ["325"], "325"), "326": (["326"], ["326"], "326"), "42": (["423", "424", "425"], ["423", "424", "425"], "42"),
    "441": (["441"], ["441"], "44-45"), "445": (["445"], ["445"], "44-45"), "452": (["455"], ["452"], "44-45"),
    "4A0": (["444", "449", "456", "457", "458", "459"], ["442", "443", "444", "446", "447", "448", "451", "453", "454"], "44-45"),
    "481": (["481"], ["481"], "481"), "482": ([], [], "482"), "483": (["483"], ["483"], "483"), "484": (["484"], ["484"], "484"),
    "485": (["485"], ["485"], "485"), "486": (["486"], ["486"], "486"), "487OS": (["487", "488", "492"], ["487", "488", "492"], "487-488,492"),
    "493": (["493"], ["493"], "493"), "511": (["513"], ["511"], "511"), "512": (["512"], ["512"], "512"),
    "513": (["516", "517"], ["515", "517"], "515,517"), "514": (["518", "519"], ["518", "519"], "518-519"),
    "521CI": (["521", "522"], ["521", "522"], "521-522"), "523": (["523"], ["523"], "523"), "524": (["524"], ["524"], "524"),
    "525": (["525"], ["525"], "525"), "HS": ([], [], None), "ORE": (["531"], ["531"], "531"),
    "532RL": (["532", "533"], ["532", "533"], "532-533"), "5411": (["541"], ["541"], "5411", ["5411"]),
    "5415": (["541"], ["541"], "5415", ["5415"]),
    "5412OP": (["541"], ["541"], "5412-5414,5416-5419", ["5412", "5413", "5414", "5416", "5417", "5418", "5419"]),
    "55": (["551"], ["551"], "55"), "561": (["561"], ["561"], "561"), "562": (["562"], ["562"], "562"),
    "61": (["611"], ["611"], "61"), "621": (["621"], ["621"], "621"), "622": (["622"], ["622"], "622"),
    "623": (["623"], ["623"], "623"), "624": (["624"], ["624"], "624"), "711AS": (["711", "712"], ["711", "712"], "711-712"),
    "713": (["713"], ["713"], "713"), "721": (["721"], ["721"], "721"), "722": (["722"], ["722"], "722"),
    "81": (["811", "812", "813", "814"], ["811", "812", "813"], "81"),
    "GFGD": (G, [], None), "GFGN": (G, [], None), "GFE": (G, [], None), "GSLG": (G, [], None), "GSLE": (G, [], None),
}
GSLE_NAICS = ["221", "485", "488", "487"]          # state and local government enterprises (utilities, transit, ports)


# ------------------------------------------------------------------ BEA national tables
def io_zip():
    return zipfile.ZipFile(get(IO_ZIP, LIVE / "bea_io" / "AllTablesIO.zip", max_age_days=30, check=is_zip, timeout=600))


def tables():
    """(use, make, names) for the model year: the BEA Data API's newest year, else the bulk file. Sets IO_YEAR and
    IO_SOURCE; read once per run."""
    global IO_YEAR, IO_SOURCE
    if not _TABLES:
        try:
            import bea_io_api
            use, make, names, year = bea_io_api.tables()
            IO_YEAR, IO_SOURCE = year, "BEA Data API"
        except Exception as e:
            print(f"    BEA API tables not used ({str(e)[:120]}); using the bulk file ({ZIP_YEAR})")
            z = io_zip()
            use, names = read_bea_table(z, USE, ZIP_YEAR)
            make, _ = read_bea_table(z, MAKE, ZIP_YEAR)
            IO_YEAR, IO_SOURCE = ZIP_YEAR, "bulk file"
        _TABLES.update(use=use, make=make, names=names)
    return _TABLES["use"], _TABLES["make"], _TABLES["names"]


def read_bea_table(z, name, year=ZIP_YEAR):
    """A BEA Make or Use sheet as a numeric frame with IO codes as row and column labels ('...' = 0)."""
    d = pd.read_excel(z.open(name.format(y=year)), sheet_name=str(year), header=None)
    cols = d.iloc[5, 2:].tolist()
    body = d.iloc[7:].copy()
    names = dict(zip(body[0], body[1]))
    body = body[body[0].notna() | body[1].isin(["Total Intermediate", "Total Industry Output", "Total Commodity Output",
                                                  "Total Final Uses (GDP)", "Total Value Added"])]
    idx = [c if pd.notna(c) else n for c, n in zip(body[0], body[1])]
    t = body.iloc[:, 2:2 + len(cols)]
    t.columns = [c if pd.notna(c) else f"col{i}" for i, c in enumerate(cols)]
    t.index = idx
    t = t.apply(lambda s: pd.to_numeric(s.replace("...", 0), errors="coerce")).fillna(0.0)
    head_names = dict(zip(d.iloc[5, 2:], d.iloc[6, 2:]))
    return t, {**names, **head_names}


# ------------------------------------------------------------------ jobs
def qcew_area(area, year=None):
    year = year or IO_YEAR
    f = RAW / "qcew" / f"{year}_{area}.csv"
    if not f.exists():
        f = LIVE / "qcew" / f"{year}_{area}.csv"
    return pd.read_csv(f, dtype=str)


def three_digit(d, state):
    """Jobs by ownership x 3-digit NAICS (agglvl 55 state / 15 national), with disclosure flags."""
    lvl = "55" if state else "15"
    x = d[d.agglvl_code == lvl]
    out = pd.DataFrame({"own": x.own_code, "naics": x.industry_code, "jobs": pd.to_numeric(x.annual_avg_emplvl),
                        "hidden": x.disclosure_code.fillna("").eq("N"), "wages": pd.to_numeric(x.total_annual_wages)})
    out.loc[out.hidden, ["jobs", "wages"]] = np.nan
    return out


def fill_hidden(nd, sector_totals, cbp_state):
    """Fill undisclosed ND private 3-digit cells: sector total minus disclosed cells, split by CBP shares."""
    p = nd[nd.own == "5"].copy()
    p["sector"] = p.naics.str[:2].replace({"32": "31", "33": "31", "45": "44", "49": "48"})
    for sec, g in p[p.jobs.isna()].groupby("sector"):
        known = p[(p.sector == sec) & p.jobs.notna()].jobs.sum()
        rest = max(sector_totals.get(sec, np.nan) - known, 0)
        if np.isnan(rest):
            continue
        w = cbp_state.reindex(g.naics).fillna(0)
        # CBP shares only when CBP shows employment for every withheld industry; otherwise an industry CBP also
        # withholds (e.g. petroleum refining) would get no jobs at all, so the rest is split evenly
        w = w / w.sum() if (w > 0).all() else pd.Series(1 / len(g), index=g.naics)
        p.loc[g.index, "jobs"] = rest * w.values
    nd = nd.copy()
    nd.loc[p.index, "jobs"] = p.jobs
    return nd


def withheld_sectors(sector_totals, nd_sec, nd_all, cbp):
    """Statewide private sector totals BLS withholds (in 2025: utilities, transportation, information, arts,
    accommodation and food, other services). The jobs they hold together are known: the published private total
    minus the disclosed sectors. They are shared out by each sector's jobs in the latest earlier year when BLS
    published all of them (County Business Patterns employment if none), with each sector at least the jobs its
    disclosed 3-digit industries already show. Disclosed sectors are left as published."""
    hidden = nd_sec.disclosure_code.fillna("").eq("N").values
    if not hidden.any():
        return sector_totals
    tot = nd_all[(nd_all.agglvl_code == "51") & (nd_all.own_code == "5")].annual_avg_emplvl
    rest = max(float(pd.to_numeric(tot).iloc[0]) - sector_totals[~hidden].sum(), 0)
    secs = list(sector_totals.index[hidden])
    w, basis = None, "County Business Patterns"
    for y in range(IO_YEAR - 1, IO_YEAR - 6, -1):
        try:
            p = qcew_area("38000", y)
        except FileNotFoundError:
            continue
        p = p[(p.agglvl_code == "54") & (p.own_code == "5")]
        p.index = p.industry_code.str[:2]
        p = p.reindex(secs)
        if p.annual_avg_emplvl.notna().all() and not p.disclosure_code.fillna("").eq("N").any():
            w, basis = pd.to_numeric(p.annual_avg_emplvl), f"QCEW {y} shares"
            break
    if w is None:
        sec_of = lambda n: {"32": "31", "33": "31", "45": "44", "49": "48"}.get(n[:2], n[:2])
        w = cbp.assign(sec=cbp.naics.map(sec_of)).groupby("sec").emp.sum().reindex(secs).fillna(0)
    w = w / w.sum() if w.sum() > 0 else pd.Series(1 / len(secs), index=secs)
    est = rest * w
    d3 = nd_all[(nd_all.agglvl_code == "55") & (nd_all.own_code == "5") & ~nd_all.disclosure_code.fillna("").eq("N")]
    sec_of = lambda n: {"32": "31", "33": "31", "45": "44", "49": "48"}.get(n[:2], n[:2])
    floor = pd.to_numeric(d3.annual_avg_emplvl).groupby(d3.industry_code.map(sec_of)).sum().reindex(secs).fillna(0)
    for _ in range(len(secs)):                    # raise sectors below their disclosed industries; rescale the rest
        low = est < floor
        if not low.any():
            break
        est[low] = floor[low]
        free = ~low & (est > floor)
        left = rest - est[~free].sum()
        est[free] = max(left, 0) * w[free] / w[free].sum() if w[free].sum() > 0 else est[free]
    out = sector_totals.astype(float)
    out.loc[secs] = est.values
    print(f"    QCEW withholds ND private sector totals {', '.join(secs)}: {rest:,.0f} jobs shared by {basis}")
    return out


def gov_split(t):
    """Government jobs (QCEW own 1-3) to the five BEA government industries."""
    f = t[t.own == "1"]
    sl = t[t.own.isin(["2", "3"])]
    return {"GFGD": f[f.naics == "928"].jobs.sum(), "GFE": f[f.naics == "491"].jobs.sum(),
            "GFGN": f[~f.naics.isin(["928", "491"])].jobs.sum(),
            "GSLE": sl[sl.naics.isin(GSLE_NAICS)].jobs.sum(), "GSLG": sl[~sl.naics.isin(GSLE_NAICS)].jobs.sum()}


def by_io(t, us4):
    """Private jobs (own 5) by model industry, splitting shared 3-digit codes with US 4-digit shares."""
    p = t[t.own == "5"].groupby("naics").jobs.sum()
    out = {}
    for code, spec in MAP.items():
        q = spec[0]
        if q == G:
            continue
        v = p.reindex(q).fillna(0).sum()
        if len(spec) > 3:
            parent = q[0]
            sib = [c for c, s in MAP.items() if len(s) > 3 and s[0] == [parent]]
            tot = sum(us4.reindex(MAP[c][3]).fillna(0).sum() for c in sib)
            v *= us4.reindex(spec[3]).fillna(0).sum() / tot if tot else 1 / len(sib)
        out[code] = v
    out.update(gov_split(t))
    return pd.Series(out)


def cbp_county(year=2023):
    from county_business import zipped_csv
    from config import CBP_URL
    yy = str(year)[2:]
    d = zipped_csv(CBP_URL.format(y=year, yy=yy), RAW / "cbp" / f"cbp{yy}co.zip")
    d = d[(d.fipstate == "38") & d.naics.str.match(r"^\d{3}///$")]
    return pd.DataFrame({"cty": d.fipscty, "naics": d.naics.str[:3], "emp": pd.to_numeric(d.emp)})


def farm_county():
    z = zipfile.ZipFile(get(BEA_URL.format("CAEMP25N"), RAW / "bea" / "CAEMP25N.zip", check=is_zip, timeout=600))
    n = [x for x in z.namelist() if "_ND_" in x and x.endswith(".csv")][0]
    d = pd.read_csv(z.open(n), dtype=str, encoding="latin1")
    d = d[d.LineCode.str.strip() == "70"]
    year = [c for c in d.columns if c.strip().isdigit()][-1]
    d["cty"] = d.GeoFIPS.str.replace('"', "").str.strip().str[-3:]
    return d.set_index("cty")[year].pipe(pd.to_numeric, errors="coerce").reindex(list(COUNTIES)).fillna(0)


def county_private(state_jobs):
    """County private jobs by 3-digit NAICS from QCEW. Withheld cells get the county's 2-digit sector total minus its
    disclosed industries, split in proportion to the state's jobs in the withheld industries."""
    rows = []
    for c in COUNTIES:
        d = qcew_area(f"38{c}")
        x = d[(d.agglvl_code == "75") & (d.own_code == "5")]
        t = pd.DataFrame({"naics": x.industry_code, "jobs": pd.to_numeric(x.annual_avg_emplvl),
                          "hidden": x.disclosure_code.fillna("").eq("N")})
        t.loc[t.hidden, "jobs"] = np.nan
        t["sector"] = t.naics.str[:2].replace({"32": "31", "33": "31", "45": "44", "49": "48"})
        sec = d[(d.agglvl_code == "74") & (d.own_code == "5")]
        sec = pd.Series(pd.to_numeric(sec.annual_avg_emplvl).values, index=sec.industry_code.str[:2])
        sec_hidden = d[(d.agglvl_code == "74") & (d.own_code == "5") & d.disclosure_code.fillna("").eq("N")].industry_code.str[:2]
        for s_, g in t[t.jobs.isna()].groupby("sector"):
            if s_ in set(sec_hidden) or s_ not in sec.index:
                rest = 0.0                      # sector itself withheld: leave to the statewide share below
            else:
                rest = max(sec[s_] - t[(t.sector == s_) & t.jobs.notna()].jobs.sum(), 0)
            w = state_jobs.reindex(g.naics).fillna(0)
            w = w / w.sum() if w.sum() > 0 else pd.Series(1 / len(g), index=g.naics)
            t.loc[g.index, "jobs"] = rest * w.values
        rows.append(t.assign(cty=c))
    return pd.concat(rows).pivot_table(index="naics", columns="cty", values="jobs", aggfunc="sum").reindex(
        columns=list(COUNTIES)).fillna(0)


def county_keys(qa, state_jobs):
    """Allocation key: county share of the state, per model industry."""
    piv = county_private(state_jobs)
    gov = qa[(qa.year == IO_YEAR) & qa.area.str.match(r"^38\d{3}$") & ~qa.area.isin(["38000", "38999"]) & (qa.industry == "10")]
    gov = gov.pivot_table(index="own", columns="area", values="jobs").rename(columns=lambda a: a[2:]).reindex(
        columns=list(COUNTIES)).fillna(0)
    total = gov.sum()
    keys = {}
    for code, spec in MAP.items():
        q = spec[0]
        if code == "111CA":
            k = farm_county()
        elif code == "482":
            k = piv.reindex(["481", "484", "485", "486", "487", "488", "492", "493"]).fillna(0).sum()
        elif code in ("GFGD", "GFGN", "GFE"):
            k = gov.loc["1"] if "1" in gov.index else total
        elif code in ("GSLG", "GSLE"):
            k = gov.reindex(["2", "3"]).fillna(0).sum()
        else:
            k = piv.reindex(q).fillna(0).sum() if q else total
        if k.sum() <= 0:
            k = total
        keys[code] = k / k.sum()
    return pd.DataFrame(keys).T                      # model industry x county


# ------------------------------------------------------------------ productivity and pay
def gdp_lines():
    z = zipfile.ZipFile(get(BEA_URL.format("SAGDP"), LIVE / "SAGDP.zip", max_age_days=7, check=is_zip))
    n = [x for x in z.namelist() if x.startswith("SAGDP2__ALL_AREAS") and x.endswith(".csv")][0]
    d = pd.read_csv(z.open(n), dtype=str, encoding="latin1")
    d["GeoFIPS"] = d.GeoFIPS.str.replace('"', "").str.strip()
    d = d[d.GeoFIPS.isin(["00000", "38000"]) & d.IndustryClassification.notna()]
    d["cls"] = d.IndustryClassification.str.strip()
    v = pd.to_numeric(d[str(IO_YEAR)], errors="coerce")
    return pd.DataFrame({"geo": d.GeoFIPS.map({"00000": "US", "38000": "ND"}), "cls": d.cls, "gdp": v}).pivot_table(
        index="cls", columns="geo", values="gdp", aggfunc="first")


def build():
    use, _, names = tables()
    codes = [c for c in use.columns if c in MAP]
    nd_raw = three_digit(qcew_area("38000"), state=True)
    us_raw = three_digit(qcew_area("US000"), state=False)
    us4d = qcew_area("US000")
    us4 = us4d[(us4d.agglvl_code == "16") & (us4d.own_code == "5")].set_index("industry_code").annual_avg_emplvl.pipe(pd.to_numeric)
    nd_all = qcew_area("38000")
    nd_sec = nd_all[(nd_all.agglvl_code == "54") & (nd_all.own_code == "5")]
    sector_totals = pd.to_numeric(nd_sec.set_index(nd_sec.industry_code.str[:2]).annual_avg_emplvl)
    cbp = cbp_county()
    sector_totals = withheld_sectors(sector_totals, nd_sec, nd_all, cbp)
    nd_raw = fill_hidden(nd_raw, sector_totals.to_dict(), cbp.groupby("naics").emp.sum())
    us_jobs, nd_jobs = by_io(us_raw, us4).reindex(codes).fillna(0), by_io(nd_raw, us4).reindex(codes).fillna(0)
    # pay ratio ND/US by model industry (wages per job), for labor income
    def pay(t):
        p = t[(t.own == "5") & t.wages.notna()].groupby("naics")[["jobs", "wages"]].sum()   # disclosed cells only
        return {c: (p.reindex(s[0])[["wages", "jobs"]].sum()) for c, s in MAP.items() if s[0] != G and s[0]}
    def ratios(us_t, nd_t):
        pu, pn = pay(us_t), pay(nd_t)
        return pd.Series({c: (pn[c].wages / pn[c].jobs) / (pu[c].wages / pu[c].jobs)
                          if pn[c].jobs > 0 and pu[c].jobs > 0 else np.nan for c in pu})
    pay_ratio = ratios(us_raw, nd_raw)
    for y in range(IO_YEAR - 1, IO_YEAR - 6, -1):  # ND pay withheld this year: the latest earlier year it was published
        if pay_ratio.notna().all():
            break
        try:
            older = ratios(three_digit(qcew_area("US000", y), state=False), three_digit(qcew_area("38000", y), state=True))
        except FileNotFoundError:
            continue
        pay_ratio = pay_ratio.fillna(older)
    pay_ratio = pay_ratio.reindex(codes).fillna(1.0).clip(0.5, 1.6)
    # productivity: ND GDP per job relative to US, by GDP-by-state line
    gl = gdp_lines()
    line_jobs = pd.DataFrame({"US": us_jobs, "ND": nd_jobs, "cls": [MAP[c][2] for c in codes]}, index=codes)
    lj = line_jobs.groupby("cls")[["US", "ND"]].sum()
    prod = {}
    for c in codes:
        cls = MAP[c][2]
        if cls is None or cls not in gl.index or cls not in lj.index or min(lj.loc[cls]) <= 0:
            prod[c] = 1.0
            continue
        prod[c] = (gl.loc[cls, "ND"] / lj.loc[cls, "ND"]) / (gl.loc[cls, "US"] / lj.loc[cls, "US"])
    prod = pd.Series(prod).clip(0.25, 6.0)
    state3 = nd_raw[nd_raw.own == "5"].groupby("naics").jobs.sum()
    keys = county_keys(pd.read_csv(OUT / "qcew_annual.csv", dtype={"area": str, "own": str, "industry": str}), state3)
    t = pd.DataFrame({"code": codes, "name": [names.get(c, c) for c in codes], "jobs_US": us_jobs.values,
                      "jobs_ND": nd_jobs.values, "pay_ratio_ND": pay_ratio.values, "productivity_ND": prod.reindex(codes).values})
    for r, cs in REGIONS.items():
        fips = [k for k, v in COUNTIES.items() if v in cs]
        t[f"jobs_{r}"] = nd_jobs.values * keys.reindex(codes)[fips].sum(axis=1).values
    return t


def stateio():
    """EPA StateIO two-region ND model files (kept as downloaded)."""
    import rdata
    out = {}
    for n in STATEIO_FILES:
        name = n.format(y=STATEIO_YEAR)
        f = get(STATEIO.format(name), RAW / "stateio" / name, timeout=600)
        obj = rdata.read_rds(str(f))
        out[name.split("_")[2]] = obj["North Dakota"] if isinstance(obj, dict) else obj
    return out


def main():
    t = build()
    t.to_csv(OUT / "io_industries.csv", index=False)
    print(f"    IO data {IO_YEAR}: {len(t)} industries; ND jobs {t.jobs_ND.sum():,.0f}; "
          f"regions sum {t[[c for c in t if c.startswith('jobs_Region')]].sum().sum():,.0f}")
    src = "BEA Data API" if IO_SOURCE == "BEA Data API" else "bulk file, no longer updated by BEA"
    return {"bea_io": {"name": f"Input-output accounts, Make and Use tables (summary, before redefinitions; {src})",
                       "publisher": "U.S. Bureau of Economic Analysis",
                       "url": "https://www.bea.gov/industry/input-output-accounts-data", "period": str(IO_YEAR),
                       "latest": str(IO_YEAR)},
            "stateio": {"name": "StateIO two-region state input-output models (cross-check)",
                        "publisher": "U.S. Environmental Protection Agency", "url": "https://github.com/USEPA/stateior",
                        "period": str(STATEIO_YEAR), "latest": str(STATEIO_YEAR)}}


if __name__ == "__main__":
    main()
