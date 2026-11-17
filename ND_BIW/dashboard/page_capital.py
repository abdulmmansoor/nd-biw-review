"""Capital and support: SBA-backed lending to North Dakota small businesses, compared with neighbors, by industry and
county. Aggregates only: groups with fewer than 3 loans show no dollar amounts."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import COUNTIES, OUT, REGIONS

PROGRAMS = {"7A": "7(a) loans", "504": "504 loans"}


def ready():
    if not all((OUT / f).exists() for f in ("sba_state.csv", "sba_county.csv", "sba_industry.csv")):
        st.info("The SBA loan tables have not been built yet. Run `py -3.15 src/run_all.py`.")
        return False
    return True


def statewide():
    s = lib.table("sba_state.csv")
    s["program"] = s.program.astype(str).str.strip().str.upper()
    pop = lib.table("population_annual.csv").set_index(["geo", "year"]).population
    tot = s.groupby(["geo", "fy"])[["loans", "gross_m", "jobs", "startups"]].sum().reset_index()
    tot["pop"] = [pop.get((g, min(int(y), int(pop.index.get_level_values(1).max()))), float("nan"))
                  for g, y in zip(tot.geo, tot.fy)]
    tot["per_100k"] = tot.loans / tot["pop"] * 1e5
    tot["dollars_pc"] = tot.gross_m * 1e6 / tot["pop"]
    last = int(tot.fy.max())
    nd = tot[tot.geo == "ND"].set_index("fy")
    us = tot[tot.geo == "US"].set_index("fy")
    st.subheader(f"SBA-backed loans, fiscal year {last}")
    k = st.columns(4)
    k[0].metric("Loans approved, North Dakota", f"{nd.loc[last, 'loans']:,.0f}",
                f"{(nd.loc[last, 'loans'] / nd.loc[last - 1, 'loans'] - 1) * 100:+.0f}% vs FY{last - 1}",
                delta_color="off", delta_arrow="off")
    k[1].metric("Amount approved", lib.money(nd.loc[last, "gross_m"] * 1e6),
                f"{lib.money(nd.loc[last, 'gross_m'] * 1e6 / nd.loc[last, 'loans'])} on average", delta_color="off",
                delta_arrow="off")
    k[2].metric("Loans per 100,000 residents", f"{nd.loc[last, 'per_100k']:.0f}", f"US {us.loc[last, 'per_100k']:.0f}",
                delta_color="off", delta_arrow="off")
    k[3].metric("To startups and businesses 2 years old or less", f"{nd.loc[last, 'startups'] / nd.loc[last, 'loans'] * 100:.0f}%",
                f"US {us.loc[last, 'startups'] / us.loc[last, 'loans'] * 100:.0f}%", delta_color="off", delta_arrow="off")
    cols = st.columns(2)
    with cols[0]:
        sel = tot[tot.geo.isin(lib.pick_places("sba_places", default=("ND", "SD", "MN", "US")))]
        fig = lib.geo_lines(sel, "fy", "per_100k", ytitle="Loans per 100,000 residents", fmt=".0f", h=340)
        lib.show(fig, "sba_pc", title="SBA loans per 100,000 residents, by federal fiscal year")
    with cols[1]:
        p = s[s.geo == "ND"].pivot_table(index="fy", columns="program", values="gross_m", aggfunc="sum").fillna(0)
        fig = go.Figure()
        for i, (code, name) in enumerate(PROGRAMS.items()):
            if code in p:
                fig.add_bar(x=p.index, y=p[code], name=name, marker=dict(color=[lib.ACCENT, lib.SECOND][i], line=dict(width=0)),
                            hovertemplate="FY%{x}: $%{y:,.0f}M")
        fig.update_layout(barmode="stack")
        lib.layout(fig, 340, "$ millions").update_xaxes(dtick=2)
        lib.show(fig, "sba_amt", title="North Dakota SBA loan dollars by program")
    t = tot[tot.geo == "ND"][["fy", "loans", "gross_m", "jobs", "startups", "per_100k"]].rename(columns={
        "fy": "Fiscal year", "loans": "Loans", "gross_m": "Amount ($M)", "jobs": "Jobs reported", "startups": "To startups",
        "per_100k": "Per 100,000 residents"})
    lib.data_table(t.round(1), "North Dakota by fiscal year (table)", key="sba_nd")
    old = s[(s.fy <= last - 7) & (s.program == "7A")].groupby("geo")[["gross_m", "chargeoff_m", "loans", "chargeoff_loans"]].sum()
    if "ND" in old.index and "US" in old.index:
        y0, y1 = int(s.fy.min()), last - 7
        st.caption(f"Repayment record: of 7(a) loans approved FY{y0}-FY{y1} (mostly past their riskiest years), "
                   f"{old.loc['ND', 'chargeoff_loans'] / old.loc['ND', 'loans'] * 100:.1f}% in North Dakota were charged "
                   f"off, against {old.loc['US', 'chargeoff_loans'] / old.loc['US', 'loans'] * 100:.1f}% nationally.")


def by_industry():
    i = lib.table("sba_industry.csv")
    last = int(i.fy.max())
    span = range(last - 4, last + 1)
    st.subheader(f"By industry, FY{span[0]}-FY{last}")
    g = i[i.fy.isin(span)].groupby("sector").agg(loans=("loans", "sum"), gross_m=("gross_m", "sum"),
                                                withheld=("withheld", "any")).sort_values("loans")
    fig = go.Figure(go.Bar(y=g.index, x=g.loans, orientation="h", marker=dict(color=lib.ACCENT, line=dict(width=0)),
                           customdata=g.gross_m, hovertemplate="%{y}: %{x:,} loans ($%{customdata:,.0f}M)<extra></extra>"))
    lib.layout(fig, 520, legend=False).update_xaxes(title="Loans approved")
    lib.show(fig, "sba_ind", title=f"North Dakota SBA loans by industry, FY{span[0]}-FY{last}")
    lib.data_table(g.sort_values("loans", ascending=False).reset_index().rename(columns={
        "sector": "Industry", "loans": "Loans", "gross_m": "Amount ($M, years with 3+ loans)", "withheld": "Some years withheld"}
    ).round(1), "Industries (table)", key="sba_ind_t")


def by_county():
    c = lib.table("sba_county.csv")
    biz = lib.table("county_business.csv", dtype={"sector": str})
    b = biz[biz.sector == "total"].set_index("county")
    businesses = b.employer_estabs.fillna(0) + b.nonemployers.fillna(0)
    period = c.period.iloc[0]
    st.subheader(f"By county and region, {period.replace('-', ' to ')}")
    level = st.radio("Show", ["Counties", "Planning regions"], horizontal=True, key="sba_level")
    lvl = "county" if level == "Counties" else "region"
    a = c[(c.level == lvl) & (c.program == "All")].copy()
    if lvl == "county":
        a["businesses"] = a.place.map(businesses)
        allc = pd.DataFrame({"place": sorted(COUNTIES.values())})
        a = allc.merge(a, on="place", how="left").fillna({"loans": 0})
    else:
        a["businesses"] = a.place.map({r: businesses.reindex(cs).sum() for r, cs in REGIONS.items()})
    a["per_1k"] = a.loans / a.businesses * 1000
    if lvl == "county":
        import page_market
        acs = lib.table("acs_places.csv")
        fips = acs[acs.level == "county"].set_index("county").code.astype(str)
        a["fips"] = a.place.map(fips)
        fig = go.Figure(go.Choropleth(geojson=page_market.geojson(), locations=a.fips, z=a.per_1k, featureidkey="id",
                                      colorscale=lib.SEQ, marker_line_color=lib.PANEL, marker_line_width=0.6,
                                      text=a.place, customdata=a.loans,
                                      hovertemplate="%{text}: %{z:.1f} per 1,000 businesses (%{customdata:,.0f} loans)"
                                                    "<extra></extra>",
                                      colorbar=dict(title=None, thickness=12, tickfont=dict(color=lib.MUTED))))
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(height=470, margin=dict(l=10, r=10, t=50, b=10), paper_bgcolor=lib.PANEL,
                          geo=dict(bgcolor=lib.PANEL), font=dict(color=lib.INK), showlegend=False)
        lib.show(fig, "sba_map", title="SBA loans per 1,000 businesses (employer and self-employed), 5 fiscal years")
    t = a.sort_values("loans", ascending=False)[["place", "loans", "gross_m", "per_1k", "startups"]]
    t = t.rename(columns={"place": "County" if lvl == "county" else "Planning region", "loans": "Loans",
                          "gross_m": "Amount ($M)", "per_1k": "Loans per 1,000 businesses", "startups": "To startups"})
    lib.data_table(t.round(1), "Loans by place (table)", key=f"sba_{lvl}")
    st.caption("Places with fewer than 3 loans show the number of loans but no amount, so no single business's loan "
               "can be read from the table. Counties with no SBA loans in the period show 0.")


def page():
    lib.header("Capital and support", "How much SBA-backed credit reaches North Dakota small businesses, how that "
               "compares with neighboring states, and which industries and places use it.", "official", "estimate",
               note="U.S. Small Business Administration. Per-resident and per-business rates: IPBA calculations.")
    if not ready():
        return
    statewide()
    st.divider()
    by_industry()
    st.divider()
    by_county()
    lib.method_panel([
        "SBA 7(a) loans (general-purpose loans made by banks with an SBA guarantee) and 504 loans (long-term financing "
        "for real estate and equipment through Certified Development Companies), from SBA's public loan data, counted "
        "by the project's state and county and by federal fiscal year (October to September). Cancelled approvals "
        "are left out. Amounts are approved amounts, not disbursements.",
        "Per resident uses Census population estimates; per business uses County Business Patterns employer "
        "establishments plus nonemployer businesses.",
        "Startups: borrowers reported as starting a business or 2 years old or less. Charge-offs: loans SBA reports as "
        "charged off; recent loans have had less time to fail, so the comparison uses older approvals.",
        "Only aggregates are shown; groups with fewer than 3 loans show no dollar amounts. SBA-backed loans are a "
        "small part of small business credit, and state programs such as those of the Bank of North Dakota are not "
        "included because loan-level data are not public. Nothing here rates or endorses any lender or borrower."])
    lib.source_line("sba", "popest", "cbp", "nes")


if __name__ == "__main__":
    page()
