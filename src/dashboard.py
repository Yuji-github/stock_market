from dash import html, dcc, callback, Input, Output, State, dash_table
import pandas as pd
from utils import (
    get_pl_bs_cashflow,
    calculate_valuation_metrics,
    create_plots,
    gemini_analysis,
)


df = pd.read_parquet("/workspace/src/edinet_company_list/company_list.parquet")
df.dropna(subset=["証券コード"], inplace=True)
data = {
    "industry": df["提出者業種"].to_list(),
    "company_name": df["提出者名"].to_list(),
    "code": df["証券コード"].to_list(),  # e.g., 72030
    "yfinance_ticker": df["yfinance_ticker"].to_list(),  # e.g., 7203.T
}
df = pd.DataFrame(data)
industry_options = sorted(df["industry"].unique())


layout = html.Div(
    [
        html.H1("Company Analysis Dashboard"),
        html.Hr(),
        html.Div(
            [
                html.Label("1. Select Industry Type(s):"),
                dcc.Dropdown(
                    id="type-selector",
                    options=[{"label": i, "value": i} for i in industry_options],
                    multi=True,
                    placeholder="Select type...",
                ),
            ],
            style={"width": "45%", "display": "inline-block"},
        ),
        html.Div(
            [
                html.Label("2. Select Company Name(s):"),
                dcc.Dropdown(
                    id="company-selector",
                    options=[],  # Empty initially, populated by callback
                    multi=True,
                    placeholder="Select companies...",
                ),
            ],
            style={"width": "45%", "display": "inline-block", "marginLeft": "20px"},
        ),
        html.Br(),
        html.Br(),
        html.Button(
            "Search Data", id="search-btn", n_clicks=0, style={"fontSize": "16px"}
        ),
        html.Hr(),
        # Area to display charts/tables later
        html.Div(id="dashboard-content"),
    ]
)


@callback(Output("company-selector", "options"), Input("type-selector", "value"))
def set_company_options(selected_types):
    if not selected_types:
        # If nothing selected, you can either return [] or all companies.
        return []

    # Filter the dataframe based on selected types
    filtered_df = df[df["industry"].isin(selected_types)]

    # Get unique companies from the filtered data
    companies = sorted(filtered_df["company_name"].unique())

    return [{"label": c, "value": c} for c in companies]


@callback(
    Output("dashboard-content", "children"),
    Input("search-btn", "n_clicks"),
    State("type-selector", "value"),
    State('user-id-store', 'data'),
    State("company-selector", "value"),
    prevent_initial_call=True,
)
def execute_search(n_clicks, selected_types, user_id, selected_companies):
    if n_clicks is None or n_clicks == 0:
        return ""

    if not selected_types and not selected_companies:
        return "Please make a selection and click Search."
    
    if not user_id:
        # Fallback if something went wrong (rare)
        user_id = "unknown_user"

    selected_comapnies_df = df[df["company_name"].isin(selected_companies)]
    # This list will hold the final HTML blocks for every company
    company_blocks = []

    for _, row in selected_comapnies_df.iterrows():
        ticker = row["yfinance_ticker"]
        name = row["company_name"]
        industry = row["industry"]

        # Clean ticker for API
        clean_ticker = ticker.split(".")[0]

        pl_data, bs_data, cf_data = get_pl_bs_cashflow(clean_ticker)
        finance_result = {}
        if pl_data and bs_data:
            finance_result = calculate_valuation_metrics(ticker, pl_data, bs_data)

        this_summary_record = {
            "Price": finance_result.get("Price", 0),
            "EquityRatio": finance_result.get("EquityRatio", 0),
            "PER": finance_result.get("PER", 0),
            "PBR": finance_result.get("PBR", 0),
            "ROE": finance_result.get("ROE", 0),
            "ROA": finance_result.get("ROA", 0),
        }
        this_comapny_df = pd.DataFrame([this_summary_record])

        # Note: DataTable styling is often best kept as props for specific cell behavior,
        # but you can move specific colors/fonts to CSS if preferred.
        this_metrics_table = dash_table.DataTable(
            data=this_comapny_df.to_dict("records"),
            columns=[{"name": i, "id": i} for i in this_comapny_df.columns],
            style_table={"overflowX": "auto"},
            style_cell={"textAlign": "center", "padding": "5px", "fontSize": "12px"},
            style_header={"backgroundColor": "#f1f1f1", "fontWeight": "bold"},
        )

        # plots
        plots = create_plots(pl_data, bs_data, cf_data)

        def wrap_graph(key):
            """Helper to wrap graph in dcc.Graph with CSS class"""
            if key in plots:
                return dcc.Graph(
                    figure=plots[key],
                    config={"displayModeBar": False},
                    className="chart-wrapper",  # Used CSS class here
                )
            return html.Div(
                [html.P("No data available for this section")], className="no-data-msg"
            )

        pl_content = [wrap_graph("pl_growth"), wrap_graph("pl_efficiency")]
        bs_content = [wrap_graph("bs_structure"), wrap_graph("bs_safety")]
        cf_content = [wrap_graph("cf_truth"), wrap_graph("cf_strategy")]

        # Gemini Analysis
        analysis_component = gemini_analysis(
            industry, this_summary_record, pl_data, bs_data, cf_data, user_id
        )

        # --- CREATE COMPANY CONTAINER ---
        company_layout = html.Div(
            [
                # --- ROW 1: Title ---
                html.H3(name, className="company-title"),
                # --- ROW 2: Metrics (Left) + Tabs (Right) ---
                html.Div(
                    [
                        # Left Col: Metrics
                        html.Div(
                            [
                                html.H5("Key Metrics", className="section-title"),
                                this_metrics_table,
                            ],
                            className="metrics-col",
                        ),
                        # Right Col: Plots using Tabs
                        html.Div(
                            [
                                dcc.Tabs(
                                    [
                                        dcc.Tab(
                                            label="Profit & Loss",
                                            children=pl_content,
                                            className="custom-tab",
                                            selected_className="custom-tab--selected",
                                        ),
                                        dcc.Tab(
                                            label="Balance Sheet",
                                            children=bs_content,
                                            className="custom-tab",
                                            selected_className="custom-tab--selected",
                                        ),
                                        dcc.Tab(
                                            label="Cash Flow",
                                            children=cf_content,
                                            className="custom-tab",
                                            selected_className="custom-tab--selected",
                                        ),
                                    ]
                                )
                            ],
                            className="plots-col",
                        ),
                    ],
                    className="content-row",
                ),
                # --- ROW 3: Gemini Analysis (Bottom) ---
                html.Div(
                    [
                        html.H5("Gemini (Flash) Analysis", className="section-title"),
                        html.Div(analysis_component, className="gemini-box"),
                    ],
                    className="analysis-row",
                ),
            ],
            className="company-card",
        )  # Main container class

        if not company_layout:
            return html.Div("No data found for selected companies.")

        company_blocks.append(company_layout)

    # Return the list of all company blocks
    return html.Div(company_blocks)
