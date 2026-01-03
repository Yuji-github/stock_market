from dash import html, dcc, callback, Input, Output, State
import pandas as pd
from utils import get_pl_bs_cashflow, calculate_valuation_metrics


df = pd.read_parquet('/workspace/src/edinet_company_list/company_list.parquet')
df.dropna(subset=['証券コード'], inplace=True)
data = {
    "industry": df["提出者業種"].to_list(),
    "company_name": df["提出者名"].to_list(),
    'code': df['証券コード'].to_list(),  # e.g., 72030
    'yfinance_ticker': df['yfinance_ticker'].to_list()  # e.g., 7203.T
}
df = pd.DataFrame(data)
industry_options = sorted(df['industry'].unique())


dashboard_layout = html.Div([
    html.H1("Company Analysis Dashboard"),
    html.Hr(),

    html.Div([
        html.Label("1. Select Industry Type(s):"),
        dcc.Dropdown(
            id='type-selector',
            options=[{'label': i, 'value': i} for i in industry_options],
            multi=True,
            placeholder="Select type..."
        ),
    ], style={'width': '45%', 'display': 'inline-block'}),

    html.Div([
        html.Label("2. Select Company Name(s):"),
        dcc.Dropdown(
            id='company-selector',
            options=[], # Empty initially, populated by callback
            multi=True,
            placeholder="Select companies..."
        ),
    ], style={'width': '45%', 'display': 'inline-block', 'marginLeft': '20px'}),

    html.Br(), html.Br(),
    
    html.Button('Search Data', id='search-btn', n_clicks=0, style={'fontSize': '16px'}),

    html.Hr(),

    # Area to display charts/tables later
    html.Div(id='dashboard-content')
])


@callback(
    Output('company-selector', 'options'),
    Input('type-selector', 'value')
)
def set_company_options(selected_types):
    if not selected_types:
        # If nothing selected, you can either return [] or all companies.
        return []
    
    # Filter the dataframe based on selected types
    filtered_df = df[df['industry'].isin(selected_types)]
    
    # Get unique companies from the filtered data
    companies = sorted(filtered_df['company_name'].unique())
    
    return [{'label': c, 'value': c} for c in companies]


@callback(
    Output('dashboard-content', 'children'),
    Input('search-btn', 'n_clicks'),
    State('type-selector', 'value'),
    State('company-selector', 'value'),
    prevent_initial_call=True
)
def execute_search(n_clicks, selected_types, selected_companies):
    if n_clicks is None or n_clicks == 0:
        return ""
        
    if not selected_types and not selected_companies:
        return "Please make a selection and click Search."

    # --- YOUR MAIN ANALYSIS LOGIC GOES HERE ---
    selected_comapnies_df = df[df['company_name'].isin(selected_companies)]
    result = {}
    for idx, row in selected_comapnies_df.iterrows():
        pl_data, bs_data, cf_data = get_pl_bs_cashflow(row['yfinance_ticker'].split('.')[0])
        finance_result = {}
        if pl_data and bs_data:
            finance_result = calculate_valuation_metrics(row['yfinance_ticker'], pl_data, bs_data)
        this_result = {'Name': row['company_name'], 'PL': pl_data, "BS": bs_data, 'CF': cf_data, 'finance_result': finance_result}
        result[idx] = this_result

    return html.Div([
        html.H3("Search Results"),
        html.P(f"Searching for Types: {selected_types}"),
        html.P(f"Searching for Companies: {selected_companies}"),
        # You can return graphs or tables here
    ])