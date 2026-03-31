import streamlit as st
import pandas as pd
import pydeck as pdk
import json
import requests
import tempfile

st.set_page_config(layout="wide")
st.title("Dashboard Usaha SLS")

# =========================
# CONFIG GOOGLE DRIVE
# =========================
ID_DATA = "1GEKjS9r_Qtm1KMM10jzmGVXxFck7dEqn"
ID_POLY = "1dZfKgYnMAOa_Jb6-SU8tXr65ixb9adg9"

URL_DATA = f"https://drive.google.com/uc?id={ID_DATA}"
URL_POLY = f"https://drive.google.com/uc?id={ID_POLY}"

# =========================
# DOWNLOAD
# =========================
@st.cache_data
def download(url, suffix):
    r = requests.get(url)
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(r.content)
    tmp.close()
    return tmp.name

# =========================
# LOAD DATA
# =========================
@st.cache_data
def load_data():
    data_path = download(URL_DATA, ".parquet")
    poly_path = download(URL_POLY, ".geojson")

    df = pd.read_parquet(data_path)

    with open(poly_path) as f:
        geojson = json.load(f)

    return df, geojson

df, geojson = load_data()

# =========================
# FILTER
# =========================
kab_list = sorted(df["kdkab"].dropna().unique())
kdkab = st.sidebar.selectbox("Kab/Kota", kab_list)

df_kab = df[df["kdkab"] == kdkab]

sls_list = sorted(df_kab["idsubsls"].unique())
idsls = st.sidebar.selectbox("SLS", ["ALL"] + sls_list)

if idsls != "ALL":
    df_kab = df_kab[df_kab["idsubsls"] == idsls]

# =========================
# MAP
# =========================
st.subheader("Peta")

polygon_layer = pdk.Layer(
    "GeoJsonLayer",
    geojson,
    pickable=True,
    get_fill_color="properties.color",
    get_line_color=[0,0,0]
)

point_layer = pdk.Layer(
    "ScatterplotLayer",
    df_kab,
    get_position=["longitude", "latitude"],
    get_radius=20,
    get_fill_color=[0,0,255,120]
)

deck = pdk.Deck(
    layers=[polygon_layer, point_layer],
    initial_view_state=pdk.ViewState(latitude=-0.5, longitude=117, zoom=7)
)

st.pydeck_chart(deck)

# =========================
# TABEL
# =========================
st.dataframe(df_kab)
pivot.columns = ["Kecamatan", "Desa", "SLS", "Jumlah Usaha"]

st.dataframe(pivot)

st.bar_chart(pivot.groupby("Kecamatan")["Jumlah Usaha"].sum())
