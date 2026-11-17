"""Case studies: short, reproducible stories built from the dashboard's own tables. Numbers update with each data run."""
import re
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import lib
from lib import OUT
from case_oil import CORE, CORE_SHARE, REST, lag_correlation

def busts(e):
    """The two oil busts, dated from the data: WTI's 2014 peak to the 2016 production low, and the 2019-20 production
    peak to the 2020 low."""
    e = e.set_index("month")
    a = e.loc["2014-01":"2014-12", "wti_usd"].idxmax()
    b = e.loc["2016-01":"2017-12", "nd_crude_kbd"].idxmin()
    c = e.loc["2019-01":"2020-03", "nd_crude_kbd"].idxmax()
    d = e.loc["2020-04":"2020-12", "nd_crude_kbd"].idxmin()
    return [(a, b, "2014-16 price collapse"), (c, d, "2020 pandemic")]


def shade(fig, bands, quarterly=False):
    for a, b, name in bands:
        fig.add_vrect(x0=a, x1=b, fillcolor="gray", opacity=.12, line_width=0, annotation_text=name,
                      annotation_position="top left", annotation_font_size=11)


def move(x):
    """'fell **40%**' or 'rose **3%**'."""
    return f"{'fell' if x < 0 else 'rose'} **{abs(x):.0f}%**"


def change(x):
    """'a **3%** drop' or 'a **3%** rise'."""
    return f"a **{abs(x):.0f}%** {'drop' if x < 0 else 'rise'}"


def quarters(n):
    n = int(round(n))
    return f"{n} quarter" + ("" if n == 1 else "s")


def oil_case():
    v = lib.table("case_oil_findings.csv").set_index("key")
    val, lab = v.value, v.label
    q = lib.table("case_oil_quarterly.csv", parse_dates=["quarter"])
    a = lib.table("case_oil_annual.csv")
    s = lib.table("case_oil_sales.csv", parse_dates=["quarter"])
    c = lib.table("case_oil_counties.csv")
    e = lib.table("energy_monthly.csv", parse_dates=["month"])
    core = c[c.core].county.tolist()
    bands = busts(e)
    year = int(c.year.iloc[0])

    st.subheader("The oil cycle and North Dakota's core oil counties")
    st.markdown(f"**Question:** how much do oil price swings move business activity in the oil patch compared with the "
                f"rest of the state, and how fast? **Core oil counties** here are the {len(core)} counties where "
                f"mining, oil and gas made up at least {CORE_SHARE:.0%} of private jobs in {year}: "
                f"**{', '.join(core)}**.")
    with st.container(border=True):
        st.markdown("**What the data show**")
        st.markdown(
            f"- **Booms and busts hit the oil counties far harder.** From the {lab['jobs_core_bust1'].split('from the ')[1]}, "
            f"private jobs {move(val['jobs_core_bust1'])} in the core oil counties, compared with "
            f"{change(val['jobs_rest_bust1'])} in the rest of the state. In the 2020 bust they "
            f"{move(val['jobs_core_bust2'])}, compared with {change(val['jobs_rest_bust2'])}.\n"
            f"- **Jobs follow prices with a lag.** Year-over-year job change in the core counties lines up best with "
            f"the oil price change about **{quarters(val['lag_core'])} earlier** (correlation {val['lag_r_core']:.2f}); "
            f"in the rest of the state, about {quarters(val['lag_rest'])} earlier and more weakly "
            f"({val['lag_r_rest']:.2f}). Timing, not proof of cause.\n"
            f"- **The boom brought a wave of new businesses.** Establishments in the core counties went from "
            f"{val['estabs_core_2007']:,.0f} in 2007 to {val['estabs_core_peak']:,.0f} at the peak; the opening rate "
            f"reached **{val['entry_core_peak']:.0f}%** in {lab['entry_core_peak'][-4:]}, against "
            f"{val['entry_rest_same']:.0f}% elsewhere. Unlike jobs, the count of establishments held up "
            f"({val['estabs_core_latest']:,.0f} in {lab['estabs_core_latest'][-4:]}).\n"
            f"- **Spending swings even more.** Taxable sales in the core counties {move(val['sales_core_2020'])} "
            f"by the {lab['sales_core_2020'].split('sales, ')[1].replace(' compared with 2019', '')} compared with 2019 "
            f"(rest of ND {val['sales_rest_2020']:+.0f}%), and are {val['sales_core_latest']:+.0f}% from 2019 now "
            f"against {val['sales_rest_latest']:+.0f}% elsewhere (current dollars).\n"
            f"- **Production recovered; jobs did not.** Oil output reached {val['prod_peak_2019']:,.0f} thousand barrels "
            f"a day in 2019, above the 2014 peak of {val['prod_peak_2015']:,.0f}, and was {val['prod_latest']:,.0f} in "
            f"{lab['prod_latest'].split(', ')[1]}; yet private jobs in the core counties are "
            f"**{abs(val['jobs_core_vs_2014peak']):.0f}% below** their 2014-15 level. The oil patch now produces about "
            f"as much with far fewer jobs. Private jobs in the rest of the state are "
            f"{abs(val['jobs_rest_vs_2014peak']):.1f}% {'below' if val['jobs_rest_vs_2014peak'] < 0 else 'above'} "
            f"their level then.")

    st.markdown("##### 1. The cycle: oil production and price")
    m = e[e.month >= "2005-01-01"]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=m.month, y=m.nd_crude_kbd, name="ND production (thousand barrels a day)",
                             line=dict(color=lib.ACCENT), hovertemplate="%{x|%b %Y}: %{y:,.0f} thousand b/d<extra></extra>"))
    fig.add_trace(go.Scatter(x=m.month, y=m.wti_usd, name="WTI price ($ a barrel, right axis)", yaxis="y2",
                             line=dict(color=lib.SECOND, dash="dash"), hovertemplate="%{x|%b %Y}: $%{y:.0f}<extra></extra>"))
    shade(fig, bands)
    lib.layout(fig, 380, ytitle="Thousand barrels a day")
    fig.update_layout(yaxis2=dict(overlaying="y", side="right", title="$ a barrel", showgrid=False))
    lib.show(fig, "case_oil_cycle", title="North Dakota oil production and the WTI price, monthly")

    st.markdown("##### 2. Jobs: the oil patch and the rest of the state")
    fig = go.Figure()
    for i, g in enumerate([CORE, REST]):
        d = q[q.group == g].dropna(subset=["index"])
        fig.add_trace(go.Scatter(x=d.quarter, y=d["index"], name=g, mode="lines",
                                 line=dict(color=[lib.ACCENT, lib.UND_GRAY][i], dash=lib.DASHES[i], width=3),
                                 hovertemplate=g + ", year to %{x|%Y Q%q}: %{y:.1f}<extra></extra>"))
    shade(fig, bands)
    fig.add_hline(y=100, line_dash="dot", line_color="gray")
    lib.layout(fig, 360, ytitle=f"Index, {q.quarter.dt.year.min()} = 100")
    lib.show(fig, "case_oil_jobs", title="Private jobs, 4-quarter average (index)")
    t = q.pivot(index="quarter", columns="group", values="private_jobs").round(0)
    t.index = t.index.to_period("Q").astype(str)
    lib.data_table(t.reset_index(), "Private jobs by quarter (table)", key="case_oil_jobs_t")

    st.markdown("##### 3. Timing: how many quarters jobs trail the oil price")
    fig = go.Figure()
    for i, g in enumerate([CORE, REST]):
        _, _, r = lag_correlation(q, g)
        fig.add_bar(x=list(r), y=list(r.values()), name=g,
                    marker=dict(color=[lib.ACCENT, lib.UND_GRAY][i], line=dict(width=0),
                                pattern=dict(shape=["", "/"][i])),
                    hovertemplate=g + ": price %{x} quarters earlier, r = %{y:.2f}<extra></extra>")
    lib.layout(fig, 320, ytitle="Correlation (r)").update_xaxes(title="Oil price change this many quarters earlier",
                                                                 dtick=1)
    lib.show(fig, "case_oil_lag", title="Correlation of year-over-year job change with earlier oil price change")
    st.caption("Each bar compares the year-over-year change in private jobs with the year-over-year change in the WTI "
               "price some quarters earlier. A higher bar means the two move together more closely at that delay. "
               "Correlation shows timing; it does not prove that prices cause the job changes.")

    st.markdown("##### 4. Business openings and closings")
    cols = st.columns(2)
    with cols[0]:
        fig = go.Figure()
        for i, g in enumerate([CORE, REST]):
            d = a[(a.group == g) & a.entry_rate.notna()]
            fig.add_trace(go.Scatter(x=d.year, y=d.entry_rate, name=g, line=dict(color=[lib.ACCENT, lib.UND_GRAY][i],
                                     dash=lib.DASHES[i]), hovertemplate=g + ", %{x}: %{y:.1f}%<extra></extra>"))
        lib.layout(fig, 320, ytitle="% of establishments")
        lib.show(fig, "case_oil_entry", title="Establishment opening rate")
    with cols[1]:
        fig = go.Figure()
        for i, g in enumerate([CORE, REST]):
            d = a[(a.group == g) & a.exit_rate.notna()]
            fig.add_trace(go.Scatter(x=d.year, y=d.exit_rate, name=g, line=dict(color=[lib.ACCENT, lib.UND_GRAY][i],
                                     dash=lib.DASHES[i]), hovertemplate=g + ", %{x}: %{y:.1f}%<extra></extra>"))
        lib.layout(fig, 320, ytitle="% of establishments")
        lib.show(fig, "case_oil_exit", title="Establishment closing rate")
    lib.data_table(a.pivot_table(index="year", columns="group", values=["estabs", "entry_rate", "exit_rate"]).round(1)
                   .pipe(lambda w: w.set_axis([f"{g}: {m}" for m, g in w.columns], axis=1)).reset_index(),
                   "Establishments, opening and closing rates by year (table)", key="case_oil_bds_t")

    st.markdown("##### 5. Spending: taxable sales")
    ss = s.dropna(subset=["four_quarter"]).copy()
    base = ss[ss.quarter == "2019-10-01"].set_index("group").four_quarter
    ss["index"] = ss.four_quarter / ss.group.map(base) * 100
    fig = go.Figure()
    for i, g in enumerate([CORE, REST]):
        d = ss[ss.group == g]
        fig.add_trace(go.Scatter(x=d.quarter, y=d["index"], name=g, line=dict(color=[lib.ACCENT, lib.UND_GRAY][i],
                                 dash=lib.DASHES[i], width=3), hovertemplate=g + ", year to %{x|%Y Q%q}: %{y:.1f}<extra></extra>"))
    fig.add_hline(y=100, line_dash="dot", line_color="gray")
    shade(fig, bands[1:])
    lib.layout(fig, 340, ytitle="Index, 2019 = 100")
    lib.show(fig, "case_oil_sales", title="Taxable sales and purchases, 4-quarter total (index, 2019 = 100)")
    st.caption("Current dollars, not adjusted for inflation; taxable sales include business purchases, which swing with "
               "drilling.")

    with st.expander("Which counties are core oil counties?"):
        cc = c[["county", "private_jobs", "mining_jobs", "mining_share", "mining_published", "core"]].copy()
        cc["mining_share"] *= 100
        st.dataframe(cc.rename(columns={"county": "County", "private_jobs": "Private jobs",
                                        "mining_jobs": "Mining, oil and gas jobs", "mining_share": "Share (%)",
                                        "mining_published": "Published by BLS", "core": "Core oil county"}),
                     hide_index=True, width="stretch",
                     column_config={"Share (%)": st.column_config.NumberColumn(format="%.1f")})
        st.caption(f"QCEW {year}, private employers. Some oil-producing counties (for example Divide, Burke and "
                   "Billings) cannot be classified because BLS withholds their mining figures; they are counted in the "
                   "rest of North Dakota, which slightly understates the contrast.")

    st.markdown("##### Do it yourself")
    st.markdown("- Oil price and production now: [Current realities](current-realities)\n"
                "- Any county's industries, pay and concentration: [Industry profiles](industry)\n"
                "- A county's people, income and peer counties: [Market finder](market)\n"
                "- Openings, closings and taxable sales by county or region: [Business pulse](pulse)")


def oil_method():
    lib.method_panel([
        f"Core oil counties: mining, oil and gas (NAICS 21) at least {CORE_SHARE:.0%} of private jobs in the latest "
        "QCEW year with the county's sector figure published. All other counties form the rest of North Dakota.",
        "Jobs: BLS QCEW private jobs by quarter, from 2014; the rest of the state is the state total less the core "
        "counties. Changes compare 4-quarter averages so seasonal swings cancel out.",
        "Bust periods are dated from the data: from WTI's 2014 peak to the 2016 low in ND production, and from the "
        "2019-20 production peak to the 2020 low.",
        "Timing: Pearson correlation between the year-over-year percent change in private jobs and in the WTI price "
        "0 to 8 quarters earlier.",
        "Openings and closings: Census Business Dynamics Statistics (establishment births and deaths divided by the "
        "average of this and last year's establishments); county figures carry Census noise for confidentiality.",
        "Taxable sales: ND Tax Commissioner by county, 4-quarter totals, current dollars."])
    lib.source_line("qcew", "bds", "eia", "taxable_sales")


def gap_word(d):
    """A pay gap relative to the state's general gap with the US, in percentage points."""
    if abs(d) < 3:
        return f"within {abs(d):.0f} points of it"
    return f"**{abs(d):.0f} points** {'above' if d > 0 else 'below'} it"


def pct_word(x, up="more", down="less"):
    """'**14%** more' or '**3%** less'."""
    return f"**{abs(x):.0f}%** {up if x >= 0 else down}"


# ------------------------------------------------------------------ value-added agriculture
def va_case():
    v = lib.table("case_va_findings.csv").set_index("key").value
    tr = lib.table("case_va_trend.csv")
    codes = lib.table("case_va_codes.csv", dtype={"naics": str})
    ex = lib.table("case_va_exports.csv")
    y, f0, ey = int(v["year"]), int(v["from_year"]), int(v["exports_year"])

    st.subheader("Value-added agriculture: processing North Dakota's crops at home")
    st.markdown("**Question:** how large is farm-product processing in North Dakota, is it growing, and how does it "
                "compare with the farm exports it could draw on? **Value-added agriculture** here follows ND Commerce's targeted-industry definition, coded by "
                "IPBA as food manufacturing, beverage manufacturing and fuel ethanol: industries that change a farm "
                "product's physical state.")
    with st.container(border=True):
        st.markdown("**What the data show**")
        st.markdown(lib.esc(
            f"- **Processing is a modest but growing employer.** Value-added agriculture had **{v['va_jobs']:,.0f}** "
            f"private jobs in {y}, {v['va_share']:.1f}% of the state's private jobs. Its jobs "
            f"{move(v['va_growth'])} from {f0} to {y}, while all private jobs "
            f"{'rose' if v['private_growth'] >= 0 else 'fell'} {abs(v['private_growth']):.1f}%.\n"
            f"- **North Dakota is a little more concentrated in processing than the nation** (location quotient "
            f"{v['va_lq']:.2f}). "
            + (f"Fuel ethanol stands out at **{v['ethanol_lq']:.1f} times** the US share, with "
               f"{v['ethanol_jobs']:,.0f} jobs paying ${v['ethanol_pay']:,.0f} on average; "
               if pd.notna(v.get("ethanol_jobs")) and pd.notna(v.get("ethanol_lq")) else
               "Fuel ethanol's figures are withheld by BLS this year; ")
            + f"food manufacturing, with {v['food_jobs']:,.0f} jobs, is close to the US share ({v['food_lq']:.2f}).\n"
            f"- **Most farm freight still leaves raw, and the processed share is not rising.** Of farm products "
            f"leaving the state for other states and abroad in {v['freight_year']:.0f}, about "
            f"**{v['freight_proc_share_tons']:.0f}%** of the tons ({v['freight_proc_share_value']:.0f}% of the value) "
            f"had been processed (feed and meal, meat, milled grain, other foods, fuel alcohol); the rest left as "
            f"grain, oilseeds and other raw farm products. In {v['freight_first_year']:.0f} the processed share was "
            f"{v['freight_proc_share_tons_first']:.0f}% of the tons: raw shipments grew while processed ones stayed "
            f"near {v['freight_proc_tons']:.1f} million tons (FAF estimates).\n"
            f"- **Pay is close to the state average.** Processing paid ${v['va_pay']:,.0f} on average in {y}, against "
            f"${v['private_pay']:,.0f} for all private jobs; since {int(tr.year.min())} its average pay rose "
            f"{v['va_pay_growth']:.0f}%, compared with {v['private_pay_growth']:.0f}% for all private jobs (current dollars).\n"
            f"- **Farm exports are mostly bulk crops.** North Dakota's farm exports were an estimated "
            f"**${v['exports_total'] / 1000:,.1f} billion** in {ey}; wheat, soybeans and corn alone made up "
            f"{v['exports_bulk_share']:.0f}%, and plant products {v['exports_plant_share']:.0f}%. Farm exports rose "
            f"{v['exports_10y']:.0f}% in ten years (current dollars)."))

    st.markdown("##### 1. Jobs in processing and in the whole private economy")
    fig = go.Figure()
    tc = tr[tr.year <= y]
    for i, (col, name) in enumerate((("va_index", "Value-added agriculture"), ("private_index", "All private jobs"))):
        fig.add_trace(go.Scatter(x=tc.year, y=tc[col], name=name, mode="lines+markers",
                                 line=dict(color=[lib.ACCENT, lib.UND_GRAY][i], dash=lib.DASHES[i], width=3),
                                 hovertemplate=name + ", %{x}: %{y:.1f}<extra></extra>"))
    fig.add_hline(y=100, line_dash="dot", line_color="gray")
    lib.layout(fig, 340, ytitle=f"Index, {int(tr.year.min())} = 100")
    lib.show(fig, "case_va_jobs", title="Private jobs (index)")
    if tr.year.max() > y:
        st.caption(f"The chart ends in {y}. {int(tr.year.max())} is BLS's first annual release, with "
                   f"{int(tr.va_codes_withheld.iloc[-1])} of the 3 codes withheld, so its jobs are a floor; it is in "
                   "the table only.")
    lib.data_table(tr[["year", "va_jobs", "va_avg_pay", "va_lq", "private_jobs", "private_avg_pay"]].round(2),
                   "Jobs, pay and concentration by year (table)", key="case_va_t")

    st.markdown("##### 2. The three processing industries")
    cc = codes[["naics", "title", "jobs", "avg_pay", "lq", "withheld"]]
    st.dataframe(cc.rename(columns={"naics": "NAICS", "title": "Industry", "jobs": "Jobs", "avg_pay": "Average pay ($)",
                                    "lq": "Location quotient", "withheld": "Withheld by BLS"}),
                 hide_index=True, width="stretch",
                 column_config={"Jobs": st.column_config.NumberColumn(format="localized"),
                                "Average pay ($)": st.column_config.NumberColumn(format="dollar")})

    st.markdown(f"##### 3. What North Dakota's farms export, {ey}")
    last = ex[(ex.year == ey) & ~ex.commodity.str.startswith("Total")].sort_values("value").tail(10)
    fig = go.Figure(go.Bar(x=last.value, y=last.commodity, orientation="h", marker=dict(color=lib.ACCENT, line=dict(width=0)),
                           hovertemplate="%{y}: $%{x:,.0f} million<extra></extra>"))
    lib.layout(fig, 360, legend=False).update_xaxes(title="$ million, current")
    lib.show(fig, "case_va_exports", title="Estimated farm exports by commodity, top ten")
    lib.data_table(ex[ex.year == ey][["commodity", "value"]].sort_values("value", ascending=False).round(1),
                   "Farm exports by commodity (table)", key="case_va_ex_t")

    fr = lib.table("case_va_freight.csv")
    st.markdown(f"##### 4. Farm products leaving the state: raw or processed, {int(fr.year.min())}-{int(fr.year.max())}")
    fig = go.Figure()
    for i, kind in enumerate(["Raw farm products", "Processed farm products"]):
        d = fr[fr.kind == kind]
        fig.add_bar(x=d.year, y=d.tons_k / 1000, name=kind,
                    marker=dict(color=[lib.UND_GRAY, lib.ACCENT][i], line=dict(width=0), pattern=dict(shape=["/", ""][i])),
                    hovertemplate=kind + ", %{x}: %{y:,.1f} million tons<extra></extra>")
    fig.update_layout(barmode="stack")
    lib.layout(fig, 340, ytitle="Million tons").update_xaxes(dtick=1)
    lib.show(fig, "case_va_freight", title="Farm products leaving North Dakota for other states and abroad (tons)")
    st.caption("Freight Analysis Framework (FHWA and BTS), modeled estimates. Raw: live animals, cereal grains and "
               "other farm products (oilseeds, beans, potatoes, etc.). Processed: animal feed (including oilseed meal "
               "and distillers' grains), meat, milled grain, other foodstuffs (including vegetable oils), and alcoholic "
               "beverages and fuel alcohol. A processed product weighs less than the crop it came from, so tons "
               "understate the crop processed; the trend is the more useful signal.")
    lib.data_table(fr.pivot_table(index="year", columns="kind", values=["tons_k", "value_m"])
                   .pipe(lambda w: w.set_axis([f"{k}: {'thousand tons' if m == 'tons_k' else '$ million (2017)'}"
                                               for m, k in w.columns], axis=1)).round(1).reset_index(),
                   "Farm products leaving ND by year (table)", key="case_va_freight_t")

    st.markdown("##### Do it yourself")
    st.markdown("- All six targeted industries, by code: [Industry profiles](industry)\n"
                "- Farm and goods exports: [Trade and exports](trade)\n"
                "- Freight of farm products leaving the state: [Freight and supply chain](freight)")
    lib.method_panel([
        "Value-added agriculture: food manufacturing (NAICS 311), beverage manufacturing (3121) and fuel ethanol "
        "(325193), IPBA's coding of ND Commerce's definition (USDA's change-in-physical-state test). Private jobs, BLS QCEW.",
        f"Headline year {y}: the latest year with job change computed; job change {f0}-{y} uses codes published in "
        "both years. The comparison is all ND private jobs in the same years.",
        "Location quotient: the group's share of ND private jobs divided by the same codes' share of US private jobs.",
        "Farm exports: USDA ERS state export estimates, current dollars. They estimate each state's share of US farm "
        "exports from its production; they are not customs records. They show what leaves the country, not how much "
        "of the state's farm output is processed in the state, which no public table measures.",
        "Freight: FAF 5.7.1 tons and value of farm products leaving ND for other states and abroad, by SCTG goods code: "
        "raw = SCTG 01-03; processed = SCTG 04-08. The processed share of farm freight is an indirect signal of in-state "
        "processing, not a measure of it: weights fall in processing, and FAF's yearly figures are modeled.",
        "Years differ: jobs are for the latest complete QCEW year, exports for the latest ERS year."])
    lib.source_line("qcew", "commerce_targets", "ers_trade", "faf")


# ------------------------------------------------------------------ advanced manufacturing and technology
def adv_case():
    v = lib.table("case_adv_findings.csv").set_index("key").value
    lab = lib.table("case_adv_findings.csv").set_index("key").label
    g = lib.table("case_adv_groups.csv")
    codes = lib.table("case_adv_codes.csv", dtype={"naics": str})
    pr = lib.table("case_adv_patents.csv")
    y = int(v["year"])
    top = lab["mfg_top_jobs"].split(": ", 1)[1]
    p0, p1 = int(v["patent_years_from"]), int(v["patent_years_to"])

    st.subheader("Advanced manufacturing and technology: North Dakota's innovation-intensive industries")
    st.markdown("**Question:** how large are North Dakota's innovation-intensive industries, what do they pay, and "
                "where does invention happen in the state? **Advanced manufacturing** and **technology-based business** "
                "are two of ND Commerce's targeted industries, coded by IPBA from Brookings' 50 advanced industries "
                "(high R&D per worker and a high share of STEM jobs).")
    with st.container(border=True):
        st.markdown("**What the data show**")
        st.markdown(lib.esc(
            f"- **Advanced manufacturing is concentrated in farm, construction and mining machinery.** It had at least "
            f"**{v['mfg_jobs']:,.0f}** jobs in {y} (location quotient {v['mfg_lq']:.2f}); {top.lower()} alone held "
            f"{v['mfg_top_share']:.0f}% of them, at **{v['mfg_top_lq']:.1f} times** the US share. BLS withheld "
            f"{v['mfg_withheld']:.0f} of the {v['mfg_codes']:.0f} codes, so these are floors.\n"
            f"- **Technology-based business is under-represented but pays well.** It had at least "
            f"**{v['tech_jobs']:,.0f}** jobs (location quotient {v['tech_lq']:.2f}: about half the US share), paying "
            f"${v['tech_pay']:,.0f} on average, {pct_word(v['tech_pay_vs_nd'], 'above', 'below')} the average private "
            f"job in North Dakota. Only {v['tech_above_1']:.0f} of its codes reaches the US share. Jobs changed "
            f"{v['tech_growth']:+.1f}% from {v['tech_from']:.0f} to {y}.\n"
            f"- **Pay is below the US, partly because of the industry mix and the state's lower pay overall.** Against "
            f"US pay for North Dakota's own mix of industries, advanced manufacturing pays "
            f"{pct_word(v['mfg_pay_vs_us_mix'], 'more', 'less')} and technology-based business "
            f"{pct_word(v['tech_pay_vs_us_mix'], 'more', 'less')}; all private jobs in North Dakota pay "
            f"{pct_word(v['private_pay_vs_us'], 'more', 'less')} than in the US. Measured against that general gap, "
            f"advanced manufacturing is {gap_word(v['mfg_pay_vs_us_mix'] - v['private_pay_vs_us'])} and "
            f"technology-based business {gap_word(v['tech_pay_vs_us_mix'] - v['private_pay_vs_us'])}. (On the US mix "
            f"of industries the gaps would read {v['mfg_pay_vs_us']:.0f}% and {v['tech_pay_vs_us']:.0f}%.)\n"
            f"- **Invention is concentrated in the Fargo region.** Of North Dakota's {v['patents_total']:,.0f} utility patents "
            f"in {p0}-{p1}, **{v['patents_fargo_share']:.0f}%** list a first inventor in the Fargo region, which has "
            f"{v['pop_fargo_share']:.0f}% of the state's residents, and "
            f"{v['patents_top3_share']:.0f}% in the Fargo, Bismarck and Grand Forks regions together. Per resident, "
            f"North Dakota had {v['patents_pc_nd']:.0f} patents per 100,000 people in {p1}, against "
            f"{v['patents_pc_us']:.0f} for the US."))

    st.markdown(f"##### 1. Pay, {y}")
    gy = g[g.year == y]
    fig = go.Figure()
    for i, (col, name) in enumerate((("avg_pay", "North Dakota"), ("us_avg_pay", "Same industries, US"),
                                     ("private_avg_pay", "All ND private jobs"))):
        fig.add_bar(x=gy.group, y=gy[col], name=name, marker=dict(color=[lib.ACCENT, lib.SECOND, lib.UND_GRAY][i],
                    line=dict(width=0), pattern=dict(shape=["", "/", "."][i])),
                    hovertemplate=name + ": $%{y:,.0f}<extra></extra>")
    lib.layout(fig, 340, ytitle="Average annual pay ($)")
    lib.show(fig, "case_adv_pay", title="Average annual pay")
    lib.data_table(gy[["group", "jobs", "avg_pay", "us_avg_pay", "private_avg_pay", "lq", "codes_withheld"]].round(2),
                   "Jobs, pay and concentration (table)", key="case_adv_t")

    st.markdown("##### 2. Which industries carry the groups")
    cc = codes[codes.jobs.fillna(0) > 0].sort_values(["group", "jobs"], ascending=[True, False])
    fig = go.Figure()
    for i, grp in enumerate(cc.group.unique()):
        d = cc[cc.group == grp].head(6).iloc[::-1]
        fig.add_bar(x=d.jobs, y=d.title, orientation="h", name=grp,
                    marker=dict(color=[lib.ACCENT, lib.SECOND][i], line=dict(width=0), pattern=dict(shape=["", "/"][i])),
                    customdata=d.lq, hovertemplate="%{y}: %{x:,.0f} jobs, LQ %{customdata:.2f}<extra></extra>")
    lib.layout(fig, 420).update_xaxes(title="Jobs")
    lib.show(fig, "case_adv_codes", title="Largest published industries in each group (jobs)")
    lib.data_table(codes[["group", "naics", "title", "jobs", "avg_pay", "lq", "withheld"]], "All codes (table)",
                   key="case_adv_codes_t")

    st.markdown(f"##### 3. Where inventors live: utility patents by planning region, {p0}-{p1}")
    w = pr[pr.year >= p0].groupby("region").patents.sum().sort_values()
    fig = go.Figure(go.Bar(x=w.values, y=w.index, orientation="h", marker=dict(color=lib.ACCENT, line=dict(width=0)),
                           hovertemplate="%{y}: %{x:,.0f} patents<extra></extra>"))
    lib.layout(fig, 340, legend=False).update_xaxes(title="Patents (first-named inventor)")
    lib.show(fig, "case_adv_patents", title="Utility patents by first-named inventor's planning region")
    lib.data_table(w.reset_index(), "Patents by region (table)", key="case_adv_pat_t")

    st.markdown("##### Do it yourself")
    st.markdown("- Every targeted industry, code by code: [Industry profiles](industry)\n"
                "- Patents, SBIR/STTR awards and university R&D over time: [Business and innovation indicators](indicators)\n"
                "- Startups: business applications, young firms and five-year survival of new firms: [Business pulse](pulse)\n"
                "- Graduates and occupations: [Workforce and talent](workforce)")
    lib.method_panel([
        "Advanced manufacturing and technology-based business: IPBA's coding of ND Commerce's definitions with "
        "Brookings' advanced industries (R&D of at least $450 per worker and a STEM share of at least 21%): the 35 "
        "manufacturing industries and the 12 service industries.",
        "Jobs are sums of the codes BLS publishes for ND (a floor); withheld codes are counted, never estimated. Pay is "
        "compared with all ND private jobs and with the same codes in the US; a group average also reflects the mix of "
        "industries in the group, which differs between ND and the US.",
        f"Headline year {y}: the latest year with job change computed. Technology-based business starts its job change "
        "in 2022 because several of its codes changed in NAICS 2022.",
        f"Patents: utility patents by grant year and first-named inventor's county (PatentsView), {p0}-{p1}; the "
        "latest grant year is left out because it is incomplete. Patents measure invention, not its commercial use. "
        "Inventors that PatentsView places in Mayville or Portland, or in Grand Forks without a state, are assigned to "
        "Grand Forks County; this moves patents between regions, not the state total."],
        refs=("muro2015", "griliches1990"))
    lib.source_line("qcew", "commerce_targets", "brookings_ai", "patents")


# ------------------------------------------------------------------ main street retail
def retail_case():
    from case_retail import HUB, HUBS, OTHER
    v = lib.table("case_retail_findings.csv").set_index("key").value
    lab = lib.table("case_retail_findings.csv").set_index("key").label
    c = lib.table("case_retail_counties.csv")
    s = lib.table("case_retail_sales.csv", parse_dates=["quarter"])
    when = re.search(r"year to \d{4} Q\d", lab["tax_hub_growth_real"]).group(0)

    st.subheader("Main street retail: the hub counties and the smaller counties")
    st.markdown(f"**Question:** do the regional hub counties draw shoppers from smaller counties, and how are main "
                f"street sales holding up? **Hub counties** are the counties of the eight planning regions' hub "
                f"cities: **{', '.join(HUBS)}**. All other counties are compared with them.")
    with st.container(border=True):
        st.markdown("**What the data show**")
        st.markdown(lib.esc(
            f"- **The hubs pull shoppers in.** With {v['pop_share_hub']:.0f}% of the state's residents, the hub "
            f"counties made {v['sales_share_hub']:.0f}% of its retail sales in 2022: a pull factor of "
            f"**{v['pf_hub']:.2f}** (sales {abs(v['pf_hub'] - 1) * 100:.0f}% above what their income would predict). "
            f"All {v['hub_above_1']:.0f} hubs are at or above 1.\n"
            f"- **Most smaller counties leak sales.** The other counties' combined pull factor is "
            f"**{v['pf_other']:.2f}**; {v['other_below_1']:.0f} of {v['other_n']:.0f} are below 1, and "
            f"{v['other_below_half']:.0f} are below 0.5, meaning local retail sales are less than half of what "
            f"local income would predict. Summed over the leaking counties, sales fell about ${v['other_leakage_m'] / 1000:,.1f} "
            f"billion short of expected.\n"
            f"- **Smaller counties still have more stores per person.** The other counties have "
            f"{v['stores_per_1000_other']:.1f} retail stores with employees per 1,000 residents (hubs "
            f"{v['stores_per_1000_hub']:.1f}) and {v['nonemp_per_1000_other']:.1f} retail businesses without "
            f"employees (hubs {v['nonemp_per_1000_hub']:.1f}).\n"
            f"- **After inflation, taxable sales are below 2019 in both groups; the smaller counties held up better "
            f"outside the oil patch.** Leaving out the {v['oil_counties_n']:.0f} core oil counties, where taxable "
            f"sales include business purchases that swing with drilling, taxable sales and purchases from 2019 to "
            f"the {when} {move(v['tax_hub_growth_real_nooil'])} in the hub counties and "
            f"{move(v['tax_other_growth_real_nooil'])} in the other counties after inflation (prices rose "
            f"{v['price_growth']:.0f}%; in current dollars {v['tax_hub_growth_nooil']:+.0f}% and "
            f"{v['tax_other_growth_nooil']:+.0f}%). With the oil counties in, the order flips: "
            f"{v['tax_hub_growth_real']:+.0f}% in the hubs against {v['tax_other_growth_real']:+.0f}% elsewhere. "
            f"Taxable sales cover more than store sales, so this is a signal, not a measure of main street retail."))

    st.markdown("##### 1. Retail pull factor by county, 2022")
    d = c.dropna(subset=["pull_factor"])
    fig = go.Figure()
    for i, grp in enumerate([HUB, OTHER]):
        e = d[d.group == grp]
        fig.add_trace(go.Scatter(x=e.population, y=e.pull_factor, mode="markers", name=grp, text=e.county,
                                 marker=dict(color=[lib.ACCENT, lib.UND_GRAY][i], size=[12, 9][i],
                                             symbol=["circle", "diamond"][i], line=dict(width=0)),
                                 hovertemplate="%{text}: %{x:,.0f} residents, pull factor %{y:.2f}<extra></extra>"))
    fig.add_hline(y=1, line_dash="dot", line_color="gray")
    lib.layout(fig, 400, ytitle="Pull factor (1 = sales match local income)")
    fig.update_xaxes(type="log", title="Residents (log scale)")
    fig.update_layout(hovermode="closest")
    lib.show(fig, "case_retail_pf", title="Retail sales against what local income predicts")
    st.caption(f"{v['estimated_n']:.0f} counties' sales are withheld by the Census Bureau and estimated from the state "
               "remainder; they are flagged in the table.")
    lib.data_table(c[["county", "group", "region", "population", "pull_factor", "estimated", "restaurant_pull_factor",
                      "retail_stores", "retail_nonemployers", "stores_per_1000"]].round(2),
                   "Pull factor, stores and residents by county (table)", key="case_retail_t")

    st.markdown("##### 2. Taxable sales and purchases, hubs and other counties")
    from case_retail import ALL, NO_OIL
    scope = st.radio("Counties", [NO_OIL, ALL], horizontal=True, key="case_retail_scope")
    ss = s[s.scope == scope].dropna(subset=["four_quarter_real"]).copy()
    base = ss[ss.quarter == "2019-10-01"].set_index("group").four_quarter_real
    ss["index"] = ss.four_quarter_real / ss.group.map(base) * 100
    fig = go.Figure()
    for i, grp in enumerate([HUB, OTHER]):
        e = ss[ss.group == grp]
        fig.add_trace(go.Scatter(x=e.quarter, y=e["index"], name=grp, line=dict(color=[lib.ACCENT, lib.UND_GRAY][i],
                                 dash=lib.DASHES[i], width=3),
                                 hovertemplate=grp + ", year to %{x|%Y Q%q}: %{y:.1f}<extra></extra>"))
    fig.add_hline(y=100, line_dash="dot", line_color="gray")
    lib.layout(fig, 340, ytitle="Index, 2019 = 100")
    lib.show(fig, "case_retail_sales", title="Taxable sales and purchases after inflation, 4-quarter total "
                                              "(index, 2019 = 100)")
    st.caption("Adjusted for inflation with the GDP price index (BEA), as on Business pulse, because about 40% of the "
               "base is business purchases. Taxable sales include business purchases, not only store sales.")
    lib.data_table(ss.pivot_table(index="quarter", columns="group", values=["four_quarter", "four_quarter_real"])
                   .pipe(lambda w: w.set_axis([f"{g}: {'current $' if m == 'four_quarter' else '2019 $'}"
                                               for m, g in w.columns], axis=1))
                   .round(0).reset_index().assign(quarter=lambda d: d.quarter.dt.to_period("Q").astype(str)),
                   "Taxable sales, 4-quarter totals, current and 2019 dollars (table)", key="case_retail_sales_t")

    st.markdown("##### Do it yourself")
    st.markdown("- Pull factors by store type, county and region: [Retail gap](retail-gap)\n"
                "- Taxable sales for any county or region: [Business pulse](pulse)\n"
                "- A county's people, income and peer counties: [Market finder](market)")
    lib.method_panel([
        "Hub counties: Williams (Williston), Ward (Minot), Ramsey (Devils Lake), Grand Forks, Cass (Fargo), Stutsman "
        "(Jamestown), Burleigh (Bismarck) and Stark (Dickinson), the hub cities of the eight planning regions.",
        "Pull factor: 2022 Economic Census retail sales divided by the state's sales times the county's share of ND "
        "household income (ACS 5-year). Groups use summed sales over summed expected sales. Withheld counties share "
        "the state remainder by income and are flagged.",
        "Stores: County Business Patterns 2023 (retail establishments with employees, NAICS 44-45) and Nonemployer "
        "Statistics 2024, per 1,000 residents (ACS 5-year population).",
        "Taxable sales: ND Tax Commissioner by county, 4-quarter totals from 2019, adjusted for inflation with the "
        "4-quarter average of BEA's GDP price index (current dollars in the table); out-of-state and "
        "statewide consolidated filers have no county and are left out. The main comparison leaves out the oil case's "
        "core oil counties (one of them, Williams, is a hub county), because their taxable sales include business "
        "purchases that swing with drilling; the county figures are not split by industry."],
        refs=("hustedde1984",))
    lib.source_line("econ_census", "acs", "cbp", "nes", "taxable_sales")


CASES = {"The oil cycle and North Dakota's core oil counties": "oil",
         "Value-added agriculture: processing crops at home": "va",
         "Advanced manufacturing and technology": "adv",
         "Main street retail: hub counties and smaller counties": "retail"}
NEED = {"oil": ["case_oil_findings.csv", "case_oil_quarterly.csv", "case_oil_annual.csv", "case_oil_sales.csv",
                "case_oil_counties.csv"],
        "va": ["case_va_findings.csv", "case_va_trend.csv", "case_va_codes.csv", "case_va_exports.csv",
               "case_va_freight.csv"],
        "adv": ["case_adv_findings.csv", "case_adv_groups.csv", "case_adv_codes.csv", "case_adv_patents.csv"],
        "retail": ["case_retail_findings.csv", "case_retail_counties.csv", "case_retail_sales.csv"]}


def page():
    lib.header("Case studies", "Short, worked examples that use the dashboard's public data to answer one question each. "
               "The numbers and text update with each data run.", "official", "estimate",
               note="BLS, Census Bureau, EIA, USDA, USPTO and ND Tax Commissioner; groupings, indexes and correlations: "
                    "IPBA calculations.")
    case = st.selectbox("Case study", list(CASES), key="case_pick")
    k = CASES[case]
    if not all((OUT / f).exists() for f in NEED[k]):
        st.info("This case study's tables have not been built yet. Run `py -3.15 src/run_all.py`.")
        return
    if k == "oil":
        oil_case()
        oil_method()
    else:
        {"va": va_case, "adv": adv_case, "retail": retail_case}[k]()


if __name__ == "__main__":
    page()
