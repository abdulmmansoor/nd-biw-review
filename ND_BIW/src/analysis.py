"""Step: analysis built on the downloaded tables (no new data).

 - Shift-share: splits a place's private job change by industry into
     national growth  = jobs at start x US private job growth,
     industry mix     = jobs at start x (US industry growth - US private growth),
     local (regional) = jobs at start x (local industry growth - US industry growth).
   The three add up exactly to the actual change. Industries BLS did not disclose in either year are left out.
   Dynamic shift-share (Barff & Knight, 1988) repeats this for every pair of consecutive years and adds the yearly
   parts, which removes the dependence on the start year's industry mix; industries must be disclosed in every year.
 - Cluster position: each industry's location quotient (LQ) against its yearly job growth.
 - Economic base: jobs above what the US share would predict (LQ > 1), i.e. jobs that likely serve
   customers outside the place (the location-quotient method; a rough estimate that ignores trade and
   differences in productivity and demand).
 - Peer scorecard: ND, MN, MT, SD, WY and the US on ten measures, with ND's rank among the five states. For survey
   (ACS) measures, each peer's difference from ND is tested at 90%, and a conservative rank counts only states that are
   significantly better than ND (U.S. Census Bureau, 2020, chapter 8).
The functions are also used by the dashboard for periods the reader picks.
Writes outputs/shift_share.csv, clusters.csv, economic_base.csv and scorecard.csv.
"""
import numpy as np
import pandas as pd
from config import OUT, PEER_NAMES, PEERS, SECTORS

STATES = list(PEERS)
SMALL_BASE = 50          # location quotients resting on fewer jobs than this are flagged "small base"


def _jobs(q, area, year):
    d = q[(q.area == area) & (q.year == year) & (q.own == "5")]
    return d.set_index("industry").jobs


def shift_share(q, area, start, end):
    e0, e1 = _jobs(q, area, start), _jobs(q, area, end)
    n0, n1 = _jobs(q, "US000", start), _jobs(q, "US000", end)
    g = n1["10"] / n0["10"] - 1
    sec = [s for s in SECTORS if pd.notna(e0.get(s)) and pd.notna(e1.get(s)) and e0.get(s) > 0]
    t = pd.DataFrame({"industry": sec, "jobs_start": e0[sec].values, "jobs_end": e1[sec].values})
    us_g = (n1[sec] / n0[sec] - 1).values
    loc_g = t.jobs_end / t.jobs_start - 1
    t["national"] = t.jobs_start * g
    t["industry_mix"] = t.jobs_start * (us_g - g)
    t["local"] = t.jobs_start * (loc_g - us_g)
    t["change"] = t.jobs_end - t.jobs_start
    t["start"], t["end"], t["area"] = start, end, area
    t.attrs["left_out"] = [s for s in SECTORS if s not in sec]
    return t


def dynamic_shift_share(q, area, start, end):
    """Barff and Knight (1988): the sum of yearly shift-share parts from start to end. Only industries disclosed in
    every year are kept, so the parts add up exactly to their actual change."""
    parts = [shift_share(q, area, y, y + 1) for y in range(start, end)]
    keep = set.intersection(*(set(p.industry) for p in parts))
    cols = ["national", "industry_mix", "local", "change"]
    t = pd.concat([p[p.industry.isin(keep)] for p in parts]).groupby("industry", sort=False)[cols].sum()
    t = t.reindex([s for s in SECTORS if s in keep]).reset_index()
    e0, e1 = _jobs(q, area, start), _jobs(q, area, end)
    t.insert(1, "jobs_start", e0.reindex(t.industry).values)
    t.insert(2, "jobs_end", e1.reindex(t.industry).values)
    t["start"], t["end"], t["area"] = start, end, area
    t.attrs["left_out"] = [s for s in SECTORS if s not in keep]
    return t


def clusters(q, area, end, span):
    start = end - span
    e0, e1 = _jobs(q, area, start), _jobs(q, area, end)
    d = q[(q.area == area) & (q.year == end) & (q.own == "5") & q.industry.isin(list(SECTORS))].set_index("industry")
    t = pd.DataFrame({"jobs": d.jobs, "lq": d.lq_jobs})
    t["growth"] = ((e1.reindex(t.index) / e0.reindex(t.index)) ** (1 / span) - 1) * 100
    total_g = ((e1.get("10") / e0.get("10")) ** (1 / span) - 1) * 100 if e0.get("10") else np.nan
    t = t.dropna(subset=["jobs", "lq", "growth"])
    t = t[t.lq > 0]
    t["quadrant"] = np.select(
        [(t.lq >= 1) & (t.growth >= total_g), (t.lq >= 1), t.growth >= total_g],
        ["Specialized and growing faster", "Specialized, growing slower", "Less concentrated, growing faster"],
        "Less concentrated, growing slower")
    t.attrs["total_growth"] = total_g
    return t.reset_index().assign(area=area, start=start, end=end)


def economic_base(q, area, year):
    d = q[(q.area == area) & (q.year == year) & (q.own == "5") & q.industry.isin(list(SECTORS))]
    t = d[["industry", "jobs", "lq_jobs"]].dropna().copy()
    t["base_jobs"] = np.where(t.lq_jobs > 1, t.jobs * (1 - 1 / t.lq_jobs), 0.0)
    return t.assign(area=area, year=year)


def latest_complete_year(q, area="38000"):
    """Latest year in which BLS disclosed jobs for every private industry in the area."""
    d = q[(q.area == area) & (q.own == "5") & q.industry.isin(list(SECTORS))]
    ok = d.groupby("year").jobs.apply(lambda s: s.notna().all())
    return int(ok[ok].index.max())


def scorecard(bfs, bds, fa, q, bea, acs):
    pop = acs[acs.level.isin(["state", "nation"])].set_index("code").population
    rows = []

    def add(name, values, period, source, fmt, higher=True):
        r = {"measure": name, "period": period, "source": source, "format": fmt, "higher_is": "higher" if higher else "lower"}
        r.update({g: values.get(g, np.nan) for g in STATES + ["US"]})
        rows.append(r)

    from population import population as lookup
    annual = lookup()
    for series, label in (("BA_BA", "Business applications per 1,000 residents"),
                          ("BA_HBA", "High-propensity applications per 1,000 residents")):
        b = bfs[(bfs.series == series) & (bfs.sa == "U") & (bfs.naics_sector == "TOTAL")]
        last = b.date.max()
        tot = b[b.date > last - pd.DateOffset(years=1)].groupby("geo").value.sum()
        v = tot / pd.Series({g: annual(g, last.year) for g in tot.index}) * 1000
        add(label, v, f"12 months to {last:%b %Y}", "Census BFS", "{:.1f}")
    y = int(bds.year.max())
    add("Establishment opening rate (%)", bds[bds.year == y].set_index("geo").estabs_entry_rate, str(y), "Census BDS", "{:.1f}")
    f = fa[fa.year == y]
    young = f[f.young].groupby("geo").emp.sum() / f.groupby("geo").emp.sum() * 100
    add("Share of jobs at firms 5 years old or younger (%)", young, str(y), "Census BDS", "{:.1f}")
    areas = {f"{v}000": k for k, v in PEERS.items()} | {"US000": "US"}
    tot = q[(q.own == "5") & (q.industry == "10") & q.area.isin(areas)]
    end = int(tot.year.max())
    p = tot.pivot_table(index="area", columns="year", values="jobs")
    gr = ((p[end] / p[end - 5]) ** (1 / 5) - 1) * 100
    add("Private job growth, yearly average (%)", gr.rename(index=areas), f"{end - 5}-{end}", "BLS QCEW", "{:+.1f}")
    pay = q[(q.own == "0") & (q.industry == "10") & (q.year == end) & q.area.isin(areas)].set_index("area").avg_pay
    add("Average annual pay, all jobs ($)", pay.rename(index=areas), str(end), "BLS QCEW", "${:,.0f}")
    r = bea[(bea.measure == "real") & (bea.industry == "total")].pivot_table(index="geo", columns="year", values="value")
    by = int(r.columns.max())
    add("Real GDP growth, yearly average (%)", ((r[by] / r[by - 5]) ** (1 / 5) - 1) * 100, f"{by - 5}-{by}", "BEA", "{:+.1f}")
    a = acs[acs.level.isin(["state", "nation"])].set_index("code")
    se = {}
    for col, label, fmt, higher in (("median_household_income", "Median household income ($)", "${:,.0f}", True),
                                    ("per_capita_income", "Per capita income ($)", "${:,.0f}", True),
                                    ("unemployment_rate", "Unemployment rate (%)", "{:.1f}", False)):
        add(label, a[col], "2020-2024", "Census ACS", fmt, higher=higher)
        se[label] = a[col + "_moe"] / 1.645                    # ACS margins are 90%: SE = MOE / 1.645
    t = pd.DataFrame(rows)
    vals = t[STATES]
    asc = t.higher_is.eq("lower")
    t["nd_rank"] = [int(vals.iloc[i].rank(ascending=bool(asc.iloc[i]), method="min")["ND"]) for i in range(len(t))]
    # Survey (ACS) measures have sampling error: test each peer's difference from ND at 90% (U.S. Census Bureau, 2020),
    # z = (x_peer - x_ND) / sqrt(SE_peer^2 + SE_ND^2), significant if |z| > 1.645. The conservative rank counts only
    # states that are significantly better than ND. Administrative measures have no sampling error.
    t["sampling_error"] = t.measure.isin(se)
    t["nd_rank_significant"] = t.nd_rank
    for g in STATES[1:]:
        t[f"{g}_significant"] = True
    for i, r in t[t.sampling_error].iterrows():
        s_ = se[r.measure]
        better = 0
        for g in STATES[1:]:
            z = (r[g] - r["ND"]) / np.sqrt(s_[g] ** 2 + s_["ND"] ** 2)
            sig = abs(z) > 1.645
            t.at[i, f"{g}_significant"] = bool(sig)
            if sig and ((z > 0) == (r.higher_is == "higher")):
                better += 1
        t.at[i, "nd_rank_significant"] = 1 + better
    return t


def main():
    q = pd.read_csv(OUT / "qcew_annual.csv", dtype={"area": str, "own": str, "industry": str})
    full = latest_complete_year(q)
    first = int(q.year.min())
    ss = shift_share(q, "38000", first, full)
    ss.to_csv(OUT / "shift_share.csv", index=False)
    clusters(q, "38000", full, 5).to_csv(OUT / "clusters.csv", index=False)
    economic_base(q, "38000", full).to_csv(OUT / "economic_base.csv", index=False)
    sc = scorecard(pd.read_csv(OUT / "bfs_monthly.csv", parse_dates=["date"]), pd.read_csv(OUT / "bds_states.csv"),
                   pd.read_csv(OUT / "bds_firm_age.csv"), q, pd.read_csv(OUT / "bea_gdp.csv", dtype={"industry": str}),
                   pd.read_csv(OUT / "acs_places.csv"))
    sc.to_csv(OUT / "scorecard.csv", index=False)
    print(f"    Shift-share {first}-{full}: {ss.change.sum():+,.0f} private jobs in {len(ss)} industries; "
          f"scorecard {len(sc)} measures")
    return {}


if __name__ == "__main__":
    main()


def startup_survival(fa, horizon=5):
    """Approximate survival of new firms: firms aged `horizon` in year t + horizon divided by firms aged 0 (new) in year t,
    for each place and starting year (BDS firm-age tables). BDS dates a firm by its oldest establishment, so mergers
    can add firms to an age class; the ratio is an approximation of cohort survival (Haltiwanger et al., 2013)."""
    f = fa[fa.age.astype(str).isin(["0", str(horizon)])].copy()
    f["age"] = f.age.astype(str)
    w = f.pivot_table(index=["geo", "year"], columns="age", values="firms").reset_index()
    born = w[["geo", "year", "0"]].rename(columns={"0": "births"})
    later = w[["geo", "year", str(horizon)]].rename(columns={str(horizon): "survivors"})
    later["year"] -= horizon
    t = born.merge(later, on=["geo", "year"]).dropna()
    t["survival"] = t.survivors / t.births * 100
    return t.rename(columns={"year": "cohort"})
