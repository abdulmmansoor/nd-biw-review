"""About the data: sources and dates, definitions, geography, data checks."""
import pandas as pd
import streamlit as st
import lib
from lib import ORG, REGIONS


def release_date(v):
    """Release date for the sources table: the publisher's date, the day a new period was first found, or a reason."""
    basis = v.get("released_basis", "")
    if v.get("released"):
        return lib.as_of(v["released"]) + (" (first found)" if basis.startswith("first found") else "")
    return {"one-time report": "One-time report",
            "recorded from the next release": "Recorded from the next release"}.get(basis, "Not given by the publisher")


def update_note():
    u = lib.update_status()
    last = ""
    if u.get("finished"):
        new = len(u.get("new_files", []))
        last = (f" The last automatic check ran on {lib.as_of(u['finished'])} and found "
                f"{'no new files' if not new else str(new) + ' new or revised file' + ('s' if new > 1 else '')}.")
    return ("**Release dates and updates.** *Released* is the date on the publisher's own file for the data shown. "
            "Where the data come through an API with no file date, it is the day the dashboard first found the "
            "latest period (marked *first found*). Every source is checked with its publisher once a day and the tables "
            "are rebuilt with all data checks, so a new release reaches the dashboard within a day of publication; "
            f"yearly sources move to the new year on their own.{last}")


def page():
    lib.header("About the data", "Where every number comes from, how current it is, and how to read it.")
    st.markdown(
        f"ND Business and Innovation Watch is an independent, nonpartisan public dashboard by the {ORG}. It brings "
        "together free public data to help businesses of every size, entrepreneurs, economic developers, lenders and "
        "researchers make decisions about North Dakota markets. It does not endorse any business, program or policy.")

    st.subheader("Sources and dates")
    s = lib.sources()
    if s:
        t = pd.DataFrame([{"Data": v["name"], "Publisher": v["publisher"], "Period shown": v["period"],
                           "Latest": v["latest"], "Released": release_date(v), "How often": v.get("cadence", ""),
                           "Link": v["url"],
                           "Last checked": lib.as_of(v["refreshed"]) if v.get("refreshed") else ""}
                          for v in s.values()])
        st.dataframe(t, hide_index=True, width="stretch", column_config={"Link": st.column_config.LinkColumn()})
        st.markdown(update_note())
    st.markdown(
        "- Every figure comes from public, aggregated statistics. No confidential or business-level data are used.\n"
        "- Agencies withhold or add noise to small cells so that no single business can be identified. Withheld "
        "values are left empty (tables show \"None\"), never shown as zero.\n"
        "- Survey estimates (American Community Survey) carry a 90% margin of error: the true value is likely within that range. "
        "Estimates are flagged 'use with caution' when the coefficient of variation (standard error / estimate) is "
        "15-30% and 'low reliability' above 30%; differences between places are called significant only at the 90% "
        "level.\n"
        "- Per-resident rates use each year's population (Census Population Estimates).\n"
        "- Dollar values are in current dollars unless marked 'real' (adjusted for inflation).")

    st.subheader("How to cite")
    c = lib.checks()
    asof = pd.Timestamp(c["run"]) if c.get("run") else pd.Timestamp.today()
    citation = (f"Institute of Policy and Business Analytics. ({asof.year}). *ND Business and Innovation Watch* "
                f"(Version {asof:%Y.%m.%d}) [Data dashboard, data as of {asof:%B %d, %Y}]. Nistler College of Business & Public Administration, "
                "University of North Dakota.")
    st.markdown(lib.esc(citation))
    st.caption("APA 7th edition. Please add the date you accessed the page and its web address, and name the original "
               "source (listed above) when quoting a single figure.")

    st.subheader("Download all data")
    import data_dictionary as dd
    st.download_button("Download all published tables (ZIP, CSV files with a data dictionary)",
                       data=dd.zip_bytes(citation.replace("*", "")), mime="application/zip", key="zip_all",
                       file_name=f"nd_business_innovation_watch_{asof:%Y%m%d}.zip")
    with st.expander("Data dictionary: every published table and column"):
        st.dataframe(dd.dictionary().rename(columns={"file": "File", "table": "Table", "column": "Column",
                                                     "meaning": "Meaning"}), hide_index=True, width="stretch")

    st.subheader("Key terms")
    st.markdown(
        "- **Business application:** a request for an employer identification number (EIN) for a business. "
        "**High-propensity** applications have features linked to later hiring.\n"
        "- **Small business:** there is no single definition. The SBA Office of Advocacy counts firms with fewer than "
        "500 employees; SBA size standards for loans and contracts vary by industry. This dashboard shows the size "
        "classes the Census Bureau publishes (for example, fewer than 20 employees) and says which one it uses.\n"
        "- **Establishment:** a single physical business location. A firm can have many establishments.\n"
        "- **Nonemployer business:** a business with no paid employees, most often a self-employed person.\n"
        "- **Location quotient (LQ):** an industry's share of local jobs divided by its share of US jobs. Above 1 "
        "means the place is more specialized in that industry than the nation. LQs based on fewer than 50 jobs are "
        "flagged 'small base'.\n"
        "- **Diffusion index:** the share of indicators better than a year earlier; above 50% means more are improving "
        "than worsening.\n"
        "- **Shift-share:** splits job change into US growth, industry mix and local factors; the dynamic version adds "
        "up the parts year by year.\n"
        "- **Taxable sales and purchases:** the base on which North Dakota sales and use tax is figured.")

    st.subheader("Geography")
    st.markdown("North Dakota's 53 counties are grouped into the eight state planning regions, each served by a "
                "regional council. Peer states are Minnesota, Montana, South Dakota and Wyoming.")
    st.dataframe(pd.DataFrame([{"Planning region": r, "Counties": ", ".join(c)} for r, c in REGIONS.items()]),
                 hide_index=True, width="stretch")

    st.subheader("Data checks")
    c = lib.checks()
    if c:
        st.markdown(f"Last update: **{c['status']}** ({pd.Timestamp(c['run']):%B %d, %Y}). Each update is checked "
                    "automatically before it is shown.")
        st.dataframe(pd.DataFrame(c["checks"]).assign(detail=lambda d: d.detail.map(
                         lambda x: ", ".join(f"{k} {v}" for k, v in x.items()) if isinstance(x, dict) else str(x))).rename(columns={"check": "Check", "status": "Result", "detail": "Detail"}),
                     hide_index=True, width="stretch")
    st.subheader("What changed")
    from changes import CHANGES
    for when, items in CHANGES:
        st.markdown(f"**{when}**\n" + "\n".join(f"- {lib.esc(i)}" for i in items))

    st.subheader("Contact")
    st.markdown(lib.contact_line())

    st.subheader("References")
    from references import REFERENCES, sorted_keys
    st.markdown("Methods and ideas the pages draw on (APA 7th edition). Data sources, with their dates, are listed under "
                "Sources and dates above and at the foot of each page.")
    st.markdown("\n".join(f"- {lib.esc(REFERENCES[k])}" for k in sorted_keys()))
    st.caption("Accessibility: every chart has a table view with a CSV download. To report a problem or ask for the "
               "data in another format, see Contact above.")


if __name__ == "__main__":
    page()
