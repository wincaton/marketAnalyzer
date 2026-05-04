import os
import pandas as pd
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# =====================================================
# LOAD DATA
# =====================================================
ev = pd.read_csv("eCleaned.csv")
ice = pd.read_csv("iceCleaned.csv")

# =====================================================
# CLEAN DATA
# =====================================================
for df in [ev, ice]:
    df.columns = df.columns.str.strip().str.lower().str.replace("\xa0", "")
    df["make"] = df["make"].astype(str).str.strip().str.title()

    if "type" in df.columns:
        df["type"] = df["type"].astype(str).str.strip().str.lower()

# =====================================================
# BRAND LIST
# =====================================================
BRANDS_ROW1 = ["Ford","Chevrolet","Toyota","Honda","Nissan","Jeep","Hyundai"]
BRANDS_ROW2 = ["Kia","Subaru","GMC","Ram","Volkswagen","Mazda","Dodge"]

# =====================================================
# CONSTANTS (UPDATED)
# =====================================================
default_elec_rate = 0.15
default_gas_price = 4.50
default_diesel_price = 5.50
gCO2grid_default = 324

# =====================================================
# CALC FUNCTION
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
# APP
# =====================================================
app = dash.Dash(__name__)
server = app.server

# =====================================================
# LAYOUT
# =====================================================
app.layout = html.Div([

    html.H2("Vehicle Impact"),

    # FILTER ROW
    html.Div([

        html.Div([
            html.Label("Vehicle Type"),
            dcc.Checklist(
                id="type-filter",
                options=[
                    {"label": "Car", "value": "car"},
                    {"label": "Van", "value": "van"},
                    {"label": "Truck", "value": "truck"},
                ],
                value=["car", "van", "truck"],
                inline=True
            ),
        ], style={"width": "35%"}),

        html.Div([
            html.Label("Select Brands"),

            dcc.Checklist(
                id="brand-filter-1",
                options=[{"label": b, "value": b} for b in BRANDS_ROW1],
                value=BRANDS_ROW1,
                inline=True
            ),

            dcc.Checklist(
                id="brand-filter-2",
                options=[{"label": b, "value": b} for b in BRANDS_ROW2],
                value=BRANDS_ROW2,
                inline=True
            ),

        ], style={"width": "65%", "textAlign": "right"}),

    ], style={"display": "flex"}),

    dcc.RangeSlider(
        id="year-filter",
        min=2017,
        max=2026,
        value=[2017, 2026],
        marks={y: str(y) for y in range(2017, 2027)},
    ),

    dcc.Graph(id="graph"),

    # =================================================
    # CONTROLS
    # =================================================
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

    ], style={"display": "flex"})

])

# =====================================================
# DROPDOWNS (2025–2026 ONLY)
# =====================================================
@app.callback(
    Output("p-year", "options"),
    Input("p-type", "value")
)
def set_years(ptype):
    return [{"label": y, "value": y} for y in [2025, 2026]]

@app.callback(
    Output("p-make", "options"),
    Input("p-year", "value"),
    Input("p-type", "value")
)
def set_make(year, ptype):
    df = ev if ptype == "EV" else ice
    df = df[df["year"] == year]
    return [{"label": m, "value": m} for m in sorted(df["make"].unique())]

@app.callback(
    Output("p-model", "options"),
    Input("p-year", "value"),
    Input("p-make", "value"),
    Input("p-type", "value")
)
def set_model(year, make, ptype):
    df = ev if ptype == "EV" else ice
    df = df[(df["year"] == year) & (df["make"] == make)]
    return [{"label": m, "value": m} for m in sorted(df["model"].unique())]

@app.callback(
    Output("p-displ", "options"),
    Input("p-year", "value"),
    Input("p-make", "value"),
    Input("p-model", "value"),
    Input("p-type", "value")
)
def set_displ(year, make, model, ptype):
    df = ev if ptype == "EV" else ice
    df = df[
        (df["year"] == year) &
        (df["make"] == make) &
        (df["model"] == model)
    ]

    col = "displ" if "displ" in df.columns else None
    if col:
        return [{"label": str(v), "value": v} for v in df[col].dropna().unique()]
    return []

# =====================================================
# GRAPH (WITH GREEN X)
# =====================================================
@app.callback(
    Output("graph", "figure"),
    Input("year-filter", "value"),
    Input("type-filter", "value"),
    Input("brand-filter-1", "value"),
    Input("brand-filter-2", "value"),
    Input("gas", "value"),
    Input("diesel", "value"),
    Input("elec", "value"),
    Input("p-type", "value"),
    Input("p-year", "value"),
    Input("p-make", "value"),
    Input("p-model", "value"),
    Input("p-displ", "value"),
)
def update_graph(years, types, b1, b2, gas, diesel, elec,
                 ptype, pyear, pmake, pmodel, pdispl):

    ev_df = calculate(ev, "EV", gas, diesel, elec)
    ice_df = calculate(ice, "ICE", gas, diesel, elec)

    df = pd.concat([ev_df, ice_df])

    # FILTERS
    start, end = years
    df = df[df["year"].between(start, end)]

    if types:
        df = df[df["type"].isin(types)]

    brands = (b1 or []) + (b2 or [])
    if brands:
        df = df[df["make"].isin(brands)]

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

    # =================================================
    # ADD GREEN X (PROSPECTIVE VEHICLE)
    # =================================================
    if pyear and pmake and pmodel:
        source = ev_df if ptype == "EV" else ice_df

        d = source[
            (source["year"] == pyear) &
            (source["make"] == pmake) &
            (source["model"] == pmodel)
        ]

        if pdispl and "displ" in d.columns:
            d = d[d["displ"] == pdispl]

        if not d.empty:
            row = d.iloc[0]

            fig.add_trace(go.Scatter(
                x=[row["cost_per_mile"]],
                y=[row["co2_per_mile"]],
                mode="markers",
                marker=dict(
                    color="green",
                    size=20,
                    symbol="x"
                ),
                name="Your Vehicle"
            ))

    fig.update_layout(
        title="Vehicle Cost vs CO₂ per Mile",
        xaxis_title="Cost per mile ($)",
        yaxis_title="CO₂ (g/mile)",
        plot_bgcolor="white"
    )

    return fig

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    app.run(debug=True)