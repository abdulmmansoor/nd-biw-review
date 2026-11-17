"""Retail gap: where residents' spending stays local and where it leaks to other places, by store type (2022)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import COUNTIES, OUT, REGIONS

LEAK, PULL = "#E5734B", lib.UND_GREEN
DIVERGING = [[0, "#E5734B"], [0.5, "#F1F3F5"], [1, "#2E8B57"]]      # leakage - balance - surplus, centred on 1


def ready():
    if not (OUT / "retail_gap.csv").exists():
        st.info("The retail gap table has not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def reading(pf):
    if pd.isna(pf):
        return "withheld"
    if pf >= 1.1:
        return "draws shoppers (surplus)"
    if pf <= 0.9:
        return "spending leaks out"
    return "about balanced"


def money_k(x):
    return lib.money(x * 1000) if pd.notna(x) else "withheld"


def profile(t, level, place):
    p = t[(t.level == level) & (t.place == place)].set_index("naics")
    tot, food = p.loc["44-45"], p.loc["722"] if "722" in p.index else None
    k = st.columns(4)
    k[0].metric("Retail store sales, 2022", money_k(tot.sales_k),
                "estimated (county data withheld)" if tot.estimated else f"{tot.estab:,.0f} stores",
                delta_color="off", delta_arrow="off")
    k[1].metric("Expected from residents' income", money_k(tot.expected_k))
    k[2].metric("Retail pull factor", f"{tot.pull_factor:.2f}", reading(tot.pull_factor), delta_color="off",
                delta_arrow="off", help="Actual sales / expected sales. Above 1: the place draws shoppers; below 1: "
                                        "residents shop elsewhere (including online).")
    gap = tot.gap_k
    k[3].metric("Leakage" if gap > 0 else "Surplus", money_k(abs(gap)),
                "spent outside the place" if gap > 0 else "drawn from outside", delta_color="off", delta_arrow="off")
    if food is not None and pd.notna(food.pull_factor):
        st.caption(f"Restaurants and bars: pull factor {food.pull_factor:.2f}, {reading(food.pull_factor)}; sales "
                   f"{money_k(food.sales_k)}{' (estimated)' if food.estimated else ''}.")
    cats = p.drop(index=["44-45"], errors="ignore").reset_index()
    shown = cats.dropna(subset=["pull_factor"]).sort_values("pull_factor")
    hidden = cats[cats.pull_factor.isna()].store_type.tolist()
    if len(shown):
        fig = go.Figure(go.Bar(y=shown.store_type, x=shown.pull_factor, orientation="h",
                               marker=dict(color=[PULL if v >= 1 else LEAK for v in shown.pull_factor], line=dict(width=0)),
                               customdata=shown[["sales_k", "expected_k"]].values / 1000,
                               hovertemplate="%{y}: %{x:.2f} (sales $%{customdata[0]:,.1f}M, expected "
                                             "$%{customdata[1]:,.1f}M)<extra></extra>"))
        fig.add_vline(x=1, line_color=lib.UND_GRAY, line_dash="dash", line_width=1)
        lib.layout(fig, 60 + 34 * len(shown), legend=False).update_xaxes(title="Pull factor (1 = balanced)")
        lib.show(fig, "rg_types", title="Pull factor by store type, 2022")
    if hidden:
        st.caption("Withheld by the Census Bureau for this place, to protect individual businesses: " + ", ".join(hidden) + ".")
    tab = cats.assign(reading=cats.pull_factor.map(reading)).sort_values("expected_k", ascending=False)
    lib.data_table(tab[["store_type", "sales_k", "expected_k", "pull_factor", "gap_k", "estab", "reading"]].rename(columns={
        "store_type": "Store type", "sales_k": "Sales ($1,000)", "expected_k": "Expected ($1,000)",
        "pull_factor": "Pull factor", "gap_k": "Leakage (+) or surplus (-) ($1,000)", "estab": "Stores",
        "reading": "Reading"}).round(2), "Store types (table)", key=f"rg_{level}")


def county_map(t, selected):
    import page_market
    acs = lib.table("acs_places.csv")
    fips = acs[acs.level == "county"].set_index("county").code.astype(str)
    c = t[(t.level == "county") & (t.naics == "44-45")].copy()
    c["fips"] = c.place.map(fips)
    c["pf"] = c.pull_factor.clip(upper=2)                  # cap so one outlier does not wash out the scale
    c["note"] = c.estimated.map({True: " (estimated)", False: ""})
    fig = go.Figure(go.Choropleth(geojson=page_market.geojson(), locations=c.fips, z=c.pf, featureidkey="id",
                                  colorscale=DIVERGING, zmin=0, zmax=2, marker_line_color=lib.PANEL,
                                  marker_line_width=0.6, text=c.place, customdata=c[["pull_factor", "note"]].values,
                                  hovertemplate="%{text}: %{customdata[0]:.2f}%{customdata[1]}<extra></extra>",
                                  colorbar=dict(title=None, thickness=12, tickvals=[0, .5, 1, 1.5, 2],
                                                ticktext=["0", "0.5", "1 balanced", "1.5", "2+"],
                                                tickfont=dict(color=lib.MUTED))))
    sel = c[c.place.isin(selected)]
    fig.add_trace(go.Choropleth(geojson=page_market.geojson(), locations=sel.fips, z=[1] * len(sel), featureidkey="id",
                                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
                                marker_line_color="#FFFFFF", marker_line_width=2.5, hoverinfo="skip"))
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(height=470, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor=lib.PANEL,
                      geo=dict(bgcolor=lib.PANEL), font=dict(color=lib.INK), showlegend=False)
    lib.show(fig, "rg_map", title="Retail pull factor by county, 2022 (orange: leakage, green: surplus)")
    st.caption("The selected place is outlined in white. Values above 2 are shown at the top of the scale.")
    tab = c.sort_values("pull_factor", ascending=False)
    tab = tab.assign(reading=tab.pull_factor.map(reading), estimated=tab.estimated.map({True: "Yes", False: ""}))
    lib.data_table(tab[["place", "sales_k", "expected_k", "pull_factor", "gap_k", "reading", "estimated"]].rename(columns={
        "place": "County", "sales_k": "Retail sales ($1,000)", "expected_k": "Expected ($1,000)", "pull_factor": "Pull factor",
        "gap_k": "Leakage (+) or surplus (-) ($1,000)", "reading": "Reading", "estimated": "Estimated"}).round(2),
        "All counties (table)", key="rg_counties")


SPEND_LINES = [4, 5, 6, 7, 9, 10, 11, 12, 15, 16, 17, 18, 19, 20, 21]     # detailed goods and services categories


def spending():
    if not (OUT / "consumer_spending.csv").exists():
        return
    s = lib.table("consumer_spending.csv")
    y = int(s.year.max())
    st.subheader(f"What residents spend: consumer spending per resident, {y}")
    tot = s[s.line == 1]
    nd, us = tot[(tot.geo == "ND") & (tot.year == y)].value.iloc[0], tot[(tot.geo == "US") & (tot.year == y)].value.iloc[0]
    nd5 = tot[(tot.geo == "ND") & (tot.year == y - 10)].value
    k = st.columns(3)
    k[0].metric("Spending per resident, North Dakota", f"${nd:,.0f}", f"US ${us:,.0f}", delta_color="off", delta_arrow="off")
    if len(nd5):
        k[1].metric(f"Growth since {y - 10}", f"{((nd / nd5.iloc[0]) ** (1 / 10) - 1) * 100:+.1f}% a year",
                    "current dollars", delta_color="off", delta_arrow="off")
    goods = s[(s.line == 2) & (s.year == y)].set_index("geo").value
    k[2].metric("Spent on goods (the retail share)", f"{goods['ND'] / nd * 100:.0f}%", f"US {goods['US'] / us * 100:.0f}%",
                delta_color="off", delta_arrow="off")
    cols = st.columns([3, 2])
    with cols[0]:
        sel = tot[tot.geo.isin(lib.pick_places("sp_places"))]
        lib.show(lib.geo_lines(sel, "year", "value", ytitle="$ per resident", fmt="$,.0f", h=340), "sp_trend",
                 title="Consumer spending per resident (current dollars)")
    with cols[1]:
        c = s[(s.year == y) & s.line.isin(SPEND_LINES) & s.geo.isin(["ND", "US"])].pivot_table(
            index="category", columns="geo", values="value")
        c["ratio"] = c.ND / c.US
        c = c.sort_values("ratio")
        fig = go.Figure(go.Bar(y=c.index, x=c.ratio, orientation="h",
                               marker=dict(color=[PULL if v >= 1 else LEAK for v in c.ratio], line=dict(width=0)),
                               customdata=c[["ND", "US"]].values,
                               hovertemplate="%{y}: %{x:.2f} (ND $%{customdata[0]:,.0f}, US $%{customdata[1]:,.0f})"
                                             "<extra></extra>"))
        fig.add_vline(x=1, line_color=lib.UND_GRAY, line_dash="dash", line_width=1)
        lib.layout(fig, 340 + 6 * len(c), legend=False).update_xaxes(title="ND per resident / US per resident")
        lib.show(fig, "sp_cats", title=f"North Dakota spending compared with the US, by category, {y}")
    t = s[(s.year == y) & s.line.isin([1, 2, 13] + SPEND_LINES)].pivot_table(index=["line", "category"], columns="geo",
                                                                            values="value").reset_index()
    lib.data_table(t.drop(columns="line").rename(columns={"category": "Category"}).rename(columns=lib.PEER_NAMES).round(0),
                   "Spending per resident by category (table)", key="spending")
    st.caption("BEA personal consumption expenditures by state of residence, in current dollars; not adjusted for "
               "differences in prices between states. The latest year is preliminary. Spending is by residents "
               "wherever it happens, including online and while travelling.")


def page():
    lib.header("Retail gap", "Where residents' spending stays in their own county or region, and where it goes to "
               "other places, by type of store: a guide to retail opportunities and to how far shoppers travel.",
               "official", "estimate", note="Census Bureau. Expected sales, pull factors and gaps: IPBA calculations.")
    if not ready():
        return
    t = lib.table("retail_gap.csv", dtype={"naics": str})
    c = st.columns([1, 2])
    level = c[0].radio("Look at", ["County", "Planning region"], horizontal=True, key="rg_level")
    if level == "County":
        names = sorted(COUNTIES.values())
        place = c[1].selectbox("County", names, index=names.index("Cass"), key="rg_county")
        members, lvl = [place], "county"
        st.markdown(f"### {place} County")
    else:
        place = c[1].selectbox("Planning region", list(REGIONS), key="rg_region")
        members, lvl = REGIONS[place], "region"
        st.markdown(f"### {place}  \n<span style='opacity:.75'>Counties: {', '.join(members)}</span>",
                    unsafe_allow_html=True)
    profile(t, lvl, place)
    st.divider()
    st.subheader("Compare counties")
    county_map(t, members)
    st.divider()
    spending()
    lib.method_panel([
        "Expected sales = North Dakota sales in the store type × the place's share of state household income (ACS "
        "aggregate income, 2020-2024). Pull factor = actual sales / expected sales; gap = expected - actual "
        "(Hustedde et al., 1984). The state is the benchmark, so North Dakota's pull factor is 1 by definition.",
        "Sales: 2022 Economic Census, all establishments, by store location. Sales include purchases by farms, "
        "businesses and visitors, so a large fuel, vehicle or building supply dealer serving farms or oil sites can "
        "lift a small county's pull factor; online purchases count where the seller is, which shows up as leakage.",
        "Withheld counties: the Census Bureau withholds sales where a few stores would be identifiable. For all retail "
        "and for restaurants, the part of the state total not shown for any county is shared among the withheld "
        "counties by expected sales and marked estimated; store types are not estimated.",
        "The pull factor measures where spending happens, not whether a new store would succeed: it does not account "
        "for store size, competition, rent, travel times or visitor and cross-border shoppers."],
        ["hustedde1984"])
    lib.source_line("econ_census", "acs", "bea_pce_state")


if __name__ == "__main__":
    page()
