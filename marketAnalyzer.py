import os
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# =====================================================
# LOAD DATA (SAFE PATHS FOR DEPLOYMENT)
# =====================================================
BASE_DIR = os.path.dirname(__file__)

EV_FILE = os.path.join(BASE_DIR, "eCleaned.csv")
ICE_FILE = os.path.join(BASE_DIR, "iceCleaned.csv")

ev = pd.read_csv(EV_FILE)
ice = pd.read_csv(ICE_FILE)

# =====================================================
# CLEAN COLUMNS
# =====================================================
for df in [ev, ice]:
    df.columns = df.columns.str.strip().str.lower().str.replace("\xa0", "")
    df["make"] = df["make"].astype(str).str.strip().str.title()

# =====================================================
# CONSTANTS
# =====================================================
BRANDS_ROW1 = ["Ford","Chevrolet","Toyota","Honda","Nissan","Jeep","Hyundai"]
BRANDS_ROW2 = ["Kia","Subaru","GMC","Ram","Volkswagen","Mazda","Dodge"]
BRANDS_ALL = BRANDS_ROW1 + BRANDS_ROW2

default_elec_rate = 0.15
default_gas_price = 3.84
default_diesel_price = 4.25
gCO2grid_default = 324

# =====================================================
# CALCULATION FUNCTION
# =====================================================
def calculate(df, vtype, gas, diesel, elec):
    df = df.copy()

    if vtype == "ICE":
        df["fuel_category"] = df["fueltype"].apply(
            lambda x: "Diesel" if str(x).lower() == "diesel" else "Gasoline"
        )
        df["cost_per_mile"] = df.apply(
            lambda r: (diesel if r["fuel_category"] == "Diesel" else gas) / r["comb"],
            axis=1
        )
        df["co2_per_mile"] = df["co2"]

    else:
        df["fuel_category"] = "EV"
        kwh_col = "kwhpmcomb" if "kwhpmcomb" in df.columns else "combe"
        df["cost_per_mile"] = df[kwh_col] * elec
        df["co2_per_mile"] = df[kwh_col] * gCO2grid_default

    df["vehicle_name"] = (
        df["year"].astype(str) + " " + df["make"] + " " + df["model"]
    )

    return df

# =====================================================
# DASH APP
# =====================================================
app = dash.Dash(__name__)
server = app.server  # ✅ REQUIRED FOR DEPLOYMENT
app.title = "Vehicle Impact"

# =====================================================
# LAYOUT
# =====================================================
app.layout = html.Div([
    html.Div([
        html.H2("Vehicle Impact"),
        html.H3("$ Cost and CO₂ per mile"),
    ]),

    dcc.RangeSlider(
        id="year-filter",
        min=2017,
        max=2026,
        step=1,
        value=[2017, 2026],
        marks={y: str(y) for y in range(2017, 2027)},
        allowCross=False
    ),

    dcc.Graph(id="graph"),

    html.Div([

        html.Div([
            html.H4("Prospective Vehicle Purchase"),

            dcc.RadioItems(
                id="p-type",
                options=[
                    {"label": "ICE/Hybrid", "value": "ICE"},
                    {"label": "EV", "value": "EV"}
                ],
                value="ICE",
                inline=True
            ),

            dcc.Dropdown(id="p-year"),
            dcc.Dropdown(id="p-make"),
            dcc.Dropdown(id="p-model"),
            dcc.Dropdown(id="p-displ"),

        ], style={"width": "45%"}),

        html.Div([
            html.H4("Fuel Prices"),

            html.Label("Gas"),
            dcc.Input(id="gas", type="number", value=default_gas_price),

            html.Label("Diesel"),
            dcc.Input(id="diesel", type="number", value=default_diesel_price),

            html.Label("Electric"),
            dcc.Input(id="elec", type="number", value=default_elec_rate),

        ], style={"width": "45%"})

    ], style={"display": "flex", "justify-content": "space-between"}),

], style={"padding": "15px"})

# =====================================================
# DROPDOWNS
# =====================================================
@app.callback(Output("p-year", "options"), Input("p-type", "value"))
def set_years(vtype):
    df = ev if vtype == "EV" else ice
    df = df[df["year"].isin([2025, 2026])]
    return [{"label": int(y), "value": int(y)} for y in sorted(df["year"].unique())]


@app.callback(Output("p-make", "options"),
              Input("p-year", "value"),
              Input("p-type", "value"))
def set_make(year, vtype):
    if year is None:
        return []
    df = ev if vtype == "EV" else ice
    df = df[df["year"] == year]
    return [{"label": m, "value": m} for m in sorted(df["make"].unique())]


@app.callback(Output("p-model", "options"),
              Input("p-year", "value"),
              Input("p-make", "value"),
              Input("p-type", "value"))
def set_model(year, make, vtype):
    if None in [year, make]:
        return []
    df = ev if vtype == "EV" else ice
    df = df[(df["year"] == year) & (df["make"] == make)]
    return [{"label": m, "value": m} for m in sorted(df["model"].unique())]


@app.callback(Output("p-displ", "options"),
              Input("p-year", "value"),
              Input("p-make", "value"),
              Input("p-model", "value"),
              Input("p-type", "value"))
def set_displ(year, make, model, vtype):
    if None in [year, make, model]:
        return []
    df = ev if vtype == "EV" else ice
    df = df[(df["year"] == year) &
            (df["make"] == make) &
            (df["model"] == model)]

    if "displ" in df.columns:
        return [{"label": str(d), "value": d} for d in sorted(df["displ"].dropna().unique())]

    return []

# =====================================================
# GRAPH
# =====================================================
@app.callback(
    Output("graph", "figure"),
    Input("year-filter", "value"),
    Input("gas", "value"),
    Input("diesel", "value"),
    Input("elec", "value"),
)
def update_graph(years, gas, diesel, elec):

    ev_df = calculate(ev, "EV", gas, diesel, elec)
    ice_df = calculate(ice, "ICE", gas, diesel, elec)

    df = pd.concat([ev_df, ice_df])

    start, end = years
    df = df[df["year"].between(start, end)]

    if df.empty:
        return go.Figure().update_layout(title="No data available")

    fig = go.Figure()

    styles = {
        "Gasoline": ("lightblue", "circle"),
        "Diesel": ("orange", "diamond"),
        "EV": ("red", "square")
    }

    for fuel, (color, symbol) in styles.items():
        d = df[df["fuel_category"] == fuel]

        fig.add_trace(go.Scatter(
            x=d["cost_per_mile"],
            y=d["co2_per_mile"],
            mode="markers",
            marker=dict(color=color, size=10, symbol=symbol),
            name=fuel,
            text=d["vehicle_name"]
        ))

    fig.update_layout(
        title="Vehicle Cost vs CO₂ per Mile",
        xaxis_title="Cost per mile ($)",
        yaxis_title="CO₂ (g/mile)",
        plot_bgcolor="white"
    )

    return fig

# =====================================================
# RUN (LOCAL ONLY)
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)