"""ND Business and Innovation Watch - Streamlit dashboard.

Run from the project folder:  py -3.15 -m streamlit run dashboard/app.py   (or Start_Dashboard.bat)
Data tables come from `py -3.15 src/run_all.py`.
"""
import streamlit as st
import lib
import review
import page_about
import page_outlook
import page_conditions
import page_impact
import page_industry
import page_market
import page_pulse
import page_scorecard
import page_workforce
import page_retail
import page_trade
import page_capital
import page_cost
import page_freight
import page_cases
import page_support
import page_brief
import page_innovation
import page_survey
import page_impact_advanced

st.set_page_config(page_title="ND Business and Innovation Watch", page_icon=":material/storefront:", layout="wide")
st.markdown(lib.CSS, unsafe_allow_html=True)

# Sidebar sections as in ND Fiscal and Economic Watch: one organising scheme per level, each page in one place, two
# levels at most; monitoring before analysis; methods and information last. Strings are sub-headings.
sections = [
    ("", [st.Page(page_outlook.overview_page, title="Business and Innovation Overview", icon=":material/dashboard:",
                  default=True)]),
    ("Business and Innovation Outlook", [
        st.Page(page_outlook.evolving_page, title="Evolving dynamics", icon=":material/timeline:", url_path="evolving-dynamics"),
        st.Page(page_conditions.conditions_page, title="Current realities", icon=":material/today:", url_path="current-realities"),
        st.Page(page_conditions.outlook_page, title="Future implications", icon=":material/explore:",
                url_path="future-implications"),
    ]),
    ("Business Indicators", [
        st.Page(page_pulse.page, title="Business pulse", icon=":material/monitor_heart:", url_path="pulse"),
        st.Page(page_conditions.indicators_page, title="Business and innovation indicators", icon=":material/monitoring:",
                url_path="indicators"),
        st.Page(page_survey.page, title="Business survey" + (" (test data)" if page_survey.test_build() else ""),
                icon=":material/poll:", url_path="business-survey"),
        st.Page(page_scorecard.page, title="Peer scorecard", icon=":material/leaderboard:", url_path="scorecard"),
    ]),
    ("Industries & Innovation", [
        st.Page(page_industry.page, title="Industry profiles", icon=":material/factory:", url_path="industry"),
        st.Page(page_innovation.page, title="Innovation", icon=":material/lightbulb:", url_path="innovation"),
        st.Page(page_cases.page, title="Case studies", icon=":material/menu_book:", url_path="case-studies"),
    ]),
    ("Markets & Places", [
        "Local markets",
        st.Page(page_market.page, title="Market finder", icon=":material/map:", url_path="market"),
        st.Page(page_brief.page, title="Market brief", icon=":material/description:", url_path="market-brief"),
        st.Page(page_retail.page, title="Retail gap", icon=":material/shopping_cart:", url_path="retail-gap"),
        "Trade and logistics",
        st.Page(page_trade.page, title="Trade and exports", icon=":material/public:", url_path="trade"),
        st.Page(page_freight.page, title="Freight and supply chain", icon=":material/local_shipping:", url_path="freight"),
    ]),
    ("Business Climate & Support", [
        st.Page(page_workforce.page, title="Workforce and talent", icon=":material/groups:", url_path="workforce"),
        st.Page(page_cost.page, title="Cost of doing business", icon=":material/payments:", url_path="cost"),
        st.Page(page_capital.page, title="Capital and support", icon=":material/account_balance:", url_path="capital"),
        st.Page(page_support.page, title="Business support insights", icon=":material/handshake:",
                url_path="business-support"),
    ]),
    ("Impact Model", [
        "Results",
        st.Page(page_impact.contribution_page, title="Economic contribution", icon=":material/hub:", url_path="contribution"),
        st.Page(page_impact.whatif_page, title="What-if impact", icon=":material/calculate:", url_path="what-if"),
        "Methods",
        st.Page(page_impact_advanced.page, title="Advanced analysis", icon=":material/insights:",
                url_path="impact-advanced"),
        st.Page(page_impact.checks_page, title="Model method and checks", icon=":material/fact_check:", url_path="model-checks"),
    ]),
    ("About", [st.Page(page_about.page, title="About the data", icon=":material/info:", url_path="about")]),
]
review.gate()
nav = st.navigation([e for _, es in sections for e in es if not isinstance(e, str)], position="hidden")
lib.sidebar_nav(sections, nav)
lib.sidebar()
review.bar(nav)
nav.run()
