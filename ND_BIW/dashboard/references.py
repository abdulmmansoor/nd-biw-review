"""One reference list for the whole dashboard (APA 7th edition), identical to the Framework and Methods deck.

Pages cite works by key, e.g. lib.method_panel(lines, ["isserman1977", "porter2003"]); the About the data page lists all
of them. Data sources are cited separately, with dates, in each page's source line and the About page's sources table.
Markdown italics (*...*) mark journal and book titles.
"""

REFERENCES = {
    "muro2015": "Muro, M., Rothwell, J., Andes, S., Fikri, K., & Kulkarni, S. (2015). *America's advanced industries: What they are, where they are, and why they matter*. Brookings Institution.",
    "isserman_westervelt2006": "Isserman, A. M., & Westervelt, J. (2006). 1.5 million missing numbers: Overcoming "
                               "employment suppression in County Business Patterns data. *International Regional Science "
                               "Review, 29*(3), 311–335.",
    "hustedde1984": "Hustedde, R. J., Shaffer, R., & Pulver, G. (1984). *Community economic analysis: A how to "
                    "manual*. North Central Regional Center for Rural Development, Iowa State University.",
    "elsby2015": "Elsby, M. W. L., Michaels, R., & Ratner, D. (2015). The Beveridge curve: A survey. *Journal of "
                 "Economic Literature, 53*(3), 571–630.",
    "barff_knight1988": "Barff, R. A., & Knight, P. L., III. (1988). Dynamic shift-share analysis. *Growth and Change, "
                        "19*(2), 1–10.",
    "bayard2018": "Bayard, K., Dinlersoz, E., Dunne, T., Haltiwanger, J., Miranda, J., & Stevens, J. (2018). *Early-stage "
                  "business formation: An analysis of applications for employer identification numbers* (NBER Working "
                  "Paper No. 24364). National Bureau of Economic Research.",
    "burns1946": "Burns, A. F., & Mitchell, W. C. (1946). *Measuring business cycles*. National Bureau of Economic Research.",
    "census2020": "U.S. Census Bureau. (2020). *Understanding and using American Community Survey data: What all data users "
                  "need to know*. U.S. Government Publishing Office.",
    "decker2014": "Decker, R., Haltiwanger, J., Jarmin, R., & Miranda, J. (2014). The role of entrepreneurship in US job "
                  "creation and economic dynamism. *Journal of Economic Perspectives, 28*(3), 3–24.",
    "flegg_tohmo2013": "Flegg, A. T., & Tohmo, T. (2013). Regional input–output tables and the FLQ formula: A case study of "
                       "Finland. *Regional Studies, 47*(5), 703–721.",
    "flegg_webber1997": "Flegg, A. T., & Webber, C. D. (1997). On the appropriate use of location quotients in generating "
                        "regional input–output tables: Reply. *Regional Studies, 31*(8), 795–805.",
    "gardner1985": "Gardner, E. S., Jr. (1985). Exponential smoothing: The state of the art. *Journal of Forecasting, 4*(1), "
                   "1–28.",
    "gibbs2021": "Gibbs, I., & Candès, E. (2021). Adaptive conformal inference under distribution shift. *Advances in Neural "
                 "Information Processing Systems, 34*.",
    "griliches1990": "Griliches, Z. (1990). Patent statistics as economic indicators: A survey. *Journal of Economic "
                     "Literature, 28*(4), 1661–1707.",
    "haltiwanger2013": "Haltiwanger, J., Jarmin, R. S., & Miranda, J. (2013). Who creates jobs? Small versus large versus "
                       "young. *Review of Economics and Statistics, 95*(2), 347–361.",
    "hyndman2021": "Hyndman, R. J., & Athanasopoulos, G. (2021). *Forecasting: Principles and practice* (3rd ed.). OTexts.",
    "isserman1977": "Isserman, A. M. (1977). The location quotient approach to estimating regional economic impacts. "
                    "*Journal of the American Institute of Planners, 43*(1), 33–41.",
    "miller_blair2022": "Miller, R. E., & Blair, P. D. (2022). *Input–output analysis: Foundations and extensions* (3rd ed.). "
                        "Cambridge University Press.",
    "porter2003": "Porter, M. E. (2003). The economic performance of regions. *Regional Studies, 37*(6–7), 549–578.",
    "stevens_moore1980": "Stevens, B. H., & Moore, C. L. (1980). A critical review of the literature on shift-share as a "
                         "forecasting technique. *Journal of Regional Science, 20*(4), 419–437.",
    "tiebout1956": "Tiebout, C. M. (1956). Exports and regional economic growth. *Journal of Political Economy, 64*(2), "
                   "160–164.",
    "valliant2018": "Valliant, R., Dever, J. A., & Kreuter, F. (2018). *Practical tools for designing and weighting survey "
                    "samples* (2nd ed.). Springer.",
    "oecd2018": "OECD & Eurostat. (2018). *Oslo Manual 2018: Guidelines for collecting, reporting and using data on "
                "innovation* (4th ed.). OECD Publishing.",
    "watson2007": "Watson, P., Wilson, J., Thilmany, D., & Winter, S. (2007). Determining economic contributions and impacts: "
                  "What is the difference and why do we care? *Journal of Regional Analysis and Policy, 37*(2), 140–146.",
}


def sorted_keys():
    """All works in reference-list order (alphabetical by entry)."""
    return sorted(REFERENCES, key=lambda k: REFERENCES[k].lower())
