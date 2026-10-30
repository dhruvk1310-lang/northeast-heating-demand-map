"""Generate the Tableau workbook: "The Thermal Year" and "Where the Year-Round Money Is".

The map data source (county shapes related to monthly county data) comes from
tableau/templates/map_datasource.xml, saved from a workbook Tableau built, so
the spatial relationship is exactly what Tableau expects. Everything else
(parameters, the other data sources, worksheets, dashboards, and the dark
ember/ice styling) is written here.

Run from the project root (after src.load.export_tableau):
    python -m src.load.build_tableau_workbook
Then open tableau/northeast_thermal_year.twb in Tableau Public.
"""

import uuid

import pandas as pd
from xml.sax.saxutils import escape, quoteattr

from src.config import ROOT
from src.load.build_tableau_extracts import EXTRACTS, HYPER_FILES, OBJECTS

TABLEAU = ROOT / "tableau"
DATA = TABLEAU / "data"
OUT = TABLEAU / "northeast_thermal_year.twb"
SEASON = "2025-26"

# Palette ----------------------------------------------------------------------
BG = "#0B1220"
PANEL = "#111A2E"
TEXT = "#E8E6E1"
MUTED = "#8B95A7"
FAINT = "#3A4659"
EMBER = "#E0662B"
GOLD = "#FFC46B"
EMBER_DIM = "#7A3416"
ICE = "#5FB4E8"
ICE_LIGHT = "#BFE9FF"
ICE_DIM = "#24618F"
DIVERGING = [ICE_LIGHT, ICE, ICE_DIM, "#16233A", EMBER_DIM, EMBER, GOLD]
QUADRANTS = {"Year-round": "#F2C14E", "Winter only": EMBER, "Summer only": ICE, "Low demand": FAINT}
FONT = "Tableau Book"
FONT_BOLD = "Tableau Semibold"

# Data source names --------------------------------------------------------------
MAP = "federated.1d875mm13w789317ga6xj1ro064z"
PULSE = "federated.pulse0thermal0year0000000001"
SCORES = "federated.scores0thermal0year00000001"
CT_REGIONS = "federated.ctregions0thermal0year000001"
CT_PROSPECTS = "federated.ctprospects0thermal0year0001"
PARAMS = "Parameters"
P_MONTH = "[Parameter 1]"
CAPTIONS = {CT_REGIONS: "Connecticut regions", CT_PROSPECTS: "Connecticut dealers",
            MAP: "counties.geojson+ (Multiple Connections)", PULSE: "Seasonal pulse",
            SCORES: "County scores"}
P_BASIS = "[Parameter 2]"
# True when a row's month_date is the month chosen in the Month parameter.
MONTH_MATCH = f"[month_label] = [Parameters].{P_MONTH}"


def q(s: str) -> str:
    return quoteattr(s)


def simple_id(name: str) -> str:
    """Stable UUID per object name, so regenerating the workbook does not churn its IDs."""
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, "northeast-thermal-year/" + name)).upper() + "}"


# Data sources ---------------------------------------------------------------------

SEASON_MONTHS = pd.date_range("2025-07-01", "2026-06-01", freq="MS")
DEFAULT_MONTH = "January 2026"


def param_columns(pad: str) -> str:
    """The two parameters. The month is a list (not a range) so each value shows as e.g. "January 2026"."""
    months = "\n".join(f"{pad}    <member value='&quot;{d:%B %Y}&quot;' />" for d in SEASON_MONTHS)
    return f"""{pad}<column caption='Month' datatype='string' name='{P_MONTH}' param-domain-type='list' role='measure' type='nominal' value='&quot;{DEFAULT_MONTH}&quot;'>
{pad}  <calculation class='tableau' formula='&quot;{DEFAULT_MONTH}&quot;' />
{pad}  <members>
{months}
{pad}  </members>
{pad}</column>
{pad}<column caption='Rank counties by' datatype='string' name='{P_BASIS}' param-domain-type='list' role='measure' type='nominal' value='&quot;Total&quot;'>
{pad}  <calculation class='tableau' formula='&quot;Total&quot;' />
{pad}  <members>
{pad}    <member value='&quot;Total&quot;' />
{pad}    <member value='&quot;Per home&quot;' />
{pad}  </members>
{pad}</column>"""


def parameters() -> str:
    return f"""
    <datasource hasconnection='false' inline='true' name='{PARAMS}' version='18.1'>
      <aliases enabled='yes' />
{param_columns("      ")}
    </datasource>"""


MAP_CALCS = {
    "Calculation_selected_month": ("Selected month", "boolean", "dimension", "nominal",
                                   MONTH_MATCH),
    "Calculation_county_label": ("County", "string", "dimension", "nominal",
                                 "REPLACE(REPLACE([county_name], ' Planning Region', ''), ' County', '') + ', ' + [state_abbr]"),
}


def calc_column(name, caption, datatype, role, kind, formula) -> str:
    return (f"      <column caption={q(caption)} datatype='{datatype}' name='[{name}]' role='{role}' type='{kind}'>\n"
            f"        <calculation class='tableau' formula={q(formula)} />\n      </column>\n")


def extract_xml(hyper: str, object_ids: list[str], col_maps: list[tuple[str, str, str]]) -> str:
    """Point a data source at its .hyper file. col_maps: (field key, object id, column)."""
    rels = "\n".join(f"            <relation name='{o}' table='[Extract].[{o}]' type='table' />" for o in object_ids)
    cols = "\n".join(f"            <map key='[{k}]' value='[{o}].[{c}]' />" for k, o, c in col_maps)
    return f"""      <extract count='-1' enabled='true' object-id='' units='records'>
        <connection access_mode='readonly' author-locale='en_US' class='hyper' dbname={q(str(EXTRACTS / hyper))} default-settings='hyper' schema='Extract' sslmode='' tablename='Extract' update-time='10/28/2026 09:00:00 PM' username='tableau_internal_user'>
          <relation type='collection'>
{rels}
          </relation>
          <cols>
{cols}
          </cols>
        </connection>
      </extract>
"""


def map_datasource() -> str:
    import re
    xml = (TABLEAU / "templates" / "map_datasource.xml").read_text()
    calcs = "".join(calc_column(n, *v) for n, v in MAP_CALCS.items())
    xml = xml.replace("      <aliases enabled='yes' />\n", "      <aliases enabled='yes' />\n" + calcs, 1)
    # month_label was added to county_month.csv after the template was saved.
    for indent in re.findall(r"\n( +)<column datatype='real' name='thermal_load' ordinal='18' />", xml):
        old = f"{indent}<column datatype='real' name='thermal_load' ordinal='18' />"
        xml = xml.replace(old, old + f"\n{indent}<column datatype='string' name='month_label' ordinal='19' />", 1)
    xml = xml.replace("          <map key='[thermal_load]' value='[county_month.csv].[thermal_load]' />",
                      "          <map key='[thermal_load]' value='[county_month.csv].[thermal_load]' />\n"
                      "          <map key='[month_label]' value='[county_month.csv].[month_label]' />", 1)
    xml = xml.replace("      <column caption='Thermal Load'",
                      "      <column caption='Month Label' datatype='string' name='[month_label]' role='dimension' type='nominal' />\n"
                      "      <column caption='Thermal Load'", 1)
    tables = {"counties.geojson": OBJECTS["counties"], "county_month.csv": OBJECTS["county_month"]}
    live_cols = re.search(r"<cols>(.*?)</cols>", xml, re.S).group(1)
    col_maps = [(k, tables[t], c) for k, t, c in re.findall(r"<map key='\[(.*?)\]' value='\[(.*?)\]\.\[(.*?)\]' />", live_cols)]
    extract = extract_xml(HYPER_FILES["map"], list(tables.values()), col_maps)
    return xml.replace("      <layout dim-ordering", extract + "      <layout dim-ordering", 1)


def text_datasource(ds: str, caption: str, filename: str, columns: list[tuple], calcs: dict,
                    object_key: str, hyper_key: str) -> str:
    """A single-CSV data source backed by an extract. columns: (name, datatype, role, type, caption)."""
    conn = "textscan." + ds.split(".")[1]
    table = filename.replace(".csv", "#csv")
    oid = OBJECTS[object_key]
    rel_cols = "\n".join(
        f"            <column datatype='{dt}' name='{n}' ordinal='{i}' />" for i, (n, dt, *_ ) in enumerate(columns))
    live_maps = "\n".join(f"          <map key='[{n}]' value='[{filename}].[{n}]' />" for n, *_ in columns)
    relation = (f"<relation connection='{conn}' name='{filename}' table='[{table}]' type='table'>\n"
                f"          <columns character-set='UTF-8' header='yes' locale='en_US' separator=','>\n"
                f"{rel_cols}\n          </columns>\n        </relation>")
    extract = extract_xml(HYPER_FILES[hyper_key], [oid], [(n, oid, n) for n, *_ in columns])
    decl = "".join(
        f"      <column caption={q(cap)} datatype='{dt}' name='[{n}]' role='{role}' type='{kind}' />\n"
        for n, dt, role, kind, cap in columns)
    calc_xml = "".join(calc_column(n, *v) for n, v in calcs.items())
    return f"""
    <datasource caption={q(caption)} inline='true' name='{ds}' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption={q(caption)} name='{conn}'>
            <connection class='textscan' directory={q(str(DATA))} filename='{filename}' password='' server='' workgroup-auth-mode='as-is' />
          </named-connection>
        </named-connections>
        {relation}
        <cols>
{live_maps}
        </cols>
      </connection>
      <aliases enabled='yes' />
{decl}{calc_xml}{extract}      <layout dim-ordering='alphabetic' measure-ordering='alphabetic' show-structure='true' />
      <object-graph>
        <objects>
          <object caption='{filename}' id='{oid}'>
            <properties context=''>
              {relation}
            </properties>
            <properties context='extract'>
              <relation name='{oid}' table='[Extract].[{oid}]' type='table' />
            </properties>
          </object>
        </objects>
      </object-graph>
    </datasource>"""


def pulse_datasource() -> str:
    cols = [
        ("heating_season", "string", "dimension", "nominal", "Heating Season"),
        ("month_date", "date", "dimension", "ordinal", "Month Date"),
        ("month_order", "integer", "dimension", "ordinal", "Month Order"),
        ("month_abbr", "string", "dimension", "nominal", "Month"),
        ("kind", "string", "dimension", "nominal", "Kind"),
        ("share", "real", "measure", "quantitative", "Share of Season"),
        ("heating_gallons", "real", "measure", "quantitative", "Heating Gallons"),
        ("heating_spend", "real", "measure", "quantitative", "Heating Spend"),
        ("cooling_index", "real", "measure", "quantitative", "Cooling Index"),
        ("month_label", "string", "dimension", "nominal", "Month Label"),
    ]
    calcs = {"Calculation_bar_code": (
        "Bar color code", "integer", "measure", "quantitative",
        f"IF [kind] = 'Cooling' AND {MONTH_MATCH} THEN 2 ELSEIF [kind] = 'Cooling' THEN 1 ELSEIF {MONTH_MATCH} THEN 4 ELSE 3 END")}
    return text_datasource(PULSE, "Seasonal pulse", "seasonal_pulse.csv", cols, calcs, "seasonal_pulse", "pulse")


def ct_regions_datasource() -> str:
    cols = [
        ("region", "string", "dimension", "nominal", "Region"),
        ("oil_homes", "integer", "measure", "quantitative", "Oil Homes"),
        ("propane_homes", "integer", "measure", "quantitative", "Propane Homes"),
        ("dealers", "integer", "measure", "quantitative", "Dealers"),
        ("hvac_dealers", "integer", "measure", "quantitative", "Full-Service Dealers"),
        ("pct_full_service", "real", "measure", "quantitative", "% Full-Service"),
        ("homes_per_dealer", "real", "measure", "quantitative", "Homes per Dealer"),
        ("spend_per_dealer_musd", "real", "measure", "quantitative", "Spend per Dealer ($M)"),
        ("underserved_rank", "integer", "measure", "quantitative", "Under-served Rank"),
    ]
    return text_datasource(CT_REGIONS, "Connecticut regions", "ct_regions.csv", cols, {}, "ct_regions", "ct_regions")


CT_PROSPECT_COLS = [
    ("prospect_rank", "integer", "measure", "quantitative", "Prospect Rank"),
    ("label", "string", "dimension", "nominal", "Dealer"),
    ("name", "string", "dimension", "nominal", "Name"),
    ("town", "string", "dimension", "nominal", "Town"),
    ("region", "string", "dimension", "nominal", "Region"),
    ("offers_hvac_service", "integer", "measure", "quantitative", "Offers HVAC Service"),
    ("years_licensed", "real", "measure", "quantitative", "Years Licensed"),
    ("region_homes_per_dealer", "real", "measure", "quantitative", "Region Homes per Dealer"),
    ("fit_score", "real", "measure", "quantitative", "Fit Score"),
]


def ct_prospects_datasource() -> str:
    calcs = {"Calculation_top_15": ("Top 15", "boolean", "dimension", "nominal", "[prospect_rank] <= 15"),
             "Calculation_fit_label": ("Fit score label", "string", "dimension", "nominal", "STR(ROUND([fit_score], 1))")}
    return text_datasource(CT_PROSPECTS, "Connecticut dealers", "ct_prospects.csv", CT_PROSPECT_COLS, calcs,
                           "ct_prospects", "ct_prospects")


def scores_datasource() -> str:
    cols = [
        ("county_key", "string", "dimension", "nominal", "County Key"),
        ("county_name", "string", "dimension", "nominal", "County Name"),
        ("state_abbr", "string", "dimension", "nominal", "State"),
        ("heating_season", "string", "dimension", "nominal", "Heating Season"),
        ("total_occupied", "integer", "measure", "quantitative", "Homes"),
        ("oil_homes", "integer", "measure", "quantitative", "Oil Homes"),
        ("propane_homes", "integer", "measure", "quantitative", "Propane Homes"),
        ("oil_propane_share", "real", "measure", "quantitative", "Oil + Propane Share"),
        ("heating_spend", "real", "measure", "quantitative", "Heating Spend"),
        ("cooling_index", "real", "measure", "quantitative", "Cooling Index"),
        ("basis", "string", "dimension", "nominal", "Basis"),
        ("heating_pct", "real", "measure", "quantitative", "Heating Percentile"),
        ("cooling_pct", "real", "measure", "quantitative", "Cooling Percentile"),
        ("year_round_score", "real", "measure", "quantitative", "Year-Round Score"),
        ("year_round_rank", "integer", "measure", "quantitative", "Year-Round Rank"),
        ("quadrant", "string", "dimension", "nominal", "Quadrant"),
        ("label", "string", "dimension", "nominal", "Label"),
        ("heating_spend_per_home", "real", "measure", "quantitative", "Heating Spend per Home"),
    ]
    calcs = {
        "Calculation_basis_match": ("Basis matches", "boolean", "dimension", "nominal",
                                    f"[basis] = [Parameters].{P_BASIS}"),
        "Calculation_top_12": ("Top 12", "boolean", "dimension", "nominal", "[year_round_rank] <= 12"),
        "Calculation_quadrant_code": ("Quadrant color code", "integer", "measure", "quantitative", "CASE [quadrant] WHEN 'Low demand' THEN 1 WHEN 'Summer only' THEN 2 WHEN 'Winter only' THEN 3 ELSE 4 END"),
        "Calculation_score_100": ("Score (0-100)", "string", "dimension", "nominal",
                                  "STR(INT(ROUND([year_round_score] * 100, 0)))"),
        "Calculation_county_label": ("County", "string", "dimension", "nominal",
                                     "REPLACE(REPLACE([county_name], ' Planning Region', ''), ' County', '') + ', ' + [state_abbr]"),
    }
    return text_datasource(SCORES, "County scores", "county_scores.csv", cols, calcs, "county_scores", "scores")


# Worksheets ----------------------------------------------------------------------

def inst(ds, field, deriv, kind):
    """Column-instance reference, e.g. inst(MAP, 'thermal_load', 'avg', 'qk')."""
    return f"[{ds}].[{deriv}:{field}:{kind}]"


DERIVATION = {"none": "None", "sum": "Sum", "avg": "Avg", "attr": "Attribute", "clct": "Collect"}


def deps(ds: str, columns: list[tuple], instances: list[tuple]) -> str:
    """columns: (name, datatype, role, type, caption[, formula]); instances: (field, deriv, kind, type)."""
    out = [f"          <datasource-dependencies datasource='{ds}'>"]
    for c in columns:
        name, dt, role, kind, cap = c[:5]
        if len(c) > 5:
            out.append(f"            <column caption={q(cap)} datatype='{dt}' name='[{name}]' role='{role}' type='{kind}'>")
            out.append(f"              <calculation class='tableau' formula={q(c[5])} />")
            out.append("            </column>")
        else:
            out.append(f"            <column caption={q(cap)} datatype='{dt}' name='[{name}]' role='{role}' type='{kind}' />")
    for field, deriv, kind, typ in instances:
        out.append(f"            <column-instance column='[{field}]' derivation='{DERIVATION[deriv]}' "
                   f"name='[{deriv}:{field}:{kind}]' pivot='key' type='{typ}' />")
    out.append("          </datasource-dependencies>")
    return "\n".join(out)


PARAM_DEPS = f"""          <datasource-dependencies datasource='{PARAMS}'>
{param_columns("            ")}
          </datasource-dependencies>"""


def member_filter(ds, field, kind, member) -> str:
    """Keep only one value. Text values must be passed with their double quotes, e.g. '"2025-26"'."""
    level = f"[none:{field}:{kind}]"
    return (f"        <filter class='categorical' column='[{ds}].{level}'>\n"
            f"          <groupfilter function='member' level='{level}' member={q(member)} "
            f"user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate' />\n"
            f"        </filter>")


def manual_sort(field_ref: str, values: list[str]) -> str:
    buckets = "\n".join(f"              <bucket>&quot;{escape(v)}&quot;</bucket>" for v in values)
    return (f"          <sort class='manual' column='{field_ref}' direction='ASC'>\n"
            f"            <dictionary>\n{buckets}\n            </dictionary>\n          </sort>")


def sheet_style(extra: str = "") -> str:
    return f"""        <style>
          <style-rule element='table'>
            <format attr='background-color' value='{BG}' />
          </style-rule>
          <style-rule element='worksheet'>
            <format attr='font-family' value='{FONT}' />
            <format attr='color' value='{MUTED}' />
            <format attr='display-field-labels' scope='cols' value='false' />
            <format attr='display-field-labels' scope='rows' value='false' />
          </style-rule>
          <style-rule element='gridline'>
            <format attr='line-visibility' value='off' />
          </style-rule>
          <style-rule element='zeroline'>
            <format attr='line-visibility' value='off' />
          </style-rule>
          <style-rule element='dropline'>
            <format attr='line-visibility' value='off' />
          </style-rule>
          <style-rule element='table-div'>
            <format attr='line-visibility' scope='rows' value='off' />
            <format attr='line-visibility' scope='cols' value='off' />
          </style-rule>
          <style-rule element='pane'>
            <format attr='background-color' value='{BG}' />
          </style-rule>
{extra}        </style>"""


def tooltip(runs: list[tuple[str, str, str]]) -> str:
    """runs: (text, color, weight) where text may contain <[field]> references."""
    body = ""
    for text, color, bold in runs:
        b = " bold='true'" if bold else ""
        line_break = text.endswith("\n")
        body += f"              <run{b} fontcolor='{color}' fontname='{FONT}'>{escape(text.rstrip(chr(10)))}</run>\n"
        if line_break:
            body += "              <run>Æ&#10;</run>\n"  # Tableau's line-break marker
    return f"""            <customized-tooltip>
              <formatted-text>
{body}              </formatted-text>
            </customized-tooltip>"""


def worksheet(name, view_ds, view, style, panes, rows, cols, title=None) -> str:
    title_xml = ""
    if title:
        title_xml = f"""      <layout-options>
        <title>
          <formatted-text>
            <run fontcolor='{TEXT}' fontname='{FONT_BOLD}' fontsize='14'>{escape(title)}</run>
          </formatted-text>
        </title>
      </layout-options>
"""
    # The first data source listed is the sheet's primary one, so parameters must come last.
    ds_list = "\n".join(f"            <datasource caption={q(CAPTIONS[d])} name='{d}' />" if d in CAPTIONS
                        else f"            <datasource name='{d}' />" for d in view_ds)
    return f"""
    <worksheet name={q(name)}>
{title_xml}      <table>
        <view>
          <datasources>
{ds_list}
          </datasources>
{view}
        </view>
{style}
        <panes>
{panes}
        </panes>
        <rows>{rows}</rows>
        <cols>{cols}</cols>
      </table>
      <simple-id uuid='{simple_id("sheet/" + name)}' />
    </worksheet>"""


def diverging_color_rule(field_ref: str) -> str:
    # The palette itself is defined once in the workbook <preferences> (see palettes()).
    return f"""          <style-rule element='mark'>
            <encoding attr='color' center='0.0' field='{field_ref}' max='1.0' min='-1.0' palette='Thermal Ice to Ember' type='interpolated' />
          </style-rule>
"""


# Category colors as 4-color continuous palettes: codes 1-4 land exactly on each color.
CODE_PALETTES = {
    # Codes 1..4, lowest first. Names are unique so a same-named palette in a user's
    # Preferences.tps (which Tableau prefers over the workbook's) cannot override them.
    "NE Heating Quadrant Codes": [FAINT, ICE, EMBER, "#F2C14E"],  # Low demand, Summer only, Winter only, Year-round
    "NE Heating Pulse Codes": [ICE_DIM, ICE_LIGHT, EMBER_DIM, GOLD],  # Cooling, Cooling (month), Heating, Heating (month)
    "NE Heating HVAC Codes": [FAINT, GOLD],  # 0 = fuel only, 1 = also HVAC service
    "NE Heating Ember Ramp": [EMBER_DIM, EMBER, GOLD],  # low to high
}


def continuous_color_rule(field_ref: str, palette: str, low: float = 1.0, high: float = 4.0) -> str:
    return f"""          <style-rule element='mark'>
            <encoding attr='color' field='{field_ref}' max='{high}' min='{low}' palette='{palette}' type='interpolated' />
          </style-rule>
"""


def palettes() -> str:
    def block(name, kind, colors):
        cs = "\n".join(f"      <color>{c.lower()}</color>" for c in colors)
        return f"    <color-palette name='{name}' type='{kind}'>\n{cs}\n    </color-palette>\n"
    out = block("Thermal Ice to Ember", "ordered-diverging", DIVERGING)
    for name, colors in CODE_PALETTES.items():
        out += block(name, "ordered-sequential", colors)
    return out


def thermal_map() -> str:
    m = MAP
    cols = [
        ("Geometry", "spatial", "measure", "nominal", "Geometry"),
        ("county_key", "string", "dimension", "nominal", "County Key"),
        ("thermal_load", "real", "measure", "quantitative", "Thermal Load"),
        ("heating_gallons", "real", "measure", "quantitative", "Heating Gallons"),
        ("heating_spend", "real", "measure", "quantitative", "Heating Spend"),
        ("cooling_index", "real", "measure", "quantitative", "Cooling Index"),
        ("heating_gal_per_home", "real", "measure", "quantitative", "Heating Gal Per Home"),
        ("hdd", "real", "measure", "quantitative", "Hdd"),
        ("cdd", "real", "measure", "quantitative", "Cdd"),
        ("county_name", "string", "dimension", "nominal", "County Name"),
        ("state_abbr", "string", "dimension", "nominal", "State Abbr"),
        ("month_date", "date", "dimension", "ordinal", "Month Date"),
        ("month_label", "string", "dimension", "nominal", "Month Label"),
        ("Calculation_selected_month", "boolean", "dimension", "nominal", "Selected month",
         MONTH_MATCH),
        ("Calculation_county_label", "string", "dimension", "nominal", "County",
         "REPLACE(REPLACE([county_name], ' Planning Region', ''), ' County', '') + ', ' + [state_abbr]"),
    ]
    inst_list = [
        ("Geometry", "clct", "nk", "nominal"),
        ("county_key", "none", "nk", "nominal"),
        ("thermal_load", "avg", "qk", "quantitative"),
        ("heating_gallons", "sum", "qk", "quantitative"),
        ("heating_spend", "sum", "qk", "quantitative"),
        ("cooling_index", "sum", "qk", "quantitative"),
        ("heating_gal_per_home", "sum", "qk", "quantitative"),
        ("hdd", "sum", "qk", "quantitative"),
        ("cdd", "sum", "qk", "quantitative"),
        ("Calculation_county_label", "attr", "nk", "nominal"),
        ("Calculation_selected_month", "none", "nk", "nominal"),
    ]
    view = "\n".join([
        "          <mapsources>\n            <mapsource name='Tableau' />\n          </mapsources>",
        PARAM_DEPS,
        deps(m, cols, inst_list),
        member_filter(m, "Calculation_selected_month", "nk", "true"),
        f"          <slices>\n            <column>[{m}].[none:Calculation_selected_month:nk]</column>\n          </slices>",
        "          <aggregation value='true' />",
    ])
    # Tableau's "Background Maps > Dark". (Turning the base map off made the polygons render as fragments.)
    style = sheet_style(diverging_color_rule(inst(m, "thermal_load", "avg", "qk")) + """          <style-rule element='map'>
            <format attr='washout' value='0' />
            <format attr='map-style' value='dark' />
          </style-rule>
""")
    tip = tooltip([
        (f"<{inst(m, 'Calculation_county_label', 'attr', 'nk')}>\n", TEXT, True),
        (f"<{inst(m, 'heating_gal_per_home', 'sum', 'qk')}>", GOLD, True),
        (" heating gallons per home this month\n", MUTED, False),
        (f"<{inst(m, 'heating_gallons', 'sum', 'qk')}>", GOLD, False),
        (" gallons in total, $", MUTED, False),
        (f"<{inst(m, 'heating_spend', 'sum', 'qk')}>\n", GOLD, False),
        (f"<{inst(m, 'hdd', 'sum', 'qk')}>", TEXT, False),
        (" heating degree days, ", MUTED, False),
        (f"<{inst(m, 'cdd', 'sum', 'qk')}>", ICE, False),
        (" cooling degree days\n", MUTED, False),
        ("Thermal load ", MUTED, False),
        (f"<{inst(m, 'thermal_load', 'avg', 'qk')}>", TEXT, True),
        ("  (+1 all heating, -1 all cooling)", MUTED, False),
    ])
    panes = f"""          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Automatic' />
            <encodings>
              <color column='{inst(m, "thermal_load", "avg", "qk")}' />
              <lod column='{inst(m, "Geometry", "clct", "nk")}' />
              <lod column='{inst(m, "county_key", "none", "nk")}' />
              <tooltip column='{inst(m, "Calculation_county_label", "attr", "nk")}' />
              <tooltip column='{inst(m, "heating_gal_per_home", "sum", "qk")}' />
              <tooltip column='{inst(m, "heating_gallons", "sum", "qk")}' />
              <tooltip column='{inst(m, "heating_spend", "sum", "qk")}' />
              <tooltip column='{inst(m, "hdd", "sum", "qk")}' />
              <tooltip column='{inst(m, "cdd", "sum", "qk")}' />
              <geometry column='{inst(m, "Geometry", "clct", "nk")}' />
            </encodings>
{tip}
          </pane>"""
    return worksheet("Thermal Map", [m, PARAMS], view, style, panes,
                     f"[{m}].[Latitude (generated)]", f"[{m}].[Longitude (generated)]")


def seasonal_pulse() -> str:
    p = PULSE
    cols = [
        ("heating_season", "string", "dimension", "nominal", "Heating Season"),
        ("month_abbr", "string", "dimension", "nominal", "Month"),
        ("month_order", "integer", "dimension", "ordinal", "Month Order"),
        ("share", "real", "measure", "quantitative", "Share of Season"),
        ("kind", "string", "dimension", "nominal", "Kind"),
        ("month_date", "date", "dimension", "ordinal", "Month Date"),
        ("month_label", "string", "dimension", "nominal", "Month Label"),
        ("Calculation_bar_code", "integer", "measure", "quantitative", "Bar color code",
         f"IF [kind] = 'Cooling' AND {MONTH_MATCH} THEN 2 ELSEIF [kind] = 'Cooling' THEN 1 ELSEIF {MONTH_MATCH} THEN 4 ELSE 3 END"),
    ]
    inst_list = [
        ("heating_season", "none", "nk", "nominal"),
        ("month_abbr", "none", "nk", "nominal"),
        ("share", "sum", "qk", "quantitative"),
        ("kind", "none", "nk", "nominal"),
        ("Calculation_bar_code", "avg", "qk", "quantitative"),
    ]
    view = "\n".join([
        PARAM_DEPS,
        deps(p, cols, inst_list),
        member_filter(p, "heating_season", "nk", f'"{SEASON}"'),
        manual_sort(inst(p, "month_abbr", "none", "nk"), [f"{d:%b}" for d in SEASON_MONTHS]),
        f"          <slices>\n            <column>[{p}].[none:heating_season:nk]</column>\n          </slices>",
        "          <aggregation value='true' />",
    ])
    style = sheet_style(continuous_color_rule(inst(p, "Calculation_bar_code", "avg", "qk"), "NE Heating Pulse Codes") + f"""          <style-rule element='axis'>
            <format attr='display' class='0' field='{inst(p, "share", "sum", "qk")}' scope='rows' value='false' />
          </style-rule>
          <style-rule element='header'>
            <format attr='color' value='{MUTED}' />
            <format attr='font-family' value='{FONT}' />
          </style-rule>
          <style-rule element='label'>
            <format attr='color' value='{MUTED}' />
            <format attr='font-family' value='{FONT}' />
          </style-rule>
""")
    tip = tooltip([
        (f"<{inst(p, 'month_abbr', 'none', 'nk')}> ", TEXT, True),
        (f"<{inst(p, 'kind', 'none', 'nk')}>\n", MUTED, False),
        (f"<{inst(p, 'share', 'sum', 'qk')}>", GOLD, True),
        (" of the season's total", MUTED, False),
    ])
    panes = f"""          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Bar' />
            <encodings>
              <color column='{inst(p, "Calculation_bar_code", "avg", "qk")}' />
              <lod column='{inst(p, "kind", "none", "nk")}' />
            </encodings>
{tip}
            <style>
              <style-rule element='mark'>
                <format attr='size' value='0.75' />
              </style-rule>
            </style>
          </pane>"""
    return worksheet("Seasonal Pulse", [p, PARAMS], view, style, panes,
                     inst(p, "share", "sum", "qk"),
                     inst(p, "month_abbr", "none", "nk"))


def score_columns():
    s = SCORES
    cols = [
        ("county_key", "string", "dimension", "nominal", "County Key"),
        ("heating_pct", "real", "measure", "quantitative", "Heating Percentile"),
        ("cooling_pct", "real", "measure", "quantitative", "Cooling Percentile"),
        ("year_round_score", "real", "measure", "quantitative", "Year-Round Score"),
        ("total_occupied", "integer", "measure", "quantitative", "Homes"),
        ("heating_spend", "real", "measure", "quantitative", "Heating Spend"),
        ("oil_propane_share", "real", "measure", "quantitative", "Oil + Propane Share"),
        ("quadrant", "string", "dimension", "nominal", "Quadrant"),
        ("label", "string", "dimension", "nominal", "Label"),
        ("Calculation_basis_match", "boolean", "dimension", "nominal", "Basis matches",
         f"[basis] = [Parameters].{P_BASIS}"),
        ("Calculation_top_12", "boolean", "dimension", "nominal", "Top 12", "[year_round_rank] <= 12"),
        ("Calculation_quadrant_code", "integer", "measure", "quantitative", "Quadrant color code", "CASE [quadrant] WHEN 'Low demand' THEN 1 WHEN 'Summer only' THEN 2 WHEN 'Winter only' THEN 3 ELSE 4 END"),
        ("Calculation_score_100", "string", "dimension", "nominal", "Score (0-100)",
         "STR(INT(ROUND([year_round_score] * 100, 0)))"),
        ("Calculation_county_label", "string", "dimension", "nominal", "County",
         "REPLACE(REPLACE([county_name], ' Planning Region', ''), ' County', '') + ', ' + [state_abbr]"),
        ("basis", "string", "dimension", "nominal", "Basis"),
        ("year_round_rank", "integer", "measure", "quantitative", "Year-Round Rank"),
        ("county_name", "string", "dimension", "nominal", "County Name"),
        ("state_abbr", "string", "dimension", "nominal", "State"),
    ]
    return s, cols


def score_tooltip(s):
    return tooltip([
        (f"<{inst(s, 'Calculation_county_label', 'attr', 'nk')}>\n", TEXT, True),
        (f"<{inst(s, 'quadrant', 'attr', 'nk')}>", GOLD, True),
        ("  score ", MUTED, False),
        (f"<{inst(s, 'year_round_score', 'sum', 'qk')}>\n", TEXT, False),
        ("Heating spend: $", MUTED, False),
        (f"<{inst(s, 'heating_spend', 'sum', 'qk')}>\n", GOLD, False),
        ("Homes on oil or propane: ", MUTED, False),
        (f"<{inst(s, 'oil_propane_share', 'sum', 'qk')}>", TEXT, False),
    ])


def scatter() -> str:
    s, cols = score_columns()
    inst_list = [
        ("county_key", "none", "nk", "nominal"),
        ("heating_pct", "sum", "qk", "quantitative"),
        ("cooling_pct", "sum", "qk", "quantitative"),
        ("year_round_score", "sum", "qk", "quantitative"),
        ("total_occupied", "sum", "qk", "quantitative"),
        ("heating_spend", "sum", "qk", "quantitative"),
        ("oil_propane_share", "sum", "qk", "quantitative"),
        ("quadrant", "attr", "nk", "nominal"),
        ("quadrant", "none", "nk", "nominal"),
        ("Calculation_quadrant_code", "avg", "qk", "quantitative"),
        ("Calculation_score_100", "attr", "nk", "nominal"),
        ("label", "attr", "nk", "nominal"),
        ("Calculation_county_label", "attr", "nk", "nominal"),
        ("Calculation_basis_match", "none", "nk", "nominal"),
    ]
    view = "\n".join([
        PARAM_DEPS,
        deps(s, cols, inst_list),
        member_filter(s, "Calculation_basis_match", "nk", "true"),
        f"          <slices>\n            <column>[{s}].[none:Calculation_basis_match:nk]</column>\n          </slices>",
        "          <aggregation value='true' />",
    ])
    style = sheet_style(continuous_color_rule(inst(s, "Calculation_quadrant_code", "avg", "qk"), "NE Heating Quadrant Codes") + f"""          <style-rule element='axis'>
            <format attr='color' value='{MUTED}' />
            <format attr='tick-color' value='{FAINT}' />
            <format attr='title' class='0' field='{inst(s, "heating_pct", "sum", "qk")}' scope='cols' value='Winter heating spend, percentile  →' />
            <format attr='title' class='0' field='{inst(s, "cooling_pct", "sum", "qk")}' scope='rows' value='Summer cooling, percentile  →' />
            <encoding attr='space' class='0' field='{inst(s, "heating_pct", "sum", "qk")}' field-type='quantitative' max='1.02' min='-0.02' range-type='fixed' scope='cols' type='space' />
            <encoding attr='space' class='0' field='{inst(s, "cooling_pct", "sum", "qk")}' field-type='quantitative' max='1.02' min='-0.02' range-type='fixed' scope='rows' type='space' />
          </style-rule>
          <style-rule element='refline'>
            <format attr='stroke-color' value='{FAINT}' />
          </style-rule>
          <style-rule element='label'>
            <format attr='color' value='{TEXT}' />
            <format attr='font-family' value='{FONT}' />
            <format attr='font-size' value='9' />
          </style-rule>
""")
    panes = f"""          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Circle' />
            <encodings>
              <color column='{inst(s, "Calculation_quadrant_code", "avg", "qk")}' />
              <size column='{inst(s, "total_occupied", "sum", "qk")}' />
              <lod column='{inst(s, "county_key", "none", "nk")}' />
              <text column='{inst(s, "label", "attr", "nk")}' />
              <tooltip column='{inst(s, "Calculation_county_label", "attr", "nk")}' />
              <tooltip column='{inst(s, "year_round_score", "sum", "qk")}' />
              <tooltip column='{inst(s, "heating_spend", "sum", "qk")}' />
              <tooltip column='{inst(s, "oil_propane_share", "sum", "qk")}' />
            </encodings>
{score_tooltip(s)}
            <style>
              <style-rule element='mark'>
                <format attr='mark-labels-show' value='true' />
                <format attr='mark-labels-cull' value='true' />
                <format attr='has-stroke' value='true' />
                <format attr='stroke-color' value='{BG}' />
                <format attr='mark-transparency' value='220' />
              </style-rule>
            </style>
          </pane>"""
    return worksheet("Year-Round Scatter", [s, PARAMS], view, style, panes,
                     inst(s, "cooling_pct", "sum", "qk"), inst(s, "heating_pct", "sum", "qk"))


def bar_style(axis_field: str, label_color: str, extra: str = "", header_field: str = "", width: int = 0) -> str:
    """Horizontal bar sheet: hidden value axis, readable row headers and labels."""
    header_width = (f"\n            <format attr='width' field='{header_field}' value='{width}' />"
                    if header_field else "")
    return sheet_style(extra + f"""          <style-rule element='axis'>
            <format attr='display' class='0' field='{axis_field}' scope='cols' value='false' />
          </style-rule>
          <style-rule element='header'>{header_width}
            <format attr='color' value='{TEXT}' />
            <format attr='font-family' value='{FONT}' />
            <format attr='font-size' value='10' />
          </style-rule>
          <style-rule element='label'>
            <format attr='color' value='{label_color}' />
            <format attr='font-size' value='9' />
          </style-rule>
""")


def ct_region_density() -> str:
    r = CT_REGIONS
    cols = [
        ("region", "string", "dimension", "nominal", "Region"),
        ("homes_per_dealer", "real", "measure", "quantitative", "Homes per Dealer"),
        ("dealers", "integer", "measure", "quantitative", "Dealers"),
        ("pct_full_service", "real", "measure", "quantitative", "% Full-Service"),
        ("spend_per_dealer_musd", "real", "measure", "quantitative", "Spend per Dealer ($M)"),
    ]
    insts = [("region", "none", "nk", "nominal"), ("homes_per_dealer", "sum", "qk", "quantitative"),
             ("dealers", "sum", "qk", "quantitative"), ("pct_full_service", "sum", "qk", "quantitative"),
             ("spend_per_dealer_musd", "sum", "qk", "quantitative")]
    region_ref, value_ref = inst(r, "region", "none", "nk"), inst(r, "homes_per_dealer", "sum", "qk")
    view = "\n".join([
        deps(r, cols, insts),
        f"          <sort class='computed' column='{region_ref}' direction='DESC' using='{value_ref}' />",
        "          <aggregation value='true' />",
    ])
    style = bar_style(value_ref, GOLD, continuous_color_rule(value_ref, "NE Heating Ember Ramp", 900.0, 2250.0),
                      region_ref, 190)
    tip = tooltip([
        (f"<{region_ref}>\n", TEXT, True),
        (f"<{value_ref}>", GOLD, True), (" oil and propane homes per dealer\n", MUTED, False),
        (f"<{inst(r, 'dealers', 'sum', 'qk')}>", TEXT, False), (" dealers, ", MUTED, False),
        (f"<{inst(r, 'pct_full_service', 'sum', 'qk')}>", TEXT, False), ("% also do HVAC\n", MUTED, False),
        ("$", MUTED, False), (f"<{inst(r, 'spend_per_dealer_musd', 'sum', 'qk')}>", GOLD, False),
        ("M of yearly heating spend per dealer", MUTED, False),
    ])
    panes = f"""          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Bar' />
            <encodings>
              <color column='{value_ref}' />
              <text column='{value_ref}' />
              <tooltip column='{inst(r, "dealers", "sum", "qk")}' />
              <tooltip column='{inst(r, "pct_full_service", "sum", "qk")}' />
              <tooltip column='{inst(r, "spend_per_dealer_musd", "sum", "qk")}' />
            </encodings>
{tip}
            <style>
              <style-rule element='mark'>
                <format attr='mark-labels-show' value='true' />
                <format attr='size' value='0.6' />
              </style-rule>
            </style>
          </pane>"""
    return worksheet("CT Region Density", [r], view, style, panes, region_ref, value_ref)


def ct_prospects() -> str:
    c = CT_PROSPECTS
    cols = CT_PROSPECT_COLS + [("Calculation_top_15", "boolean", "dimension", "nominal", "Top 15", "[prospect_rank] <= 15"),
                               ("Calculation_fit_label", "string", "dimension", "nominal", "Fit score label", "STR(ROUND([fit_score], 1))")]
    insts = [("label", "none", "nk", "nominal"), ("fit_score", "sum", "qk", "quantitative"),
             ("prospect_rank", "sum", "qk", "quantitative"), ("offers_hvac_service", "avg", "qk", "quantitative"),
             ("region", "attr", "nk", "nominal"), ("years_licensed", "sum", "qk", "quantitative"),
             ("region_homes_per_dealer", "sum", "qk", "quantitative"), ("Calculation_top_15", "none", "nk", "nominal"),
             ("Calculation_fit_label", "attr", "nk", "nominal")]
    label_ref, score_ref = inst(c, "label", "none", "nk"), inst(c, "fit_score", "sum", "qk")
    view = "\n".join([
        deps(c, cols, insts),
        member_filter(c, "Calculation_top_15", "nk", "true"),
        f"          <sort class='computed' column='{label_ref}' direction='ASC' using='{inst(c, 'prospect_rank', 'sum', 'qk')}' />",
        f"          <slices>\n            <column>[{c}].[none:Calculation_top_15:nk]</column>\n          </slices>",
        "          <aggregation value='true' />",
    ])
    hvac_ref = inst(c, "offers_hvac_service", "avg", "qk")
    style = bar_style(score_ref, MUTED, continuous_color_rule(hvac_ref, "NE Heating HVAC Codes", 0.0, 1.0) + f"""          <style-rule element='axis'>
            <encoding attr='space' class='0' field='{score_ref}' field-type='quantitative' max='110' min='0' range-type='fixed' scope='cols' type='space' />
          </style-rule>
""", label_ref, 290)
    tip = tooltip([
        (f"<{label_ref}>\n", TEXT, True),
        (f"<{inst(c, 'region', 'attr', 'nk')}>\n", MUTED, False),
        ("Fit score ", MUTED, False), (f"<{score_ref}>\n", GOLD, True),
        ("Licensed ", MUTED, False), (f"<{inst(c, 'years_licensed', 'sum', 'qk')}>", TEXT, False),
        (" years. Region: ", MUTED, False), (f"<{inst(c, 'region_homes_per_dealer', 'sum', 'qk')}>", TEXT, False),
        (" homes per dealer", MUTED, False),
    ])
    panes = f"""          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Bar' />
            <encodings>
              <color column='{hvac_ref}' />
              <text column='{inst(c, "Calculation_fit_label", "attr", "nk")}' />
              <tooltip column='{inst(c, "region", "attr", "nk")}' />
              <tooltip column='{inst(c, "years_licensed", "sum", "qk")}' />
              <tooltip column='{inst(c, "region_homes_per_dealer", "sum", "qk")}' />
            </encodings>
{tip}
            <style>
              <style-rule element='mark'>
                <format attr='mark-labels-show' value='true' />
                <format attr='size' value='0.6' />
              </style-rule>
            </style>
          </pane>"""
    return worksheet("CT Prospects", [c], view, style, panes, label_ref, score_ref)


def top_markets() -> str:
    s, cols = score_columns()
    inst_list = [
        ("Calculation_county_label", "none", "nk", "nominal"),
        ("Calculation_county_label", "attr", "nk", "nominal"),
        ("year_round_score", "sum", "qk", "quantitative"),
        ("heating_spend", "sum", "qk", "quantitative"),
        ("oil_propane_share", "sum", "qk", "quantitative"),
        ("quadrant", "attr", "nk", "nominal"),
        ("quadrant", "none", "nk", "nominal"),
        ("Calculation_quadrant_code", "avg", "qk", "quantitative"),
        ("Calculation_score_100", "attr", "nk", "nominal"),
        ("Calculation_basis_match", "none", "nk", "nominal"),
        ("Calculation_top_12", "none", "nk", "nominal"),
    ]
    label_ref = inst(s, "Calculation_county_label", "none", "nk")
    score_ref = inst(s, "year_round_score", "sum", "qk")
    view = "\n".join([
        PARAM_DEPS,
        deps(s, cols, inst_list),
        member_filter(s, "Calculation_basis_match", "nk", "true"),
        member_filter(s, "Calculation_top_12", "nk", "true"),
        f"          <sort class='computed' column='{label_ref}' direction='DESC' using='{score_ref}' />",
        f"          <slices>\n            <column>[{s}].[none:Calculation_basis_match:nk]</column>\n"
        f"            <column>[{s}].[none:Calculation_top_12:nk]</column>\n          </slices>",
        "          <aggregation value='true' />",
    ])
    style = sheet_style(continuous_color_rule(inst(s, "Calculation_quadrant_code", "avg", "qk"), "NE Heating Quadrant Codes") + f"""          <style-rule element='axis'>
            <format attr='display' class='0' field='{score_ref}' scope='cols' value='false' />
            <encoding attr='space' class='0' field='{score_ref}' field-type='quantitative' max='1.1' min='0' range-type='fixed' scope='cols' type='space' />
          </style-rule>
          <style-rule element='header'>
            <format attr='color' value='{TEXT}' />
            <format attr='font-family' value='{FONT}' />
            <format attr='font-size' value='10' />
          </style-rule>
          <style-rule element='label'>
            <format attr='color' value='{MUTED}' />
            <format attr='font-size' value='9' />
          </style-rule>
""")
    panes = f"""          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='Bar' />
            <encodings>
              <color column='{inst(s, "Calculation_quadrant_code", "avg", "qk")}' />
              <text column='{inst(s, "Calculation_score_100", "attr", "nk")}' />
              <tooltip column='{inst(s, "heating_spend", "sum", "qk")}' />
              <tooltip column='{inst(s, "oil_propane_share", "sum", "qk")}' />
            </encodings>
{score_tooltip(s)}
            <style>
              <style-rule element='mark'>
                <format attr='mark-labels-show' value='true' />
                <format attr='size' value='0.6' />
              </style-rule>
            </style>
          </pane>"""
    return worksheet("Top Markets", [s, PARAMS], view, style, panes, label_ref, score_ref)


# Dashboards ---------------------------------------------------------------------
# A layout is a tree: ("v" | "h", [(weight, child), ...]) for tiled containers, or a leaf
# dict. Positions are in Tableau's dashboard units (the whole dashboard is 100000 x 100000).

SERIF = "Georgia"
SOURCE_LINE = ("Sources: Census ACS 2020-24, NOAA nClimDiv, EIA RECS 2020, SHOPP and SEDS. Modeled estimates, "
               "not metered gallons.   Dhruv Khanna  ·  github.com/dhruvk1310-lang/northeast-heating-demand-map")


class Zones:
    def __init__(self):
        self.next_id = 2

    def new_id(self) -> int:
        self.next_id += 1
        return self.next_id


def zone_style(margin=4, background=None) -> str:
    bg = f"\n            <format attr='background-color' value='{background}' />" if background else ""
    return f"""          <zone-style>
            <format attr='border-color' value='#000000' />
            <format attr='border-style' value='none' />
            <format attr='border-width' value='0' />
            <format attr='margin' value='{margin}' />{bg}
          </zone-style>"""


def runs_xml(runs: list[tuple]) -> str:
    """runs: (text, color, font, size) or "\\n" for a line break."""
    out = []
    for r in runs:
        if r == "\n":
            out.append("              <run>Æ&#10;</run>")
        else:
            text, color, font, size = r
            out.append(f"              <run fontcolor='{color}' fontname='{font}' fontsize='{size}'>{escape(text)}</run>")
    return "\n".join(out)


def render(node, x, y, w, h, z: Zones) -> str:
    pos = f"h='{h}' id='{z.new_id()}' w='{w}' x='{x}' y='{y}'"
    if isinstance(node, tuple):
        direction, children = node
        total = sum(weight for weight, _ in children)
        parts, offset = [], 0
        for i, (weight, child) in enumerate(children):
            span = (w if direction == "h" else h) * weight // total
            if i == len(children) - 1:
                span = (w if direction == "h" else h) - offset
            cx, cy = (x + offset, y) if direction == "h" else (x, y + offset)
            cw, ch = (span, h) if direction == "h" else (w, span)
            parts.append(render(child, cx, cy, cw, ch, z))
            offset += span
        param = "horz" if direction == "h" else "vert"
        inner = "\n".join(parts)
        return f"        <zone {pos} param='{param}' type-v2='layout-flow'>\n{inner}\n{zone_style(0)}\n        </zone>"
    kind = node["kind"]
    bg = node.get("background")
    margin = node.get("margin", 6)
    if kind == "sheet":
        return f"        <zone {pos} name={q(node['name'])} show-title='false'>\n{zone_style(margin, bg)}\n        </zone>"
    if kind == "text":
        return (f"        <zone {pos} type-v2='text'>\n            <formatted-text>\n{runs_xml(node['runs'])}\n"
                f"            </formatted-text>\n{zone_style(margin, bg)}\n        </zone>")
    if kind == "param":
        mode = f" mode='{node['mode']}'" if node.get("mode") else ""
        return (f"        <zone {pos}{mode} param='[Parameters].{node['param']}' type-v2='paramctrl'>\n"
                f"{zone_style(margin, bg)}\n        </zone>")
    if kind == "legend":
        return (f"        <zone {pos} name={q(node['sheet'])} pane-specification-id='0' param='{node['field']}' "
                f"type-v2='color'>\n{zone_style(margin, bg)}\n        </zone>")
    if kind == "blank":
        return f"        <zone {pos} type-v2='empty'>\n{zone_style(0, bg)}\n        </zone>"
    raise ValueError(kind)


def dashboard(name: str, tree, width=1400, height=900) -> str:
    z = Zones()
    body = render(tree, 0, 0, 100000, 100000, z)
    return f"""
    <dashboard name={q(name)}>
      <style>
        <style-rule element='table'>
          <format attr='background-color' value='{BG}' />
        </style-rule>
      </style>
      <size maxheight='{height}' maxwidth='{width}' minheight='{height}' minwidth='{width}' />
      <zones>
        <zone h='100000' id='1' type-v2='layout-basic' w='100000' x='0' y='0'>
{body}
{zone_style(0)}
        </zone>
      </zones>
      <simple-id uuid='{simple_id("dashboard/" + name)}' />
    </dashboard>"""


def header(kicker, title, subtitle) -> dict:
    return {"kind": "text", "margin": 14, "runs": [
        (kicker, EMBER, FONT_BOLD, 10), "\n",
        (title, TEXT, SERIF, 30), "\n",
        (subtitle, MUTED, FONT, 12),
    ]}


def footer() -> dict:
    return {"kind": "text", "margin": 10, "runs": [(SOURCE_LINE, FAINT, FONT, 9)]}


def kpi_tiles() -> list[dict]:
    """Headline numbers as static text tiles, read from kpis.csv for the dashboard's season."""
    k = pd.read_csv(DATA / "kpis.csv")
    k = k[k["heating_season"] == SEASON].sort_values("kpi_order")
    return [{"kind": "text", "margin": 10, "background": PANEL, "runs": [
        (r.kpi_value, GOLD, FONT_BOLD, 26), "\n", (r.kpi_label, MUTED, FONT, 11)]} for r in k.itertuples()]


def thermal_year_dashboard() -> str:
    explainer = {"kind": "text", "margin": 14, "background": PANEL, "runs": [
        ("HOW TO READ IT", EMBER, FONT_BOLD, 10), "\n", "\n",
        ("Thermal load", TEXT, FONT_BOLD, 13), "\n",
        ("Each county's heating gallons per home, minus its cooling demand per home, that month. "
         "+1 is all heating, -1 is all cooling.", MUTED, FONT, 11), "\n", "\n",
        ("Ember counties", GOLD, FONT_BOLD, 12), "\n",
        ("Burn the most oil and propane: the winter delivery market.", MUTED, FONT, 11), "\n", "\n",
        ("Ice counties", ICE, FONT_BOLD, 12), "\n",
        ("Need the most AC: summer service work for full-service dealers.", MUTED, FONT, 11),
    ]}
    pulse_title = {"kind": "text", "margin": 4, "runs": [
        ("SEASONAL PULSE", EMBER, FONT_BOLD, 10),
        ("   Each month's share of the season's heating (up) and cooling (down). The bright bar is the month on the map.",
         MUTED, FONT, 11),
    ]}
    tree = ("v", [
        (13, ("h", [
            (70, header("NORTHEAST HEATING & COOLING DEMAND  ·  2025-26 SEASON", "The Thermal Year",
                        "Where the Northeast burns heating oil and propane, and where it runs the AC, county by county.")),
            (30, {"kind": "param", "param": P_MONTH, "mode": "slider", "margin": 18}),
        ])),
        (9, ("h", [(1, tile) for tile in kpi_tiles()])),
        (50, ("h", [
            (74, {"kind": "sheet", "name": "Thermal Map", "margin": 2}),
            (26, ("v", [
                (18, {"kind": "legend", "sheet": "Thermal Map", "field": inst(MAP, "thermal_load", "avg", "qk"),
                      "background": PANEL}),
                (82, explainer),
            ])),
        ])),
        (3, pulse_title),
        (21, {"kind": "sheet", "name": "Seasonal Pulse"}),
        (4, footer()),
    ])
    return dashboard("The Thermal Year", tree)


def year_round_dashboard() -> str:
    side_title = {"kind": "text", "margin": 8, "runs": [
        ("TOP 12 MARKETS", EMBER, FONT_BOLD, 10), "\n",
        ("Year-round score = 60% heating spend percentile + 40% cooling percentile", MUTED, FONT, 10),
    ]}
    insight = {"kind": "text", "margin": 12, "background": PANEL, "runs": [
        ("WHAT IT SHOWS", EMBER, FONT_BOLD, 10), "\n",
        ("By total, ", MUTED, FONT, 11), ("the big New York City and Boston counties", TEXT, FONT_BOLD, 11),
        (" lead: both heating and cooling grow with the number of homes.", MUTED, FONT, 11), "\n",
        ("Per home, ", MUTED, FONT, 11), ("oil-heavy towns outside the cities", GOLD, FONT_BOLD, 11),
        (" with warm summers lead, like Sussex NJ, Northeastern Connecticut and Putnam NY: "
         "the best fit for a full-service dealer.", MUTED, FONT, 11),
    ]}
    tree = ("v", [
        (15, ("h", [
            (72, header("WHERE THE YEAR-ROUND MONEY IS  ·  218 COUNTIES", "Size vs. intensity",
                        "Full-service dealers sell fuel in winter and AC service in summer. Rank counties by total "
                        "market or per home: the winners change almost completely.")),
            (28, {"kind": "param", "param": P_BASIS, "margin": 18}),
        ])),
        (80, ("h", [
            (60, {"kind": "sheet", "name": "Year-Round Scatter"}),
            (40, ("v", [
                (8, side_title),
                (50, {"kind": "sheet", "name": "Top Markets"}),
                (16, {"kind": "text", "margin": 12, "background": PANEL, "runs": [
                    ("QUADRANT", EMBER, FONT_BOLD, 10), "\n",
                    ("■ ", QUADRANTS["Year-round"], FONT, 13), ("Year-round   ", TEXT, FONT, 11),
                    ("■ ", QUADRANTS["Winter only"], FONT, 13), ("Winter only   ", TEXT, FONT, 11),
                    ("■ ", QUADRANTS["Summer only"], FONT, 13), ("Summer only   ", TEXT, FONT, 11),
                    ("■ ", QUADRANTS["Low demand"], FONT, 13), ("Low demand", TEXT, FONT, 11), "\n",
                    ("Split at the 50th percentile on each axis. Bubble size = homes.", MUTED, FONT, 10),
                ]}),
                (26, insight),
            ])),
        ])),
        (5, footer()),
    ])
    return dashboard("Where the Year-Round Money Is", tree)


def ct_dashboard() -> str:
    regions = pd.read_csv(DATA / "ct_regions.csv")
    prospects = pd.read_csv(DATA / "ct_prospects.csv")
    top, low = regions.iloc[0], regions.iloc[-1]
    full_service = prospects["offers_hvac_service"].mean()
    tiles = [
        (f"{len(prospects)}", "licensed heating fuel dealers in Connecticut"),
        (f"{full_service:.0%}", "also licensed for HVAC: full-service"),
        (f"{top.homes_per_dealer:,.0f}", f"homes per dealer in {top.region}, the most under-served"),
        (f"{low.homes_per_dealer:,.0f}", f"homes per dealer in {low.region}"),
    ]
    tile_nodes = [{"kind": "text", "margin": 10, "background": PANEL, "runs": [
        (value, GOLD, FONT_BOLD, 26), "\n", (label, MUTED, FONT, 11)]} for value, label in tiles]
    method = {"kind": "text", "margin": 12, "background": PANEL, "runs": [
        ("HOW DEALERS ARE SCORED", EMBER, FONT_BOLD, 10), "\n",
        ("Fit score = 50% offers HVAC service + 30% how under-served its region is (homes per dealer) "
         "+ 20% years licensed. ", MUTED, FONT, 11),
        ("Full-service dealers in crowded-out regions are the best fit for a dispatch, routing and service platform. ",
         TEXT, FONT, 11), "\n",
        ("■ ", GOLD, FONT, 13), ("Also does HVAC   ", TEXT, FONT, 11),
        ("■ ", FAINT, FONT, 13), ("Fuel only", TEXT, FONT, 11),
    ]}
    left_title = {"kind": "text", "margin": 8, "runs": [
        ("HOMES PER DEALER", EMBER, FONT_BOLD, 10), "\n",
        ("Oil and propane homes per licensed dealer, by planning region", MUTED, FONT, 10)]}
    right_title = {"kind": "text", "margin": 8, "runs": [
        ("TOP 15 PROSPECTS", EMBER, FONT_BOLD, 10), "\n",
        ("Ranked by fit score, out of 100", MUTED, FONT, 10)]}
    source = {"kind": "text", "margin": 10, "runs": [(
        "Sources: Connecticut Department of Consumer Protection license registry (data.ct.gov), Census ACS 2020-24. "
        "Dealers are placed in planning regions by ZIP code.   Dhruv Khanna  ·  "
        "github.com/dhruvk1310-lang/northeast-heating-demand-map", FAINT, FONT, 9)]}
    tree = ("v", [
        (13, header("CONNECTICUT PILOT  ·  468 DEALERS, 9 PLANNING REGIONS", "Who to call first",
                    "Every licensed heating fuel dealer in Connecticut, matched to HVAC contractor licenses and "
                    "to the oil and propane homes around them.")),
        (10, ("h", [(1, t) for t in tile_nodes])),
        (64, ("h", [
            (44, ("v", [(9, left_title), (91, {"kind": "sheet", "name": "CT Region Density"})])),
            (56, ("v", [(9, right_title), (91, {"kind": "sheet", "name": "CT Prospects"})])),
        ])),
        (9, method),
        (4, source),
    ])
    return dashboard("Connecticut Dealer Prospects", tree)


def dashboard_window(name: str, sheets: list[str]) -> str:
    vps = "\n".join(f"        <viewpoint name={q(s)} />" for s in sheets)
    return f"""    <window class='dashboard' maximized='true' name={q(name)}>
      <viewpoints>
{vps}
      </viewpoints>
      <active id='-1' />
      <simple-id uuid='{simple_id("window/" + name)}' />
    </window>"""


WORKBOOK_STYLE = f"""  <style>
    <style-rule element='all'>
      <format attr='font-family' value='{FONT}' />
    </style-rule>
    <style-rule element='parameter-ctrl-title'>
      <format attr='color' value='{TEXT}' />
      <format attr='font-family' value='{FONT_BOLD}' />
    </style-rule>
    <style-rule element='parameter-ctrl'>
      <format attr='color' value='{BG}' />
    </style-rule>
    <style-rule element='legend-title'>
      <format attr='color' value='{TEXT}' />
      <format attr='font-family' value='{FONT_BOLD}' />
    </style-rule>
    <style-rule element='legend'>
      <format attr='color' value='{MUTED}' />
      <format attr='background-color' value='{PANEL}' />
    </style-rule>
  </style>"""


# Workbook -----------------------------------------------------------------------

def sheet_window(name: str) -> str:
    return (f"    <window class='worksheet' name={q(name)}>\n      <cards>\n        <edge name='left'>\n"
            f"          <strip size='160'>\n            <card type='pages' />\n            <card type='filters' />\n"
            f"            <card type='marks' />\n          </strip>\n        </edge>\n        <edge name='top'>\n"
            f"          <strip size='2147483647'>\n            <card type='columns' />\n          </strip>\n"
            f"          <strip size='2147483647'>\n            <card type='rows' />\n          </strip>\n"
            f"        </edge>\n      </cards>\n      <simple-id uuid='{simple_id('window/' + name)}' />\n    </window>")


def workbook(dashboards: str = "", windows: str = "") -> str:
    sheets = [thermal_map(), seasonal_pulse(), scatter(), top_markets(), ct_region_density(), ct_prospects()]
    names = ["Thermal Map", "Seasonal Pulse", "Year-Round Scatter", "Top Markets", "CT Region Density", "CT Prospects"]
    window_xml = windows or "\n".join(sheet_window(n) for n in names)
    body = f"""  <datasources>{parameters()}
{map_datasource()}{pulse_datasource()}{scores_datasource()}{ct_regions_datasource()}{ct_prospects_datasource()}
  </datasources>
  <mapsources>
    <mapsource name='Tableau' />
  </mapsources>
  <worksheets>{''.join(sheets)}
  </worksheets>{dashboards}"""
    return f"""<?xml version='1.0' encoding='utf-8' ?>

<workbook original-version='18.1' source-build='2025.3.1 (20253.25.1210.1815)' source-platform='mac' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest>
    <AnimationOnByDefault />
    <MapboxVectorStylesAndLayers />
    <MarkAnimation />
    <ObjectModelEncapsulateLegacy />
    <ObjectModelExtractV2 />
    <ObjectModelTableType />
    <SchemaViewerObjectModel />
    <SheetIdentifierTracking />
    <SpatialFileLayer />
    <WindowsPersistSimpleIdentifiers />
  </document-format-change-manifest>
  <preferences>
    <preference name='ui.encoding.shelf.height' value='24' />
    <preference name='ui.shelf.height' value='26' />
{palettes()}  </preferences>
{WORKBOOK_STYLE}
{body}
  <windows source-height='30'>
{window_xml}
  </windows>
</workbook>
"""


def main() -> None:
    dashboards = (f"\n  <dashboards>{thermal_year_dashboard()}{year_round_dashboard()}{ct_dashboard()}"
                  "\n  </dashboards>")
    names = ["Thermal Map", "Seasonal Pulse", "Year-Round Scatter", "Top Markets", "CT Region Density", "CT Prospects"]
    windows = "\n".join([sheet_window(n) for n in names] + [
        dashboard_window("The Thermal Year", ["Seasonal Pulse", "Thermal Map"]),
        dashboard_window("Where the Year-Round Money Is", ["Top Markets", "Year-Round Scatter"]),
        dashboard_window("Connecticut Dealer Prospects", ["CT Prospects", "CT Region Density"]),
    ])
    OUT.write_text(workbook(dashboards, windows))
    print(f"  wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
