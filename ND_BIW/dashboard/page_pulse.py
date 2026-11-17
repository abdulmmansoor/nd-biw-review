"""Business pulse: new business applications, establishment openings and closings, taxable sales."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import PEER_NAMES

SERIES = {"BA_BA": "All business applications", "BA_HBA": "High-propensity applications (likely employers)",
          "BA_WBA": "Applications with planned wages", "BA_CBA": "Applications from corporations"}
MEASURES = ["Per 1,000 residents (12-month total)", "Index, 12-month total (2019 = 100)"]


def rolling12(b, series):
    """12-month totals of the not-seasonally-adjusted counts (sums of 12 months need no seasonal adjustment)."""
    d = b[(b.series == series) & (b.sa == "U") & (b.naics_sector == "TOTAL")].sort_values("date")
    d = d.assign(r12=d.groupby("geo").value.transform(lambda s: s.rolling(12).sum())).dropna(subset=["r12"])
    return d


def applications():
    b = lib.table("bfs_monthly.csv", parse_dates=["date"])
    pa = lib.table("population_annual.csv")
    pop_y = pa.set_index(["geo", "year"]).population
    last_y = pa.groupby("geo").year.max()

    def pop_at(geo, dates):
        return [pop_y.get((g, min(d.year, last_y[g])), float("nan")) for g, d in zip(geo, dates)]
    st.subheader("New business applications")
    st.caption("Applications for an employer identification number (EIN) for a business. Not every application "
               "becomes an operating business; high-propensity applications are the ones most likely to hire.")
    c = st.columns([2, 2])
    label = c[0].selectbox("Type of application", list(SERIES.values()), key="bfs_series")
    series = {v: k for k, v in SERIES.items()}[label]
    measure = c[1].radio("Show as", MEASURES, horizontal=True, key="bfs_measure")

    r = rolling12(b, series)
    last = r.date.max()
    nd = r[r.geo == "ND"].set_index("date").r12
    prev = nd.get(last - pd.DateOffset(years=1))
    rate = r[r.date == last].assign(per1k=lambda x: x.r12 / pop_at(x.geo, x.date) * 1000)
    rank = rate[rate.geo != "US"].sort_values("per1k", ascending=False).geo.tolist()
    ndm = b[(b.geo == "ND") & (b.series == series) & (b.sa == "A") & (b.naics_sector == "TOTAL")].sort_values("date")
    k = st.columns(4)
    k[0].metric(f"ND, 12 months to {last:%b %Y}", lib.num(nd.iloc[-1]),
                lib.pct((nd.iloc[-1] / prev - 1) * 100) + " vs year before" if prev else None)
    k[1].metric("ND per 1,000 residents", lib.num(rate.set_index("geo").per1k.get("ND"), 1),
                f"US: {lib.num(rate.set_index('geo').per1k.get('US'), 1)}", delta_color="off", delta_arrow="off")
    k[2].metric("ND rank among 5 states", f"{rank.index('ND') + 1} of {len(rank)}", "ND, MN, MT, SD, WY", delta_color="off", delta_arrow="off")
    k[3].metric(f"ND in {ndm.date.iloc[-1]:%B %Y} (seasonally adjusted)", lib.num(ndm.value.iloc[-1]),
                lib.pct((ndm.value.iloc[-1] / ndm.value.iloc[-2] - 1) * 100) + " vs month before")

    if measure.startswith("Per"):
        r["y"] = r.r12 / pop_at(r.geo, r.date) * 1000
        yt, fmt = "Per 1,000 residents", ",.2f"
    else:
        base = r[r.date == "2019-12-01"].set_index("geo").r12
        r["y"] = r.r12 / r.geo.map(base) * 100
        yt, fmt = "Index (12 months to Dec 2019 = 100)", ",.1f"
    r = r[r.date >= "2012-01-01"]
    r = r[r.geo.isin(lib.pick_places("bfs_places", default=("ND", "MN", "MT", "SD", "US")))]
    st.caption("Wyoming is off by default: its rate is several times higher than the others because many companies "
               "based elsewhere register there, which flattens the other lines. Add it back above.")
    lib.show(lib.geo_lines(r, "date", "y", ytitle=yt, fmt=fmt), "bfs_chart", title=f"{label}: {measure.lower()}")
    t = r.pivot_table(index="date", columns="geo", values="y").reset_index()
    t["date"] = t.date.dt.strftime("%Y-%m")
    lib.data_table(t.rename(columns=PEER_NAMES).round(2), key="business_applications")
    st.caption("Per 1,000 residents uses each year's population (Census Population Estimates). 12-month totals smooth out seasonal swings.")


def region_bds(c):
    """Opening and closing rates for the planning regions from county BDS data, with the Census denominator (average
    establishments this year and last); counties with withheld values are left out of numerator and denominator."""
    from lib import REGIONS
    region_of = {cty: r for r, cs in REGIONS.items() for cty in cs}
    c = c.sort_values(["county", "year"]).copy()
    c["region"] = c.county.map(region_of)
    c["denom"] = (c.estabs + c.groupby("county").estabs.shift()) / 2
    ok = c.estabs_entry.notna() & c.estabs_exit.notna() & c.denom.notna()
    c["withheld"] = (~ok).astype(int)
    g = c.assign(**{k: c[k].where(ok) for k in ("estabs_entry", "estabs_exit", "denom")}).groupby(["region", "year"]).agg(
        estabs=("estabs", "sum"), estabs_entry=("estabs_entry", "sum"), estabs_exit=("estabs_exit", "sum"),
        denom=("denom", "sum"), withheld=("withheld", "sum")).reset_index()
    g = g[g.denom > 0]
    g["entry_rate"] = g.estabs_entry / g.denom * 100
    g["exit_rate"] = g.estabs_exit / g.denom * 100
    for k in ("entry", "exit"):
        g[f"{k}_rate_3y"] = g.groupby("region")[f"{k}_rate"].transform(lambda s: s.rolling(3).mean())
    order = {r: i for i, r in enumerate(REGIONS)}
    return g.sort_values(["region", "year"], key=lambda s: s.map(order) if s.name == "region" else s)


def openings():
    s = lib.table("bds_states.csv")
    c = lib.table("bds_counties.csv")
    last = int(s.year.max())
    st.subheader("Business openings and closings")
    st.caption("Establishments (business locations with paid employees) that opened or closed, as a share of all "
               "establishments. Business Dynamics Statistics; yearly, as of March.")
    nd = s[s.geo == "ND"].set_index("year")
    k = st.columns(4)
    k[0].metric(f"ND openings, {last}", lib.num(nd.estabs_entry.get(last)), f"{nd.estabs_entry_rate.get(last):.1f}% of establishments", delta_color="off", delta_arrow="off")
    k[1].metric(f"ND closings, {last}", lib.num(nd.estabs_exit.get(last)), f"{nd.estabs_exit_rate.get(last):.1f}% of establishments", delta_color="off", delta_arrow="off")
    k[2].metric(f"Jobs at new establishments, {last}", lib.num(nd.job_creation_births.get(last)))
    k[3].metric(f"Net job creation, {last}", lib.num(nd.net_job_creation.get(last)), f"{nd.net_job_creation_rate.get(last):+.1f}%",
                delta_color="off", delta_arrow="off")
    sel = s[s.geo.isin(lib.pick_places("bds_places"))]
    cols = st.columns(2)
    for col, var, title in ((cols[0], "estabs_entry_rate", "Opening rate (%)"), (cols[1], "estabs_exit_rate", "Closing rate (%)")):
        with col:
            lib.show(lib.geo_lines(sel, "year", var, ytitle="% of establishments", fmt=".1f", h=340), f"bds_{var}", title=f"{title}")
    t = s.pivot_table(index="year", columns="geo", values=["estabs_entry_rate", "estabs_exit_rate"])
    t.columns = [f"{'Opening' if a == 'estabs_entry_rate' else 'Closing'} rate, {PEER_NAMES[g]}" for a, g in t.columns]
    lib.data_table(t.reset_index(), key="openings_closings")

    by = st.radio("Show", ["Planning regions", "Counties"], horizontal=True, key="bds_level")
    if by == "Planning regions":
        r = region_bds(c)
        st.markdown(f"**By planning region, {last}**")
        cols = st.columns(2)
        for col, var, title in ((cols[0], "entry_rate_3y", "Opening rate"), (cols[1], "exit_rate_3y", "Closing rate")):
            with col:
                fig = go.Figure()
                for i, (reg, g) in enumerate(r.groupby("region", sort=False)):
                    fig.add_scatter(x=g.year, y=g[var], name=reg, mode="lines",
                                    line=dict(color=lib.PALETTE[i % len(lib.PALETTE)], dash=lib.DASHES[i % len(lib.DASHES)],
                                              width=2), hovertemplate="%{y:.1f}%")
                lib.show(lib.layout(fig, 360, "% of establishments (3-year average)"), f"bds_reg_{var}",
                         title=f"{title} by planning region (3-year average)")
        cc = r[r.year == last][["region", "estabs", "estabs_entry", "entry_rate", "estabs_exit", "exit_rate", "withheld"]]
        cc = cc.sort_values("estabs", ascending=False).rename(columns={
            "region": "Planning region", "estabs": "Establishments", "estabs_entry": "Openings",
            "entry_rate": "Opening rate (%)", "estabs_exit": "Closings", "exit_rate": "Closing rate (%)",
            "withheld": "Counties withheld"})
        st.dataframe(cc, hide_index=True, width="stretch",
                     column_config={"Opening rate (%)": st.column_config.NumberColumn(format="%.1f"),
                                    "Closing rate (%)": st.column_config.NumberColumn(format="%.1f")})
        st.caption("Regions add up their counties. Rates use the Census method: openings or closings divided by the "
                   "average number of establishments this year and last. Counties the Census Bureau withheld are left "
                   "out of both parts of the rate. Charts show 3-year averages because single years swing.")
        return
    st.markdown(f"**By county, {last}**")
    cc = c[c.year == last][["county", "estabs", "estabs_entry", "estabs_entry_rate", "estabs_exit", "estabs_exit_rate"]]
    cc = cc.sort_values("estabs", ascending=False).rename(columns={
        "county": "County", "estabs": "Establishments", "estabs_entry": "Openings", "estabs_entry_rate": "Opening rate (%)",
        "estabs_exit": "Closings", "estabs_exit_rate": "Closing rate (%)"})
    st.dataframe(cc, hide_index=True, width="stretch", height=300,
                 column_config={"Opening rate (%)": st.column_config.NumberColumn(format="%.1f"),
                                "Closing rate (%)": st.column_config.NumberColumn(format="%.1f")})
    st.caption("Cells showing \"None\" are withheld by the Census Bureau to protect confidentiality. Rates in small counties "
               "swing a lot from year to year because a few openings or closings move them.")


def young_firms():
    f = lib.table("bds_firm_age.csv")
    last = int(f.year.max())
    st.subheader("Young firms")
    st.caption("Firms (all their locations together) by years since they first hired. Young firms create a large share "
               "of new jobs; their share of employment is a common gauge of entrepreneurial activity.")
    share = (f[f.young].groupby(["geo", "year"]).emp.sum() / f.groupby(["geo", "year"]).emp.sum() * 100).rename("share")
    share = share.reset_index()
    cols = st.columns([3, 2])
    with cols[0]:
        sel = share[share.geo.isin(lib.pick_places("fa_places"))]
        lib.show(lib.geo_lines(sel, "year", "share", ytitle="% of jobs", fmt=".1f", h=340), "fa_share", title="Share of jobs at firms 5 years old or younger (%)")
        lib.data_table(share.pivot_table(index="year", columns="geo", values="share").rename(columns=PEER_NAMES)
                       .round(2).reset_index(), key="young_firm_share")
    with cols[1]:
        nd = f[(f.geo == "ND") & (f.year == last)]
        import plotly.graph_objects as go
        fig = go.Figure(go.Bar(x=nd.age, y=nd.firms, marker=dict(color=lib.ACCENT, cornerradius=3),
                               customdata=nd.emp, hovertemplate="Age %{x}: %{y:,.0f} firms, %{customdata:,.0f} jobs<extra></extra>"))
        lib.layout(fig, 340, "Firms", legend=False).update_xaxes(title="Firm age (years)", type="category")
        lib.show(fig, "fa_nd", title=f"North Dakota firms by age, {last}")
        lib.data_table(nd[["age", "firms", "estabs", "emp"]].rename(columns={
            "age": "Firm age (years)", "firms": "Firms", "estabs": "Establishments", "emp": "Jobs"}), key="nd_firm_age")
    st.caption("'Before 1977' covers firms older than the Census records used to date them.")
    survival_chart()


def taxable_regions(last, price):
    """Taxable sales and purchases by planning region from the county file: last 4 quarters against the 4 before.
    About half of the base (out-of-state and consolidated filers) is not assigned to any county."""
    from config import COUNTY_REGION, REGIONS
    c = lib.table("taxable_sales_county.csv", parse_dates=["quarter"])
    if price is not None:
        idx = price.reindex(price.index.union(c.quarter.unique())).sort_index().ffill()
        c = c.assign(value=c.value * idx.loc[last] / c.quarter.map(idx))
    c["region"] = c.county.map(COUNTY_REGION)
    yago = last - pd.DateOffset(years=1)
    l4 = c[c.quarter > yago].groupby("region").value.sum()
    p4 = c[(c.quarter <= yago) & (c.quarter > yago - pd.DateOffset(years=1))].groupby("region").value.sum()
    allq = c[c.quarter > yago].value.sum()
    acs = lib.table("acs_places.csv")
    pop = acs[acs.level == "region"].set_index("code").population
    t = pd.DataFrame({"Last 4 quarters ($M)": l4 / 1e6, "Change vs prior 4 quarters (%)": (l4 / p4 - 1) * 100,
                      "Per resident ($)": l4 / pop.reindex(l4.index), "Share of county-assigned total (%)": l4 / l4.sum() * 100})
    t = t.reindex(list(REGIONS))
    st.markdown("**By planning region (sales reported by businesses located in the region)**")
    fig = go.Figure(go.Bar(x=t.index.str.replace(r" \(", "<br>(", regex=True), y=t.iloc[:, 1],
                           marker=dict(color=[lib.ACCENT if v >= 0 else lib.SECOND for v in t.iloc[:, 1]], line=dict(width=0)),
                           text=[f"{v:+.1f}%" for v in t.iloc[:, 1]], textposition="outside",
                           hovertemplate="%{x}: %{y:+.1f}%<extra></extra>"))
    fig.add_hline(y=0, line_color=lib.UND_GRAY, line_width=1)
    lib.show(lib.layout(fig, 320, "% change", legend=False), "ts_regions",
             title="Change in taxable sales and purchases by planning region, last 4 quarters vs prior 4")
    lib.data_table(t.round(1).reset_index().rename(columns={"index": "Planning region", "region": "Planning region"}),
                   "Taxable sales by planning region (table)", key="ts_regions_t")
    st.caption(f"Only {l4.sum() / allq * 100:.0f}% of the statewide base is assigned to a county; the rest is reported by "
               "out-of-state and consolidated (multi-location) filers, so region totals understate where spending "
               "happens, most for regions with many chain stores. Changes over time are more reliable than levels. "
               "Per resident uses ACS 2020-2024 population.")


def fiscal_years(tot):
    """Sum of the four filing quarters of each complete state fiscal year (July to June; FY2026 ends June 2026)."""
    fy = pd.Series(tot.index.year + (tot.index.month >= 7), index=tot.index)
    g = tot.groupby(fy.values).agg(["sum", "count"])
    g = g[g["count"] == 4]["sum"]
    return pd.DataFrame({"Fiscal year": [f"FY{y}" for y in g.index],
                         "Taxable sales and purchases ($ billions)": (g / 1e9).values,
                         "Change from year before (%)": (g.pct_change() * 100).values}).iloc[::-1]


def survival_chart():
    from analysis import startup_survival
    t = startup_survival(lib.table("bds_firm_age.csv"))
    sel = t[t.geo.isin(lib.pick_places("surv_places"))]
    lib.show(lib.geo_lines(sel, "cohort", "survival", ytitle="% still operating after 5 years", fmt=".1f", h=320),
             "surv", title="New firms still operating five years later (%), by year started")
    last = t.cohort.max()
    nd, us = t[(t.geo == "ND") & (t.cohort == last)].survival, t[(t.geo == "US") & (t.cohort == last)].survival
    if len(nd) and len(us):
        st.caption(f"Of North Dakota firms started in {last}, about {nd.iloc[0]:.0f}% were still operating five years "
                   f"later (US: {us.iloc[0]:.0f}%). An approximation from BDS firm-age counts; see Method.")
    lib.data_table(t.pivot_table(index="cohort", columns="geo", values="survival").rename(columns=PEER_NAMES).round(1)
                   .reset_index().rename(columns={"cohort": "Year started"}), key="survival")


def taxable_sales():
    i = lib.table("taxable_sales_industry.csv", parse_dates=["quarter"])
    st.subheader("Taxable sales and purchases")
    real = False
    try:
        pce = lib.table("pce_price_quarterly.csv", parse_dates=["quarter"]).set_index("quarter").gdp_price.dropna()
        real = st.toggle("Adjust for inflation", value=True, key="ts_real",
                         help="Divides each quarter by the GDP price index (BEA), so a rise means more real spending, "
                              "not just higher prices. The GDP index is used, not a consumer price index, because "
                              "about 40% of the base is business purchases (wholesale, mining, manufacturing).")
    except FileNotFoundError:
        pce = None
    if real:
        idx = pce.reindex(pce.index.union(i.quarter.unique())).sort_index().ffill()   # latest index for recent quarters
        base = idx.loc[i.quarter.max()]
        i = i.assign(value=i.value * base / i.quarter.map(idx))
        st.caption(f"The sales and use tax base reported by businesses each quarter (taxable sales plus taxable purchases), "
                   f"in {lib.quarter_label(i.quarter.max())} dollars: adjusted for inflation with the GDP price index "
                   f"(BEA; latest index {lib.quarter_label(pce.index.max())}, carried forward if newer quarters lack it). "
                   "A broad gauge of consumer and business spending.")
    else:
        st.caption("The sales and use tax base reported by businesses each quarter (taxable sales plus taxable purchases), "
                   "in current dollars, not adjusted for inflation. A broad gauge of consumer and business spending.")
    tot = i.groupby("quarter").value.sum().sort_index()
    last = tot.index.max()
    yago = last - pd.DateOffset(years=1)
    l4 = tot[tot.index > yago].sum()
    p4 = tot[(tot.index <= yago) & (tot.index > yago - pd.DateOffset(years=1))].sum()
    k = st.columns(3)
    k[0].metric(f"Statewide, {lib.quarter_label(last)}", lib.money(tot.iloc[-1]),
                lib.pct((tot.iloc[-1] / tot.get(yago) - 1) * 100) + " vs same quarter last year" if yago in tot else None)
    k[1].metric("Last 4 quarters", lib.money(l4), lib.pct((l4 / p4 - 1) * 100) + " vs prior 4 quarters")
    cols = st.columns([3, 2])
    with cols[0]:
        fig = go.Figure(go.Bar(x=tot.index, y=tot.values / 1e9, marker=dict(color=lib.ACCENT, cornerradius=3),
                               hovertemplate="%{x|%Y Q%q}: $%{y:.2f} billion<extra></extra>", name="Taxable sales"))
        lib.show(lib.layout(fig, 340, "$ billions" + (" (inflation-adjusted)" if real else ""), legend=False), "ts_total",
                 title="Statewide, by filing quarter" + (", inflation-adjusted" if real else ""))
    q4 = i[i.quarter > yago].groupby("industry").value.sum()
    p = i[(i.quarter <= yago) & (i.quarter > yago - pd.DateOffset(years=1))].groupby("industry").value.sum()
    chg = ((q4 / p - 1) * 100).sort_values()
    with cols[1]:
        fig = go.Figure(go.Bar(y=chg.index, x=chg.values, orientation="h", marker=dict(color=lib.ACCENT, cornerradius=3),
                               hovertemplate="%{y}: %{x:+.1f}%<extra></extra>"))
        fig.add_vline(x=0, line_color="gray", line_width=1)
        lib.show(lib.layout(fig, 340, legend=False), "ts_industry", title="Change by industry, last 4 quarters vs prior 4 (%)")
    t = pd.DataFrame({"Industry": q4.index, "Last 4 quarters ($)": q4.values, "Prior 4 quarters ($)": p.reindex(q4.index).values})
    t["Change (%)"] = (t.iloc[:, 1] / t.iloc[:, 2] - 1) * 100
    lib.data_table(t.sort_values("Last 4 quarters ($)", ascending=False).round(1), key="taxable_sales_industry",
                   fmt={"Change (%)": "%.1f"})
    taxable_regions(i.quarter.max(), pce if real else None)
    fy = fiscal_years(tot)
    if len(fy):
        st.markdown("**By state fiscal year (July to June)**")
        st.dataframe(fy, hide_index=True, width="stretch", column_config={
            "Taxable sales and purchases ($ billions)": st.column_config.NumberColumn(format="%.2f"),
            "Change from year before (%)": st.column_config.NumberColumn(format="%+.1f")})
        st.caption("Complete fiscal years only, by filing quarter, " + ("in today's dollars." if real else "current dollars.")
                   + " The state budget uses fiscal years and two-year bienniums starting in odd years.")


def page():
    lib.header("Business pulse", "How many new businesses are starting in North Dakota, how many open and close, "
               "and how much taxable spending is moving, compared with neighboring states and the nation.",
               "official", note="Census Bureau and ND Tax Commissioner. Rates and indexes: IPBA calculations.")
    if not lib.ready():
        return
    applications()
    st.divider()
    openings()
    st.divider()
    young_firms()
    st.divider()
    taxable_sales()
    lib.method_panel([
        "Business applications: Census Business Formation Statistics, not seasonally adjusted, summed over 12 months; "
        "per 1,000 residents uses each year's population (Census Population Estimates). The monthly figure is seasonally adjusted.",
        "Openings and closings: establishment entry and exit rates from Business Dynamics Statistics (March to March).",
        "Young firms: jobs at firms aged 0-5 years as a share of all jobs at firms (BDS firm-age tables).",
        "Taxable sales and purchases: ND Tax Commissioner, by filing quarter (returns filed in the quarter, mostly for "
        "the quarter before). Shown in today's dollars with the GDP price index (BEA) unless the inflation switch is "
        "off. Fiscal years run July to June and sum the four filing quarters.",
        "New-firm survival: firms aged 5 in a year divided by new firms (age 0) five years earlier (BDS). BDS dates a "
        "firm by its oldest location, so mergers can move firms between age classes; the ratio approximates the "
        "share of new firms still operating."],
        ["bayard2018", "haltiwanger2013", "decker2014"])
    lib.source_line("bfs", "bds", "taxable_sales", "pce", "popest",
                    note="Neighboring (peer) states: Minnesota, Montana, South Dakota and Wyoming.")


if __name__ == "__main__":
    page()
