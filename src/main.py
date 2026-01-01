from dash import html
from app import app
import login  
import dashboard


app.layout = html.Div([
    login.layout,       # The Login Module
    dashboard.dashboard_layout    # The Dashboard Module
])


if __name__ == '__main__':
    app.run(debug=True, port=8050)