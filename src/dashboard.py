from dash import html,dcc


dashboard_layout = html.Div(id='dashboard-container', style={'display': 'none'}, children=[
    html.Div([
        html.H1("Welcome to the Dashboard"),
        html.Hr(),
        html.P("Here is your secure data."),
        dcc.Graph(
            id='example-graph',
            figure={
                'data': [{'x': [1, 2, 3], 'y': [4, 1, 2], 'type': 'bar', 'name': 'SF'}],
                'layout': {'title': 'Secure Data Visualization'}
            }
        )
    ])
])