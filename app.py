from dash import Dash, dcc, html, Input, Output, State, exceptions
import dash_design_kit as ddk
import plotly.express as px
from sdig.erddap.info import Info
from tile import Tile
import pandas as pd
import os
from flask import send_file
import hashlib
import urllib
import redis
import json
from pyproj import Transformer

redis_instance = redis.StrictRedis.from_url(os.environ.get("REDIS_URL", "redis://127.0.0.1:6379"))

app = Dash(__name__)
server = app.server  # expose server variable for Procfile

def relpath(path):
    if 'Workspaces' in app.get_relative_path('/'):
        return "/Workspaces/view/{}{}".format(os.environ["DASH_APP_NAME"], path)
    else:
        return path

app.layout = ddk.App([
    ddk.Header([
        ddk.Logo(src=app.get_asset_url('50th_webheader_720px__a.png')),
        ddk.Title('Web Mapping Tile Server for ERDDAP Data'),
    ]),
    ddk.Row(children=[
        ddk.ControlCard(width=.3, orientation='vertical', children=[
            ddk.ControlItem(label="Dataset URL:", children=[
                dcc.Input(id='erddap-url', type='url', placeholder='Enter the ERDDAP URL of a dataset.', style={'width':'100%'})
            ])
        ]),
        ddk.ControlCard(width=.3, orientation='vertical', children=[
            ddk.ControlItem(label="Variable to Map:", children=[
                dcc.Dropdown(id='variable')
            ])
        ]),
        ddk.ControlCard(width=.3, orientation='vertical', children=[
            ddk.ControlItem(label="Messages:", children=[
                dcc.Loading(dcc.Textarea(id='message', readOnly=True, style={'width': '100%'}))
            ])
        ])
    ]),
    ddk.Block(children=[
        ddk.ControlCard(width=.3, children=[
            ddk.ControlItem(label='Variable Minimum for plot colorbar range.', children=[
                dcc.Input(id='var-min', type='number')
            ])
        ]),
        ddk.ControlCard(width=.3, children=[
            ddk.ControlItem(label='Variable Maximum for plot colorbar range.', children=[
                dcc.Input(id='var-max', type='number')
            ])
        ]),
        html.Button(id='preview', children='Preview'),
    ]),
    ddk.Block(width=.3, children=[
        dcc.Loading(html.Img(id='img1', src=app.get_asset_url('blank.png')))
    ]),
    ddk.Block(width=.3, children=[
        dcc.Loading(html.Img(id='img2', src=app.get_asset_url('blank.png')))
    ]),
    html.Button(id='save', children='Save'),
    ddk.ControlCard(width=.5, children=[
        ddk.ControlItem(label='Internal URL for Mapbox Maps:', children=[
            dcc.Loading(dcc.Textarea(id='internal-url', readOnly=True, style={'width': '100%'}))
        ])
    ]),
    ddk.ControlCard(width=.5, children=[
        ddk.ControlItem(label='External URL for Mapbox Maps:', children=[
            dcc.Loading(dcc.Textarea(id='external-url', readOnly=True, style={'width': '100%'}))
        ])
    ])
])

@server.route(relpath('/tile/<tile_hash>/<zoom>/<y>/<x>'))
def tile(tile_hash, zoom, y, x):
    tile = Tile(zoom, x, y)
    tile_config = redis_instance.hget("tile", tile_hash)
    img_file = make_image(tile, tile_config.url, tile_config.variable, tile_config.min, tile_config.max)
    return send_file(
        'assets/' + img_file
    )


@app.callback(
    Output('variable', 'options'),
    Output('message', 'value', allow_duplicate=True),
    Input('erddap-url', 'value'),
    prevent_initial_call=True
)
def define_variables(in_url):
    options = []
    if in_url is None or len(in_url) == 0:
        raise exceptions.PreventUpdate
    try:
        myinfo = Info(in_url)
        dsg_type = myinfo.get_dsg_type()
        if dsg_type != 'points' and dsg_type != 'trajectory':
            return options, 'I do not know how to make a map of the selected data type of ' + dsg_type
        else:
            ds_vars, long_names, units, std_names = myinfo.get_variables()
            for v in ds_vars:
                if v in long_names:
                    long_n = long_names[v]
                else:
                    long_n = v
                options.append({'label': long_n, 'value': v})
            return options, 'Variables added. Now pick a variable.'
    except:
        raise exceptions.PreventUpdate
    return options, 'Nope!'

@app.callback(
    Output('var-min', 'value'),
    Output('var-max', 'value'),
    Output('message', 'value', allow_duplicate=True),
    Input('variable', 'value'),
    State('erddap-url', 'value'),
    prevent_initial_call=True
)
def get_min_max(in_variable, in_url):
    vmin = -1
    vmax = 1
    if in_url is None or len(in_url) == 0 or in_variable is None or len(in_variable) == 0:
        raise exceptions.PreventUpdate
    myinfo = Info(in_url)
    data_url = myinfo.url + '.csv?' + in_variable + '&orderByMinMax("' + in_variable + '")'
    print(data_url)
    df = pd.read_csv(data_url)
    vmin = str(round(float(df.iloc[1][0]), 2))
    vmax = str(round(float(df.iloc[2][0]), 2))
    return vmin, vmax, 'Adjust the min max values if desired.'    


@app.callback(
[
    Output('img1', 'src'),
    Output('img2', 'src')
],
[
    Input('preview', 'n_clicks')
],
[
    State('erddap-url', 'value'),
    State('variable', 'value'),
    State('var-min', 'value'),
    State('var-max', 'value')
]
)
def make_previews(click, state_url, state_variable, state_min, state_max):
    if not state_url or not state_variable or not state_min or not state_max:
        raise exceptions.PreventUpdate

    tile1 = Tile(2,2,2)
    img_file1 = make_image(tile1, state_url, state_variable, state_min, state_max)
    tile2 = Tile(4,4,4)
    img_file2 = make_image(tile2, state_url, state_variable, state_min, state_max)
    print(img_file2)
    return [app.get_asset_url(img_file1), app.get_asset_url(img_file2)]



def make_image(my_tile, my_url, my_variable, my_min, my_max):
    local_info = Info(my_url)
    s = local_info.url+my_variable+str(my_min)+str(my_max)
    hash_key = hashlib.sha1(s.encode("utf-8")).hexdigest()
    lon_con = '&longitude>=' + str(my_tile.box.exterior.coords[3][0]) + '&longitude<=' + str(my_tile.box.exterior.coords[0][0])
    lat_con = '&latitude>=' + str(my_tile.box.exterior.coords[0][1]) + '&latitude<=' + str(my_tile.box.exterior.coords[1][1])
    url = (
            local_info.url +
            '.csv?latitude,longitude,expocode,' + my_variable +
            urllib.parse.quote(lon_con, safe='&()=:/') +
            urllib.parse.quote(lat_con, safe='&()=:/')
    )

    assets_dir = 'assets'
    base_dir = 'tiles/' + hash_key
    tile_dir = str(my_tile.zoom) + '/' + str(my_tile.x)
    tile_name = str(my_tile.y) + '.png'
    full_tile = assets_dir + '/' + base_dir + '/' + tile_dir + '/' + tile_name
    assets_rel = base_dir + '/' + tile_dir + '/' + tile_name
    if os.path.isfile(full_tile):
        print('returning cached tile')
        return assets_rel
    else:
        try:
            df = pd.read_csv(url, skiprows=[1])
            df = df.query('-90.0 <= latitude <= 90')
            df = df.query('-180.0 <= longitude <= 180')
            transformer = Transformer.from_crs("epsg:4326", "epsg:3857")
            lon_meters, lat_meters = transformer.transform(df.latitude, df.longitude)
            df = df.assign(lon_meters=lon_meters, lat_meters=lat_meters)
            lat_range = [df['lat_meters'].min(), df['lat_meters'].max()]
            lon_range = [df['lon_meters'].min(), df['lon_meters'].max()]
            df.reset_index(drop=True, inplace=True)
            figure = px.scatter(df,
                                y='lat_meters',
                                x='lon_meters',
                                color=my_variable,
                                range_color=[float(my_min), float(my_max)],
                                color_continuous_scale='Viridis'
                                )
            figure.update_traces(marker={'size': 2})
            figure.update_layout(height=256, width=256, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                 margin={'l': 0, 'r': 0, 't': 0, 'b': 0}, showlegend=False)
            figure.update_coloraxes(showscale=False)
            # figure.update_geos(projection_type="mercator",
            #                    lataxis_range=[my_tile.box.exterior.coords[0][1], my_tile.box.exterior.coords[1][1]],
            #                    lonaxis_range=[my_tile.box.exterior.coords[3][0], my_tile.box.exterior.coords[0][0]])
            figure.update_xaxes(showgrid=False, visible=False, showticklabels=False, range=lon_range)
            figure.update_yaxes(showgrid=False, visible=False, showticklabels=False, range=lat_range)
            if not os.path.exists(assets_dir + '/' + base_dir + '/' + tile_dir):
                os.makedirs(assets_dir + '/' + base_dir + '/' + tile_dir)
            figure.write_image(full_tile)
            return assets_rel
        except Exception as e:
            print(url)
            app.logger.error('Exception encountered')
            app.logger.error(e)
            return 'blank.png'
                
                
@app.callback(
[
    Output('message', 'value', allow_duplicate=True),
    Output('internal-url', 'value'),
    Output('external-url', 'value')
],
[
    Input('save', 'n_clicks')
],
[
    State('erddap-url', 'value'),
    State('variable', 'value'),
    State('var-min', 'value'),
    State('var-max', 'value')
], prevent_initial_call=True
)
def save_tile_map(save_click, save_url, save_variable, save_min, save_max):
    save_info = Info(save_url)
    s = save_info.url+save_variable+str(save_min)+str(save_max)
    hash_key = hashlib.sha1(s.encode("utf-8")).hexdigest()
    tile_config = {
        'url': save_info.url,
        'variable': save_variable,
        'min': save_min,
        'max': save_max
        }
    internal_url = 'https://dash.pmel.noaa.gov/wmts/tile/' + hash_key + '/' + save_variable + '/{z}/{y}/{x}'
    external_url = 'https://viz.pmel.noaa.gov/wmts/tile/' + hash_key + '/' + save_variable + '/{z}/{y}/{x}'
    redis_instance.hset("tile", hash_key, json.dumps(tile_config))
    return 'File config saved. See below', internal_url, external_url


if __name__ == '__main__':
    app.run_server(debug=True)