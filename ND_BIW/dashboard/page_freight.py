"""Freight and supply chain: what moves into, out of, within and through North Dakota, how, and where (FAF5)."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT, PEER_NAMES

OUTBOUND = ["To other states", "Exports from North Dakota"]
INBOUND = ["From other states", "Imports to North Dakota"]
WITHIN = ["Within North Dakota"]
THROUGH = ["Exports of other states leaving through North Dakota",
           "Imports to other states entering through North Dakota"]
GROUPS = {"Leaving North Dakota": OUTBOUND, "Arriving in North Dakota": INBOUND, "Within North Dakota": WITHIN,
          "Crossing ND's border (other states' trade)": THROUGH}
SHORT_TONS_PER_BARREL = 0.143     # Bakken crude, about 42 degrees API (specific gravity 0.816)


def ready():
    if not all((OUT / f).exists() for f in ("freight_nd.csv", "freight_partners.csv", "freight_states.csv")):
        st.info("The freight tables have not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def measure_pick(key):
    m = st.radio("Measure", ["Tons", "Value"], horizontal=True, key=key,
                 help="Tons: weight moved (short tons). Value: value of the goods, current dollars.")
    return ("tons_k", 1e3, "million tons", ",.1f") if m == "Tons" else ("current_value_m", 1e3, "$ billions", "$,.1f")


def group_of(flow):
    return next(g for g, fl in GROUPS.items() if flow in fl)


def headline(f, y):
    cur = f[f.year == y]
    by = cur.groupby("flow")[["tons_k", "current_value_m"]].sum()
    start = by.loc[WITHIN + OUTBOUND].sum()
    arrive = by.loc[INBOUND].sum()
    through = by.reindex(THROUGH).fillna(0).sum()
    out = cur[cur.flow.isin(OUTBOUND)]
    rp = out[out["mode"].isin(["Rail", "Pipeline"])].tons_k.sum() / out.tons_k.sum() * 100
    k = st.columns(4)
    k[0].metric(f"Freight starting in North Dakota, {y} (million tons)", f"{start.tons_k / 1e3:,.0f}",
                f"worth {lib.money(start.current_value_m * 1e6)}", delta_color="off", delta_arrow="off",
                help="Moved within the state, to other states, or abroad.")
    k[1].metric("Arriving from other states and abroad (million tons)", f"{arrive.tons_k / 1e3:,.0f}",
                f"worth {lib.money(arrive.current_value_m * 1e6)}", delta_color="off", delta_arrow="off")
    k[2].metric("Leaving by rail or pipeline (share of tons)", f"{rp:.0f}%",
                "of freight leaving for other states and abroad", delta_color="off", delta_arrow="off")
    k[3].metric("Other states' trade crossing ND's border (million tons)", f"{through.tons_k / 1e3:,.0f}",
                f"worth {lib.money(through.current_value_m * 1e6)}", delta_color="off", delta_arrow="off",
                help="Imports and exports of other states that enter or leave the US at North Dakota's border.")


def flows_chart(f, y):
    col, div, unit, fmt = measure_pick("fr_m_flows")
    v = f[f.year == y].groupby("flow")[col].sum().reindex(lib_order()).fillna(0) / div
    fig = go.Figure(go.Bar(y=v.index[::-1], x=v.values[::-1], orientation="h",
                           marker=dict(color=[lib.UND_GRAY if i in THROUGH else lib.ACCENT for i in v.index[::-1]],
                                       cornerradius=3),
                           hovertemplate="%{y}: %{x:" + fmt + "} " + unit + "<extra></extra>"))
    lib.layout(fig, 330, legend=False).update_xaxes(title=unit)
    lib.show(fig, "fr_flows", title=f"Freight by direction, {y}")
    st.caption("Gray bars are other states' imports and exports that only cross North Dakota's border, mostly "
               "Canadian crude oil by pipeline; they are not North Dakota's own trade.")


def lib_order():
    return WITHIN + OUTBOUND + INBOUND + THROUGH


def commodities(f, y):
    st.subheader("What moves")
    c = st.columns([2, 1])
    grp = c[0].selectbox("Direction", list(GROUPS), key="fr_dir")
    with c[1]:
        col, div, unit, fmt = measure_pick("fr_m_comm")
    cur = f[(f.year == y) & f.flow.isin(GROUPS[grp])]
    v = cur.groupby("commodity")[col].sum().sort_values(ascending=False) / div
    top = v.head(15)[::-1]
    fig = go.Figure(go.Bar(y=top.index, x=top.values, orientation="h", marker=dict(color=lib.ACCENT, cornerradius=3),
                           hovertemplate="%{y}: %{x:" + fmt + "} " + unit + "<extra></extra>"))
    lib.layout(fig, 460, legend=False).update_xaxes(title=unit)
    lib.show(fig, "fr_comm", title=f"Top 15 goods, {grp.lower()}, {y}")
    t = cur.groupby("commodity")[["tons_k", "current_value_m"]].sum()
    t["Value per ton ($)"] = t.current_value_m * 1e6 / (t.tons_k * 1e3)
    t["Share of tons (%)"] = t.tons_k / t.tons_k.sum() * 100
    lib.data_table(t.sort_values("tons_k", ascending=False).rename(columns={
        "tons_k": "Thousand tons", "current_value_m": "Value ($ millions)"}).round(1).reset_index().rename(
        columns={"commodity": "Goods (SCTG)"}), f"All goods, {grp.lower()}, {y} (table)", key="fr_comm_t")


def modes(f, y):
    st.subheader("How it moves")
    col, div, unit, fmt = measure_pick("fr_m_mode")
    cur = f[f.year == y].copy()
    cur["group"] = cur.flow.map(group_of)
    w = cur.pivot_table(index="group", columns="mode", values=col, aggfunc="sum").reindex(list(GROUPS)).fillna(0)
    sh = w.div(w.sum(axis=1), axis=0) * 100
    order = [m for m in ["Truck", "Rail", "Pipeline", "Multiple modes and mail", "Water", "Air", "Other and unknown",
                         "No domestic mode"] if m in sh.columns]
    fig = go.Figure()
    for i, m in enumerate(order):
        fig.add_bar(y=sh.index[::-1], x=sh[m][::-1], name=m, orientation="h",
                    marker=dict(color=lib.PALETTE[i % len(lib.PALETTE)], line=dict(width=0),
                                pattern=dict(shape=["", "/", ".", "x", "-", "|", "+", "\\"][i % 8])),
                    hovertemplate=m + ": %{x:.1f}%<extra></extra>")
    fig.update_layout(barmode="stack")
    lib.layout(fig, 340).update_xaxes(title="% of " + ("tons" if col == "tons_k" else "value"), range=[0, 100])
    lib.show(fig, "fr_modes", title=f"Share by mode of transport, {y}")
    lib.data_table((w / div).round(2).reset_index().rename(columns={"group": "Direction"}),
                   f"By mode, {unit}, {y} (table)", key="fr_modes_t")
    st.caption("Mode is the US part of the trip. Trucks carry most short trips and most value; rail and pipelines "
               "carry most of the weight leaving the state (grain, crude oil, coal products and fuels).")


def partners(p, y):
    st.subheader("Where it goes and where it comes from")
    c = st.columns([2, 1])
    grp = c[0].selectbox("Direction", [g for g in GROUPS if g != "Within North Dakota"], key="fr_partner_dir")
    with c[1]:
        col, div, unit, fmt = measure_pick("fr_m_partner")
    cur = p[(p.year == y) & p.flow.isin(GROUPS[grp])]
    v = cur.groupby("partner")[col].sum().sort_values(ascending=False) / div
    top = v.head(15)[::-1]
    fig = go.Figure(go.Bar(y=top.index, x=top.values, orientation="h", marker=dict(color=lib.SECOND, cornerradius=3),
                           hovertemplate="%{y}: %{x:" + fmt + "} " + unit + "<extra></extra>"))
    lib.layout(fig, 440, legend=False).update_xaxes(title=unit)
    lib.show(fig, "fr_partners", title=f"Top 15 partners, {grp.lower()}, {y}")
    t = cur.groupby(["flow", "partner"])[["tons_k", "current_value_m"]].sum().reset_index()
    lib.data_table(t.sort_values("tons_k", ascending=False).rename(columns={
        "flow": "Flow", "partner": "Partner", "tons_k": "Thousand tons", "current_value_m": "Value ($ millions)"}).round(1),
        f"All partners, {grp.lower()}, {y} (table)", key="fr_partners_t")
    st.caption("Partners are US states for trade between states, and world regions for North Dakota's own imports and "
               "exports. For other states' trade crossing the border, the partner is the US state the goods come from "
               "or go to.")


def balance(f, y):
    st.subheader("Supply chain links: what North Dakota ships out and what it brings in")
    cur = f[f.year == y]
    out = cur[cur.flow.isin(OUTBOUND)].groupby("commodity").tons_k.sum()
    inn = cur[cur.flow.isin(INBOUND)].groupby("commodity").tons_k.sum()
    b = pd.DataFrame({"out": out, "in": inn}).fillna(0) / 1e3
    b["net"] = b.out - b["in"]
    b = b[(b.out + b["in"]) > 0.05].sort_values("net")
    show = pd.concat([b.head(10), b.tail(10)]).drop_duplicates()
    fig = go.Figure(go.Bar(y=show.index, x=show.net, orientation="h",
                           marker=dict(color=[lib.NEG if x < 0 else lib.ACCENT for x in show.net], cornerradius=3),
                           customdata=show[["out", "in"]].values,
                           hovertemplate="%{y}: net %{x:+,.2f} million tons (out %{customdata[0]:,.2f}, in "
                                         "%{customdata[1]:,.2f})<extra></extra>"))
    fig.add_vline(x=0, line_color="gray")
    lib.layout(fig, 520, legend=False).update_xaxes(title="Leaving minus arriving, million tons")
    lib.show(fig, "fr_balance", title=f"Net shipments by goods, {y}: the 10 largest each way")
    st.caption("Green: North Dakota sends out more than it receives (it supplies other places). Orange: it brings in "
               "more than it sends (it relies on suppliers elsewhere, for example for fuels, building materials and "
               "manufactured goods). Freight within the state and other states' trade crossing the border are left out.")
    lib.data_table(b.sort_values("net", ascending=False).rename(columns={
        "out": "Leaving (million tons)", "in": "Arriving (million tons)", "net": "Net (million tons)"}).round(3)
        .reset_index().rename(columns={"commodity": "Goods (SCTG)"}), f"Net shipments by goods, {y} (table)",
        key="fr_balance_t")


def outlook(f, s, y):
    st.subheader("Trend and FAF forecast to 2050")
    cur = f.copy()
    cur["group"] = cur.flow.map(group_of)
    t = cur[cur.group != "Crossing ND's border (other states' trade)"].groupby(["group", "year"]).tons_k.sum() / 1e3
    fig = go.Figure()
    for i, g in enumerate(["Leaving North Dakota", "Arriving in North Dakota", "Within North Dakota"]):
        d = t.loc[g]
        obs, proj = d[d.index <= y], d[d.index >= y]
        clr = lib.PALETTE[i]
        fig.add_trace(go.Scatter(x=obs.index, y=obs.values, name=g, mode="lines+markers",
                                 line=dict(color=clr, dash=lib.DASHES[i]),
                                 hovertemplate=g + ", %{x}: %{y:,.1f} million tons<extra></extra>"))
        fig.add_trace(go.Scatter(x=proj.index, y=proj.values, name=g + " (FAF forecast)", mode="lines+markers",
                                 line=dict(color=clr, dash="dot", width=1.5), marker=dict(symbol="circle-open"),
                                 hovertemplate=g + ", %{x} forecast: %{y:,.1f} million tons<extra></extra>"))
    fig.add_vrect(x0=y + .5, x1=2050.5, fillcolor="gray", opacity=.08, line_width=0, annotation_text="FAF forecast",
                  annotation_position="top left")
    lib.layout(fig, 400, ytitle="Million tons")
    lib.show(fig, "fr_trend", title="Freight tons by direction, 2017-2050")
    st.caption("2017-2024 are FAF estimates for each year; 2030-2050 are FAF's baseline forecasts, published by the "
               "Federal Highway Administration (not an IPBA forecast). Forecasts assume past relationships hold; FAF "
               "also publishes high and low scenarios, not shown here.")
    lib.data_table(t.unstack(0).round(2).reset_index(), "Tons by direction and year (table)", key="fr_trend_t")

    pop = lib.table("population_annual.csv").set_index(["geo", "year"]).population
    ss = s[(s.year == y) & s.geo.isin(list(PEER_NAMES))].copy()
    idx = list(zip(ss.geo, ss.year))
    ss["per_resident"] = ss.tons_start_k * 1e3 / pd.Series(pop.reindex(idx).values, index=ss.index)
    ss["name"] = ss.geo.map(PEER_NAMES)
    ss = ss.sort_values("per_resident")
    fig = go.Figure(go.Bar(y=ss.name, x=ss.per_resident, orientation="h",
                           marker=dict(color=[lib.ACCENT if g == "ND" else lib.UND_GRAY for g in ss.geo], cornerradius=3),
                           hovertemplate="%{y}: %{x:,.0f} tons per resident<extra></extra>"))
    lib.layout(fig, 280, legend=False).update_xaxes(title="Tons per resident")
    lib.show(fig, "fr_peers", title=f"Freight starting in each state per resident, {y}")
    lib.data_table(ss[["name", "tons_start_k", "tons_end_k", "per_resident"]].rename(columns={
        "name": "Place", "tons_start_k": "Starting (thousand tons)", "tons_end_k": "Ending (thousand tons)",
        "per_resident": "Starting, tons per resident"}).round(1), f"Freight by state, {y} (table)", key="fr_peers_t")


def crude_note(f, y):
    e = lib.table("energy_monthly.csv", parse_dates=["month"])
    e = e[e.month.dt.year == y].nd_crude_kbd
    if len(e) < 12:
        return
    eia = e.mean() * 365 * SHORT_TONS_PER_BARREL / 1e3                      # million short tons
    cur = f[(f.year == y) & (f.commodity == "Crude petroleum")]
    faf = cur[cur.flow.isin(OUTBOUND + WITHIN)].tons_k.sum() / 1e3
    with st.expander("How reliable are the crude oil figures?"):
        st.markdown(f"FAF estimates **{faf:,.0f} million tons** of crude oil leaving or moving within North Dakota in "
                    f"{y}. North Dakota's production that year, from EIA, was about **{e.mean():,.0f} thousand barrels a "
                    f"day**, roughly **{eia:,.0f} million tons** (at {SHORT_TONS_PER_BARREL} short tons a barrel). FAF "
                    "is a model built mostly from the Commodity Flow Survey, which does not survey crude oil "
                    "producers, so FAF fills crude and pipeline flows from other data. Its crude tonnage for North "
                    f"Dakota is about {faf / eia:.1f} times production. Read crude oil tons here as a broad estimate; "
                    "for production use the EIA series on Current realities.")


def page():
    lib.header("Freight and supply chain", "What goods move out of, into, within and through North Dakota, by what "
               "mode and to or from where, and how freight is expected to grow to 2050.", "estimate",
               note="Freight Analysis Framework (FHWA and BTS), a modeled estimate. Net shipments and per-resident "
                    "figures: IPBA calculations.")
    if not ready():
        return
    f = lib.table("freight_nd.csv")
    p = lib.table("freight_partners.csv")
    s = lib.table("freight_states.csv")
    y = int(f[~f.projected.astype(bool)].year.max())
    headline(f, y)
    flows_chart(f, y)
    st.divider()
    commodities(f, y)
    st.divider()
    modes(f, y)
    st.divider()
    partners(p, y)
    st.divider()
    balance(f, y)
    crude_note(f, y)
    st.divider()
    outlook(f, s, y)
    lib.method_panel([
        "Source: Freight Analysis Framework version 5.7.1 (FAF5), state database, from the Federal Highway "
        "Administration and the Bureau of Transportation Statistics with Oak Ridge National Laboratory. FAF combines "
        "the 2017 Commodity Flow Survey with other data to estimate tons, value and ton-miles by origin and "
        "destination state, goods (SCTG 2-digit), mode and trade type, then updates the estimates each year to 2024 "
        "and forecasts them to 2050. Figures are modeled estimates, not counts.",
        "Directions: freight within the state, to and from other states, and North Dakota's own exports and imports. "
        "For exports, FAF records the state where goods start; for imports, the state where they end up. Other states' "
        "trade that enters or leaves the US at North Dakota's border is shown separately and not counted as the "
        "state's freight.",
        "Tons are short tons. Value is in current dollars for 2018-2024 (FAF current value) and 2017 dollars for 2017 "
        "and the forecasts. Mode is the US part of the trip.",
        "Net shipments: tons leaving for other states and abroad minus tons arriving from other states and abroad, "
        "by goods. Per resident: tons starting in the state (within, to other states and exports) divided by "
        "Census population."])
    lib.source_line("faf", "eia", "popest")


if __name__ == "__main__":
    page()
