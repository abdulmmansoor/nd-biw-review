"""Step: case study, main street retail (built only from tables the pipeline already has).

Question: do the regional hub counties draw shoppers from smaller counties, and how are main street sales holding up?
 - Hub counties: the county of each planning region's hub city (the city each regional council is named after).
   All other counties are "other counties".
 - Retail pull factor (Hustedde et al., 1984): 2022 Economic Census retail sales against the sales the county's share
   of ND household income would predict (from the retail gap step). Groups use summed sales over summed expected sales.
   A few counties' sales are withheld by the Census Bureau and estimated in that step; they are flagged.
 - Taxable sales and purchases by county (ND Tax Commissioner), 4-quarter totals from 2019, current dollars. Out-of-state
   and statewide consolidated filers have no county and are left out. The base includes business purchases, which
   swing with drilling, so the comparison is made without the oil case's core oil counties (one of them, Williams, is
   a hub); the all-county series is kept in the table (scope column).
 - Retail stores (County Business Patterns, employer establishments, NAICS 44-45) and retail businesses without
   employees (Nonemployer Statistics), per 1,000 residents (ACS 5-year population).
Writes outputs/case_retail_counties.csv, case_retail_sales.csv and case_retail_findings.csv.
"""
import numpy as np
import pandas as pd
from config import COUNTIES, OUT, REGIONS

HUB_COUNTY = {"Williston": "Williams", "Minot": "Ward", "Devils Lake": "Ramsey", "Grand Forks": "Grand Forks",
              "Fargo": "Cass", "Jamestown": "Stutsman", "Bismarck": "Burleigh", "Dickinson": "Stark"}
HUBS = [HUB_COUNTY[r.split("(")[1].rstrip(")")] for r in REGIONS]
HUB, OTHER = "Hub counties", "Other counties"
ALL, NO_OIL = "All counties", "Excluding core oil counties"
BASE = pd.Timestamp("2019-10-01")          # taxable sales compare the year to 2019 Q4 with later years


def counties():
    r = pd.read_csv(OUT / "retail_gap.csv")
    r = r[r.level == "county"]
    rt = r[r.naics == "44-45"].set_index("place")
    rest = r[r.naics == "722"].set_index("place")
    a = pd.read_csv(OUT / "acs_places.csv")
    a = a[a.level == "county"].set_index("county")
    b = pd.read_csv(OUT / "county_business.csv", dtype={"sector": str})
    b = b[b.sector == "44-45"].set_index("county")
    c = pd.DataFrame(index=sorted(COUNTIES.values()))
    c.index.name = "county"
    c["group"] = np.where(c.index.isin(HUBS), HUB, OTHER)
    c["region"] = a.region.reindex(c.index)
    c["population"] = a.population.reindex(c.index)
    c["retail_sales_k"] = rt.sales_k.reindex(c.index)
    c["retail_expected_k"] = rt.expected_k.reindex(c.index)
    c["pull_factor"] = rt.pull_factor.reindex(c.index)
    c["estimated"] = rt.estimated.reindex(c.index).fillna(False).astype(bool)
    c["restaurant_pull_factor"] = rest.pull_factor.reindex(c.index)
    c["retail_stores"] = b.employer_estabs.reindex(c.index)
    c["retail_nonemployers"] = b.nonemployers.reindex(c.index)
    c["stores_per_1000"] = c.retail_stores / c.population * 1000
    return c.reset_index()


def core_oil():
    """The oil case's core oil counties (built just before this step). Their taxable sales are mostly business
    purchases that swing with drilling, so the sales comparison is also shown without them."""
    f = OUT / "case_oil_counties.csv"
    if not f.exists():
        return []
    c = pd.read_csv(f)
    return c[c.core.astype(bool)].county.tolist()


def price_4q():
    """GDP price index (BEA), average of the 4 quarters ending in each quarter: the deflator the dashboard uses for
    real taxable sales, since about 40% of the base is business purchases."""
    p = pd.read_csv(OUT / "pce_price_quarterly.csv", parse_dates=["quarter"]).set_index("quarter").sort_index()
    return p.gdp_price.rolling(4).mean()


def sales(oil=()):
    s = pd.read_csv(OUT / "taxable_sales_county.csv", parse_dates=["quarter"])
    s = s[s.county.isin(COUNTIES.values())]
    s["group"] = np.where(s.county.isin(HUBS), HUB, OTHER)
    out = []
    for scope, d in ((ALL, s), (NO_OIL, s[~s.county.isin(oil)])):
        g = d.groupby(["group", "quarter"]).value.sum(min_count=1).reset_index()
        n = d.groupby(["group", "quarter"]).county.nunique().reset_index(name="counties")
        g = g.merge(n, on=["group", "quarter"]).assign(scope=scope)
        g["four_quarter"] = g.groupby("group").value.transform(lambda v: v.rolling(4).sum())
        out.append(g)
    out = pd.concat(out, ignore_index=True)
    p = price_4q()
    base = p.loc[BASE]
    out["four_quarter_real"] = out.four_quarter / out.quarter.map(p) * base     # dollars of the year to 2019 Q4
    return out


def findings(c, s, oil=()):
    f = []

    def add(key, value, unit, label):
        f.append({"key": key, "value": float(value) if pd.notna(value) else np.nan, "unit": unit, "label": label})

    grp = c.groupby("group")[["retail_sales_k", "retail_expected_k", "population", "retail_stores",
                              "retail_nonemployers"]].sum()
    for g, k in ((HUB, "hub"), (OTHER, "other")):
        add(f"pf_{k}", grp.loc[g, "retail_sales_k"] / grp.loc[g, "retail_expected_k"], "PF", f"{g}: retail pull factor, 2022")
        add(f"pop_share_{k}", grp.loc[g, "population"] / grp.population.sum() * 100, "%", f"{g}: share of ND residents")
        add(f"sales_share_{k}", grp.loc[g, "retail_sales_k"] / grp.retail_sales_k.sum() * 100, "%",
            f"{g}: share of ND retail sales, 2022")
        add(f"stores_per_1000_{k}", grp.loc[g, "retail_stores"] / grp.loc[g, "population"] * 1000, "per 1,000",
            f"{g}: retail stores with employees per 1,000 residents")
        add(f"nonemp_per_1000_{k}", grp.loc[g, "retail_nonemployers"] / grp.loc[g, "population"] * 1000, "per 1,000",
            f"{g}: retail businesses without employees per 1,000 residents")
    o = c[c.group == OTHER].dropna(subset=["pull_factor"])
    add("other_n", len(o), "counties", "Other counties with a pull factor")
    add("other_below_1", int((o.pull_factor < 1).sum()), "counties", "Other counties with a pull factor below 1")
    add("other_below_half", int((o.pull_factor < .5).sum()), "counties", "Other counties with a pull factor below 0.5")
    h = c[c.group == HUB]
    add("hub_above_1", int((h.pull_factor >= 1).sum()), "counties", "Hub counties with a pull factor of 1 or more")
    leak = (o.retail_expected_k - o.retail_sales_k).clip(lower=0).sum() / 1000
    add("other_leakage_m", leak, "$ million", "Other counties: sales below expected, summed over leaking counties, 2022")
    add("estimated_n", int(c.estimated.sum()), "counties", "Counties with estimated (withheld) retail sales")
    base = BASE
    for scope, sfx in ((NO_OIL, "_nooil"), (ALL, "")):
        d = s[s.scope == scope].dropna(subset=["four_quarter"])
        x = d.pivot(index="quarter", columns="group", values="four_quarter")
        xr = d.dropna(subset=["four_quarter_real"]).pivot(index="quarter", columns="group", values="four_quarter_real")
        lx, lr = x.index.max(), xr.index.max()
        for g, k in ((HUB, "hub"), (OTHER, "other")):
            who = g + (" without core oil counties" if sfx else "")
            add(f"tax_{k}_growth{sfx}", (x.loc[lx, g] / x.loc[base, g] - 1) * 100, "%",
                f"{who}: taxable sales, year to {lx.year} Q{lx.quarter} compared with 2019 (current dollars)")
            add(f"tax_{k}_growth_real{sfx}", (xr.loc[lr, g] / xr.loc[base, g] - 1) * 100, "%",
                f"{who}: taxable sales after inflation, year to {lr.year} Q{lr.quarter} compared with 2019")
    p = price_4q()
    add("price_growth", (p.loc[lx] / p.loc[base] - 1) * 100, "%",
        f"GDP price index, year to {lx.year} Q{lx.quarter} compared with 2019")
    add("oil_counties_n", len(oil), "counties", "Core oil counties left out of the comparison (from the oil case)")
    w = s[s.scope == ALL].dropna(subset=["four_quarter"]).pivot(index="quarter", columns="group", values="four_quarter")
    last = w.index.max()
    add("tax_hub_share_2019", w.loc[base, HUB] / w.loc[base].sum() * 100, "%", "Hub counties' share of county taxable sales, 2019")
    add("tax_hub_share_latest", w.loc[last, HUB] / w.loc[last].sum() * 100, "%",
        f"Hub counties' share of county taxable sales, year to {last.year} Q{last.quarter}")
    return pd.DataFrame(f)


def main():
    oil = core_oil()
    c, s = counties(), sales(oil)
    fnd = findings(c, s, oil)
    c.to_csv(OUT / "case_retail_counties.csv", index=False)
    s.to_csv(OUT / "case_retail_sales.csv", index=False)
    fnd.to_csv(OUT / "case_retail_findings.csv", index=False)
    v = fnd.set_index("key").value
    print(f"    Main street retail case: pull factor hubs {v['pf_hub']:.2f}, other counties {v['pf_other']:.2f}; "
          f"{v['other_below_1']:.0f} of {v['other_n']:.0f} other counties below 1")
    return {}


if __name__ == "__main__":
    main()
