from dash import html
from app import app
import login  
import dashboard


app.layout = html.Div([
    html.Div(login.layout),
    html.Div(dashboard.dashboard_layout, id='dashboard-container', style={'display': 'none'})
])


if __name__ == '__main__':
    app.run(debug=True, port=8050)