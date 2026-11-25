"""Step: county and state unemployment from BLS Local Area Unemployment Statistics (LAUS), monthly.

LAUS is the official source of county unemployment rates (BLS, with Job Service North Dakota). It combines the
Current Population Survey, unemployment insurance claims and payroll jobs in a model, so county rates are far more
precise than the 5-year ACS survey estimate (Bureau of Labor Statistics, 2024, LAUS methodology).

Data come from the BLS public API, version 1 (no key; at most 25 series per request and 25 requests a day). Each
county has two series, unemployed (04) and labor force (06); not seasonally adjusted. Rates are computed from them,
so planning regions can be built the same way (sum of unemployed / sum of labor force). Responses are cached in
data/live/laus and refreshed after 7 days; if BLS cannot be reached, the last copy is used. A month whose county
figures are not out yet (the state is released first) is held back until they are.
Writes outputs/laus_monthly.csv (place, level, month, labor_force, unemployed, rate, preliminary).
"""
import json
import time
from datetime import date
import pandas as pd
import requests
from config import COUNTIES, COUNTY_REGION, LIVE, OUT, USER_AGENT

API = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
YEARS = 3                                      # current year and the two before: enough for 12-month averages


def series():
    out = {}
    for fips, name in COUNTIES.items():
        for m, what in (("04", "unemployed"), ("06", "labor_force")):
            out[f"LAUCN38{fips}00000000{m}"] = (name, what)
    for m, what in (("04", "unemployed"), ("06", "labor_force")):
        out[f"LAUST3800000000000{m}"] = ("North Dakota", what)
    return out


def fetch(ids, cache, max_age_days=7):
    from fetch import recheck
    if recheck():                                  # automatic daily update: ask BLS each day (5 of 25 daily requests)
        max_age_days = min(max_age_days, 0.5)
    if cache.exists() and time.time() - cache.stat().st_mtime < max_age_days * 86400:
        return json.loads(cache.read_text())
    end = date.today().year
    try:
        r = requests.post(API, json={"seriesid": ids, "startyear": str(end - YEARS + 1), "endyear": str(end)},
                          headers={"User-Agent": USER_AGENT}, timeout=120)
        r.raise_for_status()
        js = r.json()
        if js.get("status") != "REQUEST_SUCCEEDED" or any(not s["data"] for s in js["Results"]["series"]):
            raise ValueError(f"BLS API: {js.get('status')} {js.get('message')}")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(js))
        return js
    except Exception as e:
        if not cache.exists():
            raise
        print(f"    BLS API failed ({str(e)[:80]}); using last copy of {cache.name}")
        return json.loads(cache.read_text())


def build():
    meta = series()
    ids = list(meta)
    rows = []
    for k in range(0, len(ids), 25):
        js = fetch(ids[k:k + 25], LIVE / "laus" / f"laus_{k // 25:02d}.json")
        for s in js["Results"]["series"]:
            place, what = meta[s["seriesID"]]
            for d in s["data"]:
                if not d["period"].startswith("M") or d["period"] == "M13":
                    continue
                rows.append({"place": place, "what": what, "month": pd.Timestamp(int(d["year"]), int(d["period"][1:]), 1),
                             "value": float(d["value"].replace(",", "")) if d["value"] not in ("-", "") else None,
                             "preliminary": any(f.get("code") == "P" for f in d.get("footnotes", []) if f)})
    d = pd.DataFrame(rows)
    w = d.pivot_table(index=["place", "month"], columns="what", values="value").reset_index()
    pre = d.groupby(["place", "month"]).preliminary.any().reset_index()
    w = w.merge(pre, on=["place", "month"])
    w["level"] = ["state" if p == "North Dakota" else "county" for p in w.place]
    reg = w[w.level == "county"].assign(place=lambda x: x.place.map(COUNTY_REGION))
    reg = reg.groupby(["place", "month"]).agg(labor_force=("labor_force", "sum"), unemployed=("unemployed", "sum"),
                                               preliminary=("preliminary", "any"), n=("labor_force", "count")).reset_index()
    reg = reg[reg.n == reg.groupby("place").n.transform("max")].drop(columns="n").assign(level="region")
    t = pd.concat([w, reg], ignore_index=True)
    t["rate"] = t.unemployed / t.labor_force * 100
    t = complete_months(t)
    return t[["place", "level", "month", "labor_force", "unemployed", "rate", "preliminary"]].sort_values(["level", "place", "month"])


def complete_months(t):
    """Keep months up to the latest one with all 53 counties. BLS releases the state figure about two weeks before the
    county figures, so for a while the newest month has the state only; it is added, with the counties and regions,
    once the county release is out. Every level then ends in the same month."""
    c = t[(t.level == "county") & t.labor_force.notna()].groupby("month").place.nunique()
    full = c[c == len(COUNTIES)]
    if full.empty:
        return t
    held = sorted(t.month[t.month > full.index.max()].unique())
    if held:
        print(f"    LAUS: {', '.join(f'{pd.Timestamp(m):%Y-%m}' for m in held)} held back until BLS releases the counties")
    return t[t.month <= full.index.max()]


def latest_12(t):
    """Average of the latest 12 months for each place: removes the seasonal swing of unadjusted county data."""
    last = t.month.max()
    w = t[t.month > last - pd.DateOffset(months=12)]
    g = w.groupby(["place", "level"]).agg(labor_force=("labor_force", "mean"), unemployed=("unemployed", "mean"),
                                          months=("month", "nunique")).reset_index()
    g["rate"] = g.unemployed / g.labor_force * 100
    return g


def main():
    t = build()
    t.to_csv(OUT / "laus_monthly.csv", index=False)
    last = t.month.max()
    print(f"    LAUS: {t[t.level == 'county'].place.nunique()} counties, through {last:%Y-%m}")
    return {"laus": {"name": "Local Area Unemployment Statistics (counties and state, not seasonally adjusted)",
                     "publisher": "U.S. Bureau of Labor Statistics with Job Service North Dakota",
                     "url": "https://www.bls.gov/lau/", "period": f"{t.month.min():%Y-%m} to {last:%Y-%m}",
                     "latest": f"{last:%B %Y}"}}


if __name__ == "__main__":
    main()
