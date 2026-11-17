"""Market brief: pick a county and a type of business; read the brief here or download it as a PDF."""
import re
import pandas as pd
import streamlit as st
import brief
import lib
from lib import COUNTIES


def show_rows(rows, county, key):
    if not rows:
        return
    d = pd.DataFrame(rows).rename(columns={"measure": "Measure", "county": f"{county} County",
                                           "state": "North Dakota", "note": "Note"})
    st.dataframe(d, hide_index=True, width="stretch", key=key)


def page():
    lib.header("Market brief", "A short, printable profile of the market for one type of business in one North Dakota "
               "county: people and income, businesses already there, retail sales against local income, and "
               "openings, survival and owner age.", "official", "estimate",
               note="Census Bureau, BLS and ND Tax Commissioner; per-resident figures, pull factors and survival: "
                    "IPBA calculations.")
    missing = brief.ready()
    if missing:
        st.info("The tables this brief needs have not been built yet. Run `py -3.15 src/run_all.py`.")
        return
    c = st.columns(2)
    county = c[0].selectbox("County", sorted(COUNTIES.values()), index=sorted(COUNTIES.values()).index("Cass"),
                            key="brief_county")
    kind = c[1].selectbox("Type of business", list(brief.KINDS), key="brief_kind")
    b = brief.build(county, kind)
    st.subheader(f"{kind}: {county} County")
    st.caption(f"{b['region']}. Figures for all of {brief.SECTOR_NAME[b['sector']]} unless a store type is named.")
    with st.container(border=True):
        st.markdown("**What the data show**")
        st.markdown(lib.esc("\n".join(f"- {x}" for x in b["findings"])) if b["findings"] else
                    "Too few businesses of this kind in the county for most figures to be published.")
    st.download_button("Download this brief (PDF)", data=brief.pdf(b), mime="application/pdf",
                       file_name=re.sub(r"[^A-Za-z0-9]+", "_", f"Market brief {kind} {county} County").strip("_") + ".pdf",
                       icon=":material/download:", key="brief_pdf")
    st.markdown("##### People and income")
    show_rows(b["people"], county, "brief_people")
    st.markdown("##### Businesses in this field")
    show_rows(b["market"], county, "brief_market")
    if b["retail"]:
        st.markdown("##### Retail sales against local income, 2022")
        show_rows(b["retail"], county, "brief_retail")
    st.markdown("##### Openings, closings, survival and owners")
    show_rows(b["dynamics"], county, "brief_dyn")
    if b["peers"]:
        st.markdown(f"**Similar counties elsewhere in the US:** {', '.join(b['peers'])} (see Market finder).")
    st.markdown("##### Read with care")
    st.markdown("\n".join(f"- {x}" for x in b["caveats"]))
    lib.method_panel([
        "People and income: ACS 5-year estimates with 90% margins; unemployment: BLS LAUS, average of the latest 12 months.",
        "Businesses: County Business Patterns (employer establishments, employees, payroll) and Nonemployer Statistics, "
        "by NAICS sector; per 1,000 residents with ACS population; the state figure sums the 53 counties.",
        "Retail sales: 2022 Economic Census by store type; pull factor = county sales / (state sales x county share of "
        "ND household income) (Hustedde et al., 1984); counties Census withheld are estimated and flagged.",
        "Openings and closings: Census BDS for the county, all industries; survival and owner age: statewide for the "
        "sector (Census BDS and Annual Business Survey), because county figures are not published.",
        "The brief describes a market from public, aggregated data; it does not evaluate any business or site."],
        refs=("hustedde1984",))
    lib.source_line("acs", "laus", "cbp", "nes", "econ_census", "bds", "bds_sec_fa", "abs", "taxable_sales")


if __name__ == "__main__":
    page()
