"""Cost of doing business: prices and rents, energy, wages and state taxes, North Dakota against peers and the US.
Each measure keeps its own scale; there is no combined index."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT, PEER_NAMES

ORDER = ["ND", "MN", "MT", "SD", "WY", "US"]
RPP = {"rpp_all": "All items", "rpp_goods": "Goods", "rpp_housing": "Housing rents", "rpp_utilities": "Utilities",
       "rpp_other": "Other services"}


def ready():
    if not (OUT / "cost_business.csv").exists():
        st.info("The cost of doing business table has not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def latest(t, measure):
    """Latest value of a measure for each place (a place's own latest year when a value is withheld)."""
    m = t[t.measure == measure].dropna(subset=["value"]).sort_values("year")
    return m.groupby("geo").tail(1).set_index("geo")


def bars(df, value, title, key, fmt, unit):
    df = df.reindex([g for g in ORDER if g in df.index])
    colors = [lib.ACCENT if g == "ND" else (lib.UND_GRAY if g == "US" else lib.GEO_COLORS.get(g, lib.UND_GRAY)) for g in df.index]
    fig = go.Figure(go.Bar(x=[PEER_NAMES[g] for g in df.index], y=df[value], marker=dict(color=colors, line=dict(width=0)),
                           text=[fmt.format(v) for v in df[value]], textposition="outside",
                           customdata=df.year, hovertemplate="%{x}: %{text} (%{customdata})<extra></extra>"))
    lib.layout(fig, 320, unit, legend=False)
    fig.update_yaxes(range=[0, df[value].max() * 1.18])
    lib.show(fig, key, title=title)


def headline(t):
    k = st.columns(4)
    r = latest(t, "rpp_all")
    k[0].metric(f"Overall price level, {int(r.loc['ND', 'year'])}", f"{r.loc['ND', 'value']:.1f}", "US = 100",
                delta_color="off", delta_arrow="off")
    e = latest(t, "elec_commercial")
    k[1].metric(f"Electricity for businesses, {int(e.loc['ND', 'year'])}", f"{e.loc['ND', 'value']:.2f}¢ per kWh",
                f"US {e.loc['US', 'value']:.2f}¢ (commercial)", delta_color="off", delta_arrow="off")
    p = latest(t, "pay_private")
    k[2].metric(f"Average private-sector pay, {int(p.loc['ND', 'year'])}", f"${p.loc['ND', 'value']:,.0f}",
                f"US ${p.loc['US', 'value']:,.0f}", delta_color="off", delta_arrow="off")
    x = latest(t, "tax_state_ex_severance_pc")
    k[3].metric(f"State taxes per resident, FY{int(x.loc['ND', 'year'])}", f"${x.loc['ND', 'value']:,.0f}",
                f"US ${x.loc['US', 'value']:,.0f}; excluding oil and gas severance taxes", delta_color="off",
                delta_arrow="off")


def prices(t):
    st.subheader("Prices and rents")
    y = int(t[t.measure == "rpp_all"].year.max())
    w = t[(t.year == y) & t.measure.isin(RPP)].pivot_table(index="measure", columns="geo", values="value").reindex(list(RPP))
    fig = go.Figure()
    for g in [g for g in ORDER if g in w.columns]:
        fig.add_bar(x=[RPP[m] for m in w.index], y=w[g], name=PEER_NAMES[g], hovertemplate="%{y:.1f}",
                    marker=dict(color=lib.ACCENT if g == "ND" else lib.GEO_COLORS.get(g, lib.UND_GRAY), line=dict(width=0)))
    fig.add_hline(y=100, line_color=lib.UND_GRAY, line_dash="dash", line_width=1)
    fig.update_layout(barmode="group")
    lib.layout(fig, 360, "Price level (US = 100)")
    lib.show(fig, "cost_rpp", title=f"Regional price parities by category, {y} (US = 100)")
    cols = st.columns(2)
    for col, m in zip(cols, ["rpp_all", "rpp_housing"]):
        with col:
            d = t[(t.measure == m)]
            lib.show(lib.geo_lines(d[d.geo.isin(["ND", "MN", "SD", "US"])], "year", "value", ytitle="US = 100", fmt=".1f",
                                   h=300), f"cost_{m}", title=f"{RPP[m]}: price level over time")
    st.caption("BEA Regional Price Parities compare price levels across states in the same year; they are not "
               "inflation rates. Housing covers rents (including the rental value of owned homes), a guide to space "
               "costs; commercial rents are not published by any federal agency.")


def energy(t):
    st.subheader("Energy")
    cols = st.columns(2)
    for col, m, title in ((cols[0], "elec_commercial", "Electricity, commercial customers"),
                          (cols[1], "elec_industrial", "Electricity, industrial customers")):
        with col:
            d = latest(t, m)
            bars(d, "value", f"{title}, {int(d.year.max())} (cents per kWh)", f"cost_{m}", "{:.2f}¢", "Cents per kWh")
    ytd = latest(t, "elec_commercial_ytd")
    if "ND" in ytd.index:
        st.caption(f"This year to date ({int(ytd.loc['ND', 'year'])}): commercial electricity "
                   f"{ytd.loc['ND', 'value']:.2f}¢ per kWh in North Dakota, {ytd.loc['US', 'value']:.2f}¢ in the US.")
    cols = st.columns(2)
    for col, m, title in ((cols[0], "gas_commercial", "Natural gas, commercial customers"),
                          (cols[1], "gas_industrial", "Natural gas, industrial customers")):
        with col:
            d = t[(t.measure == m) & (t.year >= 2005)]
            lib.show(lib.geo_lines(d[d.geo.isin(["ND", "MN", "SD", "US"])], "year", "value",
                                   ytitle="$ per thousand cubic feet", fmt="$.2f", h=300), f"cost_{m}", title=title)
    st.caption("EIA average prices, current dollars, all providers. Gaps mean EIA withheld the value. Industrial gas "
               "prices are averages over large and small users and vary widely by contract.")


def labor(t):
    st.subheader("Wages")
    pay = t[t.measure == "pay_private"]
    rpp = t[t.measure == "rpp_all"].set_index(["geo", "year"]).value
    pay = pay.assign(adjusted=[v / rpp.get((g, min(y, int(rpp.index.get_level_values(1).max())))) * 100
                               for g, v, y in zip(pay.geo, pay.value, pay.year)])
    cols = st.columns(2)
    with cols[0]:
        lib.show(lib.geo_lines(pay[pay.geo.isin(["ND", "MN", "SD", "US"])], "year", "value", ytitle="$ per year",
                               fmt="$,.0f", h=300), "cost_pay", title="Average private-sector pay (current dollars)")
    with cols[1]:
        lib.show(lib.geo_lines(pay[pay.geo.isin(["ND", "MN", "SD", "US"])], "year", "adjusted",
                               ytitle="$ at US price levels", fmt="$,.0f", h=300), "cost_pay_adj",
                 title="Pay adjusted for local price levels")
    st.caption("BLS QCEW average annual pay per private-sector job. Pay is a cost to employers and income to workers; "
               "adjusting for price levels shows what the pay buys locally, which matters for hiring. Wages differ "
               "by occupation (see Workforce and talent).")


def taxes(t):
    st.subheader("State taxes")
    cols = st.columns(2)
    with cols[0]:
        d = latest(t, "tax_state_ex_severance_pc")
        bars(d, "value", f"State taxes per resident excluding severance, FY{int(d.year.max())}", "cost_tax", "${:,.0f}",
             "$ per resident")
    with cols[1]:
        fig = go.Figure()
        for m, name, clr in (("tax_state_pc", "All state taxes", lib.SECOND), ("tax_state_ex_severance_pc",
                                                                                "Excluding oil and gas severance", lib.ACCENT)):
            s = t[(t.measure == m) & (t.geo == "ND")]
            fig.add_scatter(x=s.year, y=s.value, name=name, mode="lines", line=dict(color=clr, width=2.4,
                            dash="solid" if m == "tax_state_ex_severance_pc" else "dash"), hovertemplate="$%{y:,.0f}")
        lib.layout(fig, 320, "$ per resident")
        lib.show(fig, "cost_tax_nd", title="North Dakota state taxes per resident, with and without severance taxes")
    corp = latest(t, "tax_corporate_pc")
    st.caption(f"Census state tax collections (state government only; local property and sales taxes are not "
               f"included) divided by residents, fiscal years. Severance taxes on oil and gas are paid mostly by "
               f"producers and swing with oil prices, so the comparison leaves them out. Corporate income tax per "
               f"resident, FY{int(corp.loc['ND', 'year'])}: North Dakota ${corp.loc['ND', 'value']:,.0f}, US "
               f"${corp.loc['US', 'value']:,.0f}. Collections per resident are not the tax bill of a particular "
               f"business.")


def summary(t):
    rows = {}
    labels = {"rpp_all": "Overall price level (US = 100)", "rpp_housing": "Housing rents (US = 100)",
              "elec_commercial": "Electricity, commercial (¢/kWh)", "elec_industrial": "Electricity, industrial (¢/kWh)",
              "gas_commercial": "Natural gas, commercial ($/Mcf)", "gas_industrial": "Natural gas, industrial ($/Mcf)",
              "pay_private": "Average private pay ($)", "tax_state_ex_severance_pc": "State taxes per resident, excl. severance ($)",
              "tax_corporate_pc": "Corporate income tax per resident ($)"}
    for m, lab in labels.items():
        d = latest(t, m)
        rows[lab] = {PEER_NAMES[g]: d.value.get(g) for g in ORDER}
        rows[lab]["Year"] = int(d.year.max())
    tab = pd.DataFrame(rows).T
    lib.data_table(tab.round(2).reset_index().rename(columns={"index": "Measure"}), "All measures, latest year (table)",
                   key="cost_summary")


def page():
    lib.header("Cost of doing business", "What it costs to operate in North Dakota compared with neighboring states "
               "and the nation: prices and rents, energy, wages and state taxes.", "official", "estimate",
               note="BEA, EIA, BLS and Census Bureau. Per-resident and price-adjusted values: IPBA calculations.")
    if not ready():
        return
    t = lib.table("cost_business.csv")
    headline(t)
    st.caption("Each cost is shown on its own scale. There is no single cost index, because the right weights differ "
               "from one business to another (an energy-heavy plant and a software firm face very different mixes).")
    st.divider()
    prices(t)
    st.divider()
    energy(t)
    st.divider()
    labor(t)
    st.divider()
    taxes(t)
    summary(t)
    lib.method_panel([
        "Prices: BEA Regional Price Parities by state, US = 100, for all items, goods, housing rents, utilities and "
        "other services.",
        "Energy: EIA average retail electricity prices by sector (Electric Power Annual table 2.10; Electric Power "
        "Monthly table 5.6.B for this year to date) and natural gas prices to commercial and industrial consumers.",
        "Wages: BLS QCEW average annual pay, private ownership, all industries; adjusted pay = pay / price level × 100.",
        "Taxes: Census Annual Survey of State Government Tax Collections, state government only, per resident (Census "
        "population estimates); severance taxes (T53) shown separately; corporate net income tax (T41).",
        "Not covered: commercial rents and land, insurance, local property tax rates, regulation and permitting "
        "time, which have no consistent public data by state."])
    lib.source_line("bea_rpp", "eia_prices", "qcew", "census_stc", "popest")


if __name__ == "__main__":
    page()
