from dash import html
from app import app
import login
import dashboard
from dash import html, dcc, Input, Output, State
import uuid


app.layout = html.Div([
    dcc.Store(id='user-id-store', storage_type='local'),
    dcc.Location(id='url', refresh=False),
    html.Div(id='dummy-div', style={'display': 'none'}), 
    html.Div(id='page-content')
])


@app.callback(
    Output('user-id-store', 'data'),
    Input('dummy-div', 'children'),
    State('user-id-store', 'data')
)
def initialize_user_id(dummy, existing_user_id):
    if existing_user_id is None:
        # Create a new permanent ID for Alice
        new_id = str(uuid.uuid4())
        return new_id
    
    # Alice is back! Return her existing ID.
    return existing_user_id


@app.callback(
    Output('page-content', 'children'),
    Input('url', 'pathname')
)
def display_page(pathname):
    if pathname == '/dashboard':
        return dashboard.layout
    else:
        return login.layout
    

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=False, port=8050)
