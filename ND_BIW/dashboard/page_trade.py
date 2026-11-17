"""Trade and exports: how much North Dakota sells abroad, compared with its neighbors, and what its farms export."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT, PEER_NAMES

TOTALS = ["Total agricultural exports", "Total plant products", "Total animal products"]


def ready():
    if not ((OUT / "trade_exports.csv").exists() and (OUT / "trade_ag_exports.csv").exists()):
        st.info("The trade tables have not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def per_resident(full):
    """Goods exports per resident and as a share of GDP, by place and year."""
    pop = lib.table("population_annual.csv").set_index(["geo", "year"]).population
    gdp = lib.table("bea_gdp.csv")
    gdp = gdp[(gdp.industry == "total") & (gdp.measure == "current")].set_index(["geo", "year"]).value
    f = full.copy()
    idx = list(zip(f.geo, f.year))
    f["per_resident"] = f.total * 1e6 / pd.Series(pop.reindex(idx).values, index=f.index)
    f["share_gdp"] = f.total / pd.Series(gdp.reindex(idx).values, index=f.index) * 100
    return f


def goods():
    x = lib.table("trade_exports.csv")
    full = per_resident(x[x.months == 12])
    y = int(full.year.max())
    nd = full[full.geo == "ND"].set_index("year")
    st.subheader("Goods exports")
    k = st.columns(4)
    k[0].metric(f"North Dakota goods exports, {y}", lib.money(nd.loc[y, "total"] * 1e6),
                f"{(nd.loc[y, 'total'] / nd.loc[y - 1, 'total'] - 1) * 100:+.1f}% vs {y - 1}" if y - 1 in nd.index else None,
                delta_color="off", delta_arrow="off")
    ytd = x[x.months < 12]
    if len(ytd):
        ly, m = int(ytd.year.max()), int(ytd.months.max())
        a = ytd[(ytd.geo == "ND") & (ytd.year == ly)].total
        b = ytd[(ytd.geo == "ND") & (ytd.year == ly - 1)].total
        mon = pd.Timestamp(ly, m, 1)
        if len(a) and len(b):
            k[1].metric(f"January to {mon:%B} {ly}", lib.money(a.iloc[0] * 1e6),
                        f"{(a.iloc[0] / b.iloc[0] - 1) * 100:+.1f}% vs same months of {ly - 1}", delta_color="off",
                        delta_arrow="off")
    latest = full[full.year == y].set_index("geo")
    k[2].metric("Exports per resident", f"${latest.loc['ND', 'per_resident']:,.0f}",
                f"US ${latest.loc['US', 'per_resident']:,.0f}", delta_color="off", delta_arrow="off")
    if pd.notna(latest.loc["ND", "share_gdp"]):
        k[3].metric("Goods exports as % of GDP", f"{latest.loc['ND', 'share_gdp']:.1f}%",
                    f"US {latest.loc['US', 'share_gdp']:.1f}%", delta_color="off", delta_arrow="off")
    cols = st.columns(2)
    with cols[0]:
        sel = full[full.geo.isin(lib.pick_places("tr_places", default=("ND", "MN", "SD", "US")))]
        lib.show(lib.geo_lines(sel, "year", "per_resident", ytitle="$ per resident", fmt="$,.0f", h=340), "tr_pc",
                 title="Goods exports per resident")
    with cols[1]:
        fig = go.Figure()
        for col, name, clr in (("manufactured", "Manufactured", lib.ACCENT),
                               ("non_manufactured", "Farm, mining and other raw goods", lib.SECOND),
                               ("reexports", "Reexports", lib.UND_GRAY)):
            fig.add_bar(x=nd.index, y=nd[col] / 1e3, name=name, marker=dict(color=clr, line=dict(width=0)),
                        hovertemplate="%{x}: $%{y:.2f}B")
        fig.update_layout(barmode="stack")
        lib.layout(fig, 340, "$ billions").update_xaxes(dtick=1)
        lib.show(fig, "tr_mix", title="North Dakota goods exports by type")
    t = full.pivot_table(index="year", columns="geo", values=["total", "per_resident"])
    t.columns = [f"{PEER_NAMES[g]}: {'exports ($M)' if a == 'total' else 'per resident ($)'}" for a, g in t.columns]
    lib.data_table(t.round(0).reset_index(), "Goods exports by place (table)", key="trade_states")
    st.caption("ZIP-code based series: Census places each shipment by the ZIP code the exporter reports as its "
               "origin, which is often the exporter's office rather than where the goods start moving. Current "
               "dollars; services exports (tourism, education, software) are not included.")


def detail():
    """Products (HS chapters) and destination countries, when the Census trade API data have been built."""
    if not ((OUT / "trade_products.csv").exists() and (OUT / "trade_destinations.csv").exists()):
        st.caption("Exports by product and destination country appear here once a Census API key is saved "
                   "(Set_Census_Key.bat) and the data are updated.")
        return
    p = lib.table("trade_products.csv", dtype={"hs2": str})
    d = lib.table("trade_destinations.csv", dtype={"country_code": str})
    years = sorted(p[p.months == 12].year.unique(), reverse=True)
    st.subheader("Goods leaving North Dakota: products and destinations")
    c = st.columns([1, 3])
    y = c[0].selectbox("Year", years, key="tr_year")
    pp = p[(p.year == y) & (p.months == 12)].sort_values("value", ascending=False)
    dd = d[(d.year == y) & (d.months == 12)].sort_values("value", ascending=False)
    tot = dd.value.sum()
    fuels = pp[pp.hs2 == "27"].value.sum()
    z = lib.table("trade_exports.csv")
    zip_tot = z[(z.geo == "ND") & (z.year == y) & (z.months == 12)].total
    k = st.columns(4)
    k[0].metric(f"Goods starting their trip in ND, {y}", lib.money(tot * 1e6),
                f"{lib.money((tot - fuels) * 1e6)} without mineral fuels", delta_color="off", delta_arrow="off",
                help="State where goods begin their journey to the port of export (Census origin-of-movement series).")
    if len(zip_tot):
        k[1].metric("ZIP-code based total (above)", lib.money(zip_tot.iloc[0] * 1e6), "different basis; see note",
                    delta_color="off", delta_arrow="off")
    k[2].metric(f"Largest product group, {y}", pp["product"].iloc[0], lib.money(pp.value.iloc[0] * 1e6),
                delta_color="off", delta_arrow="off")
    k[3].metric(f"Largest market, {y}", dd.country.iloc[0], f"{dd.value.iloc[0] / tot * 100:.0f}% of exports; "
                f"{(dd.value > 0).sum():,} countries in all", delta_color="off", delta_arrow="off")
    cols = st.columns(2)
    with cols[0]:
        top = pp.head(12).iloc[::-1]
        fig = go.Figure(go.Bar(y=top["product"].str.slice(0, 40), x=top.value, orientation="h",
                               marker=dict(color=lib.ACCENT, line=dict(width=0)),
                               hovertemplate="%{y}: $%{x:,.1f}M<extra></extra>"))
        lib.layout(fig, 440, legend=False).update_xaxes(title="$ millions")
        lib.show(fig, "tr_products", title=f"Top 12 product groups (HS chapters), {y}")
    with cols[1]:
        top = dd.head(12).iloc[::-1]
        fig = go.Figure(go.Bar(y=top.country, x=top.value, orientation="h", marker=dict(color=lib.SECOND, line=dict(width=0)),
                               customdata=top.value / tot * 100,
                               hovertemplate="%{y}: $%{x:,.1f}M (%{customdata:.1f}%)<extra></extra>"))
        lib.layout(fig, 440, legend=False).update_xaxes(title="$ millions")
        lib.show(fig, "tr_dest", title=f"Top 12 destination countries, {y}")
    ytd = d[d.months < 12]
    if len(ytd):
        ly, m = int(ytd.year.max()), int(ytd.months.max())
        a = ytd[ytd.year == ly].set_index("country").value
        b = ytd[ytd.year == ly - 1].set_index("country").value
        t = pd.DataFrame({f"Jan-{pd.Timestamp(ly, m, 1):%b} {ly} ($M)": a, f"Same months {ly - 1} ($M)": b}).fillna(0)
        t["Change (%)"] = (t.iloc[:, 0] / t.iloc[:, 1].where(t.iloc[:, 1] > 0) - 1) * 100
        lib.data_table(t.sort_values(t.columns[0], ascending=False).head(25).round(1).reset_index().rename(
            columns={"index": "Country", "country": "Country"}), "Top 25 markets this year so far (table)", key="tr_ytd")
    lib.data_table(pp[["hs2", "product", "value"]].rename(columns={"hs2": "HS chapter", "product": "Product group",
                                                                     "value": "$ millions"}).round(2),
                   f"All product groups, {y} (table)", key="tr_products_t")
    lib.data_table(dd[["country", "value"]].assign(share=dd.value / tot * 100).rename(columns={
        "country": "Country", "value": "$ millions", "share": "% of ND exports"}).round(2),
                   f"All destinations, {y} (table)", key="tr_dest_t")
    st.caption("State-based origin-of-movement series: goods counted in the state where they begin their journey to "
               "the port of export, by Harmonized System chapter and destination country, current dollars. It includes "
               "crude oil and other goods that leave North Dakota by pipeline, rail or truck even when the exporter is "
               "based elsewhere, which is why it is much larger than the ZIP-code based total, and why mineral fuels "
               "and Canada lead. Grain consolidated and shipped from ports in other states counts in those states.")


def farm():
    a = lib.table("trade_ag_exports.csv")
    y = int(a.year.max())
    st.subheader(f"Farm exports by commodity, {y}")
    nd = a[a.geo == "ND"]
    tot = nd[nd.commodity == "Total agricultural exports"].set_index("year").value
    us = a[(a.geo == "US") & (a.commodity == "Total agricultural exports")].set_index("year").value
    k = st.columns(3)
    k[0].metric("North Dakota farm exports (estimated)", lib.money(tot.loc[y] * 1e6),
                f"{(tot.loc[y] / tot.loc[y - 1] - 1) * 100:+.1f}% vs {y - 1}", delta_color="off", delta_arrow="off")
    k[1].metric("Share of US farm exports", f"{tot.loc[y] / us.loc[y] * 100:.1f}%")
    top = nd[(nd.year == y) & ~nd.commodity.isin(TOTALS) & nd.commodity.str.match(r"^(?!Other )")]
    top = top.sort_values("value", ascending=False)
    k[2].metric("Largest commodity", top.commodity.iloc[0], lib.money(top.value.iloc[0] * 1e6), delta_color="off",
                delta_arrow="off")
    cols = st.columns([3, 2])
    with cols[0]:
        c = nd[(nd.year == y) & ~nd.commodity.isin(TOTALS) & (nd.value > 0)].sort_values("value")
        fig = go.Figure(go.Bar(y=c.commodity, x=c.value, orientation="h", marker=dict(color=lib.ACCENT, line=dict(width=0)),
                               hovertemplate="%{y}: $%{x:,.0f}M<extra></extra>"))
        lib.layout(fig, 480, legend=False).update_xaxes(title="$ millions")
        lib.show(fig, "tr_ag", title=f"North Dakota farm exports by commodity, {y} ($ millions)")
    with cols[1]:
        sh = (tot / us * 100).rename("share").reset_index().assign(geo="ND")
        lib.show(lib.geo_lines(sh, "year", "share", ytitle="% of US farm exports", fmt=".2f", h=480), "tr_ag_share",
                 title="North Dakota's share of US farm exports (%)")
    w = nd.pivot_table(index="year", columns="commodity", values="value")
    lib.data_table(w.round(1).reset_index(), "Farm exports by commodity and year, $ millions (table)", key="trade_ag")
    st.caption("USDA estimates each state's farm exports from its share of US production, so North Dakota is credited "
               "with crops grown here even when they are shipped abroad by firms in other states. It measures something "
               "different from the Census series above; the series should not be added or compared directly.")


def page():
    lib.header("Trade and exports", "How much North Dakota sells to other countries, how that compares with "
               "neighboring states, and which farm products carry the state's exports.", "official", "estimate",
               note="Census Bureau and USDA. Per-resident and GDP shares: IPBA calculations.")
    if not ready():
        return
    goods()
    detail()
    st.divider()
    farm()
    lib.method_panel([
        "Goods exports, two Census origin-of-movement series: (1) ZIP-code based, by the ZIP code the exporter "
        "reports, available for every state by product type (manufactured = NAICS 31-33; non-manufactured = farm, "
        "forestry, fishing, mining, scrap and used goods; reexports = foreign goods exported again unchanged); "
        "(2) state based, by the state where goods begin their journey to the port, used for products (HS chapters) "
        "and destinations. Census advises against comparing them or computing state trade balances. The latest "
        "year is year to date and is compared with the same months a year earlier.",
        "Per resident uses Census population estimates; share of GDP uses BEA state GDP in current dollars.",
        "Farm exports: USDA Economic Research Service estimates, which share national farm exports out to states by "
        "production (cash receipts). They measure how much of a state's farm output is sold abroad, not where the "
        "exporter is located."])
    lib.source_line("census_exports", "census_trade_api", "ers_trade", "popest", "bea")


if __name__ == "__main__":
    page()
