"""Step: case study, the oil cycle and North Dakota's core oil counties (built only from tables the pipeline already has).

Core oil counties are chosen from data, not by name: counties where mining, oil and gas (NAICS 21) held at least
CORE_SHARE of private jobs in the latest full QCEW year with the county's sector figure published. BLS withholds the
sector for some smaller oil counties (for example Divide, Burke, Billings); they cannot be classified and stay in
"rest of North Dakota", which the page says.

Series compared, core counties against the rest of the state:
 - private jobs by quarter (BLS QCEW, 2014 onward; rest of ND = state less core counties, so withheld small counties
   do not leave gaps),
 - establishments, openings and closings by year (Census BDS, 2000-2023),
 - taxable sales by quarter (ND Tax Commissioner, 2019 onward),
 - oil production and price by month (EIA).
Job changes compare 4-quarter averages, so seasonal swings do not distort them.
Key findings are computed here so the page text updates with each data run. The lag correlation between oil prices and
jobs is descriptive: it shows timing, not cause.
Writes outputs/case_oil_counties.csv, case_oil_quarterly.csv, case_oil_annual.csv, case_oil_sales.csv and
case_oil_findings.csv.
"""
import numpy as np
import pandas as pd
from config import COUNTIES, LIVE, OUT

CORE_SHARE = 0.20
QUARTERLY = LIVE / "qcew_region" / "nd_quarterly.csv"
CORE, REST = "Core oil counties", "Rest of North Dakota"


def core_counties():
    q = pd.read_csv(OUT / "qcew_annual.csv", dtype={"area": str, "own": str, "industry": str})
    q = q[q.area.isin([f"38{c}" for c in COUNTIES]) & (q.own == "5")]
    y = int(q[q.industry == "21"].groupby("year").disclosed.mean().pipe(lambda s: s[s == s.max()]).index.max())
    q = q[q.year == y]
    tot = q[q.industry == "10"].set_index("place").jobs
    m = q[q.industry == "21"].set_index("place")
    c = pd.DataFrame({"county": tot.index, "private_jobs": tot.values})
    c["mining_jobs"] = c.county.map(m.jobs)
    c["mining_published"] = c.county.map(m.disclosed).fillna(False).astype(bool)
    c["mining_share"] = c.mining_jobs / c.private_jobs
    c["core"] = c.mining_published & (c.mining_share >= CORE_SHARE)
    c["year"] = y
    return c.sort_values("mining_share", ascending=False)


def quarterly(core):
    d = pd.read_csv(QUARTERLY, dtype={"area": str, "own": str})
    d = d[d.own == "5"]
    d["quarter"] = pd.PeriodIndex.from_fields(year=d.year, quarter=d.qtr, freq="Q").to_timestamp()
    fips = {f"38{c}": n for c, n in COUNTIES.items()}
    st = d[d.area == "38000"].set_index("quarter").jobs
    cc = d[d.area.map(fips).isin(core)].groupby("quarter").jobs.sum(min_count=len(core))
    out = pd.DataFrame({CORE: cc, REST: st - cc}).dropna()
    e = pd.read_csv(OUT / "energy_monthly.csv", parse_dates=["month"])
    e["quarter"] = e.month.dt.to_period("Q").dt.to_timestamp()
    eq = e.groupby("quarter").agg(wti_usd=("wti_usd", "mean"), nd_crude_kbd=("nd_crude_kbd", "mean"),
                                  months=("nd_crude_kbd", "count"))
    eq.loc[eq.months < 3, "nd_crude_kbd"] = np.nan
    t = out.stack().rename("private_jobs").reset_index().rename(columns={"level_1": "group"})
    t["avg4"] = t.groupby("group").private_jobs.transform(lambda v: v.rolling(4).mean())
    b4 = t[t.quarter.dt.year == t.quarter.dt.year.min()].groupby("group").private_jobs.mean()
    t["index"] = t.avg4 / t.group.map(b4) * 100      # 4-quarter average, first full year = 100 (no seasonality)
    t["yoy_pct"] = t.groupby("group").private_jobs.pct_change(4) * 100
    return t.merge(eq[["wti_usd", "nd_crude_kbd"]].reset_index(), on="quarter", how="left")


def annual(core):
    b = pd.read_csv(OUT / "bds_counties.csv")
    b["group"] = np.where(b.county.isin(core), CORE, REST)
    g = b.groupby(["group", "year"])[["firms", "estabs", "emp", "estabs_entry", "estabs_exit"]].sum().reset_index()
    prev = g.groupby("group").estabs.shift(1)
    denom = (g.estabs + prev) / 2                     # BDS rates use the average of this and last year's count
    g["entry_rate"] = g.estabs_entry / denom * 100
    g["exit_rate"] = g.estabs_exit / denom * 100
    return g


def sales(core):
    s = pd.read_csv(OUT / "taxable_sales_county.csv", parse_dates=["quarter"])
    s = s[s.county.isin(COUNTIES.values())]
    s["group"] = np.where(s.county.isin(core), CORE, REST)
    g = s.groupby(["group", "quarter"]).value.sum(min_count=1).reset_index()
    g["four_quarter"] = g.groupby("group").value.transform(lambda v: v.rolling(4).sum())
    return g


def lag_correlation(t, group, max_lag=8):
    """Correlation of the group's year-over-year job change with the year-over-year change in the WTI price lagged
    0..max_lag quarters (2015 onward, after the first full year of the series)."""
    d = t[t.group == group].set_index("quarter").sort_index()
    p = d.wti_usd.pct_change(4) * 100
    r = {k: d.yoy_pct.corr(p.shift(k)) for k in range(max_lag + 1)}
    k = max(r, key=lambda x: r[x])
    return k, r[k], r


def findings(c, t, a, s):
    f = []

    def add(key, value, unit, label):
        f.append({"key": key, "value": float(value) if pd.notna(value) else np.nan, "unit": unit, "label": label})

    e = pd.read_csv(OUT / "energy_monthly.csv", parse_dates=["month"]).set_index("month")
    w14 = e.loc["2014-01":"2014-12", "wti_usd"]; w16 = e.loc["2015-01":"2016-12", "wti_usd"]
    add("wti_peak_2014", w14.max(), "$", f"WTI peak, {w14.idxmax():%B %Y}")
    add("wti_low_2016", w16.min(), "$", f"WTI low, {w16.idxmin():%B %Y}")
    p1 = e.loc["2014-01":"2015-12", "nd_crude_kbd"]; p2 = e.loc["2016-01":"2017-12", "nd_crude_kbd"]
    add("prod_peak_2015", p1.max(), "thousand barrels a day", f"Production peak, {p1.idxmax():%B %Y}")
    add("prod_low_2016", p2.min(), "thousand barrels a day", f"Production low, {p2.idxmin():%B %Y}")
    p3 = e.loc["2019-01":"2020-03", "nd_crude_kbd"]; p4 = e.loc["2020-04":"2020-12", "nd_crude_kbd"]
    add("prod_peak_2019", p3.max(), "thousand barrels a day", f"Production before COVID-19, peak {p3.idxmax():%B %Y}")
    add("prod_low_2020", p4.min(), "thousand barrels a day", f"Production low, {p4.idxmin():%B %Y}")
    pl = e.nd_crude_kbd.dropna()
    add("prod_latest", pl.iloc[-1], "thousand barrels a day", f"Production, {pl.index[-1]:%B %Y}")

    j = t.pivot(index="quarter", columns="group", values="avg4").dropna()      # 4 quarters ending in the quarter
    pk = j.loc["2014":"2015", CORE].idxmax(); tr = j.loc["2016":"2017", CORE].idxmin()
    lbl = lambda q: f"year to {q.year} Q{q.quarter}"
    for g, k in ((CORE, "core"), (REST, "rest")):
        add(f"jobs_{k}_bust1", (j.loc[tr, g] / j.loc[pk, g] - 1) * 100, "%",
            f"{g}: private jobs, from the {lbl(pk)} to the {lbl(tr)}")
    pk2 = j.loc["2019":"2020-03", CORE].idxmax(); tr2 = j.loc["2020-04":"2021-12", CORE].idxmin()
    for g, k in ((CORE, "core"), (REST, "rest")):
        add(f"jobs_{k}_bust2", (j.loc[tr2, g] / j.loc[pk2, g] - 1) * 100, "%",
            f"{g}: private jobs, from the {lbl(pk2)} to the {lbl(tr2)}")
    last = j.index.max()
    for g, k in ((CORE, "core"), (REST, "rest")):
        add(f"jobs_{k}_vs_2014peak", (j.loc[last, g] / j.loc[pk, g] - 1) * 100, "%",
            f"{g}: private jobs, {lbl(last)} compared with the {lbl(pk)}")
    add("core_share_jobs", j.loc[last, CORE] / j.loc[last].sum() * 100, "%",
        f"Core oil counties' share of ND private jobs, {lbl(last)}")
    for g, k in ((CORE, "core"), (REST, "rest")):
        lag, r, _ = lag_correlation(t, g)
        add(f"lag_{k}", lag, "quarters", f"{g}: oil price change that lines up best with job change, quarters earlier")
        add(f"lag_r_{k}", r, "r", f"{g}: correlation at that lag")

    ac = a[a.group == CORE].set_index("year")
    add("estabs_core_2007", ac.loc[2007, "estabs"], "establishments", "Core oil counties: establishments, 2007")
    y_max = int(ac.loc[2008:2016, "estabs"].idxmax())
    add("estabs_core_peak", ac.loc[y_max, "estabs"], "establishments", f"Core oil counties: establishments, peak {y_max}")
    yl = int(ac.index.max())
    add("estabs_core_latest", ac.loc[yl, "estabs"], "establishments", f"Core oil counties: establishments, {yl}")
    ye = int(ac.loc[2005:, "entry_rate"].idxmax())
    add("entry_core_peak", ac.loc[ye, "entry_rate"], "%", f"Core oil counties: highest opening rate, {ye}")
    add("entry_rest_same", a[(a.group == REST) & (a.year == ye)].entry_rate.iloc[0], "%",
        f"Rest of North Dakota: opening rate, {ye}")

    sw = s.dropna(subset=["four_quarter"]).pivot(index="quarter", columns="group", values="four_quarter")
    b0 = sw.loc["2019-10-01"] if pd.Timestamp("2019-10-01") in sw.index else sw.iloc[0]
    low = sw.loc["2020":"2021", CORE].idxmin()
    for g, k in ((CORE, "core"), (REST, "rest")):
        add(f"sales_{k}_2020", (sw.loc[low, g] / b0[g] - 1) * 100, "%",
            f"{g}: taxable sales, {lbl(low)} compared with 2019")
        add(f"sales_{k}_latest", (sw[g].iloc[-1] / b0[g] - 1) * 100, "%",
            f"{g}: taxable sales, {lbl(sw.index[-1])} compared with 2019")

    add("core_n", int(c.core.sum()), "counties", "Core oil counties")
    return pd.DataFrame(f)


def main():
    c = core_counties()
    core = c[c.core].county.tolist()
    t, a, s = quarterly(core), annual(core), sales(core)
    fnd = findings(c, t, a, s)
    c.to_csv(OUT / "case_oil_counties.csv", index=False)
    t.to_csv(OUT / "case_oil_quarterly.csv", index=False)
    a.to_csv(OUT / "case_oil_annual.csv", index=False)
    s.to_csv(OUT / "case_oil_sales.csv", index=False)
    fnd.to_csv(OUT / "case_oil_findings.csv", index=False)
    v = fnd.set_index("key").value
    print(f"    Oil case study: core counties {', '.join(core)}; private jobs 2014-16 bust {v['jobs_core_bust1']:+.1f}% "
          f"(rest {v['jobs_rest_bust1']:+.1f}%); best price lag {v['lag_core']:.0f} quarters (r = {v['lag_r_core']:.2f})")
    return {}


if __name__ == "__main__":
    main()
