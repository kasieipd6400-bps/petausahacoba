import streamlit as st
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import json
import tempfile
import requests

st.set_page_config(layout="wide")
st.title("Dashboard Usaha SLS (ONLINE PARQUET)")

# =========================
# CONFIG GOOGLE DRIVE
# =========================
ID_USAHA = "1GEKjS9r_Qtm1KMM10jzmGVXxFck7dEqn"
ID_SLS = "1dZfKgYnMAOa_Jb6-SU8tXr65ixb9adg9"

URL_USAHA = f"https://drive.google.com/uc?id={ID_USAHA}"
URL_SLS = f"https://drive.google.com/uc?id={ID_SLS}"

# =========================
# DOWNLOAD FILE
# =========================
@st.cache_data
def download_file(url, suffix):
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

    # download dari drive
    usaha_path = download_file(URL_USAHA, ".parquet")
    sls_path = download_file(URL_SLS, ".parquet")

    # load usaha
    df = pd.read_parquet(usaha_path)

    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    gdf_usaha = gpd.GeoDataFrame(
        df,
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326"
    )

    # load sls
    gdf_sls = gpd.read_parquet(sls_path)

    gdf_sls = gdf_sls[
        ["idsubsls", "kdkab", "nmkec", "nmdesa", "nmsls", "geometry"]
    ]

    gdf_sls["idsubsls"] = gdf_sls["idsubsls"].astype(str)
    gdf_sls["kdkab"] = gdf_sls["kdkab"].astype(str).str.zfill(2)

    # simplify biar ringan
    gdf_sls["geometry"] = gdf_sls["geometry"].simplify(0.0005)

    # spatial join
    hasil = gpd.sjoin(
        gdf_usaha,
        gdf_sls,
        how="left",
        predicate="intersects"
    )

    for col in ["kdkab", "idsubsls", "nmkec", "nmdesa", "nmsls"]:
        if col not in hasil.columns:
            if f"{col}_right" in hasil.columns:
                hasil[col] = hasil[f"{col}_right"]

    hasil["idsubsls"] = hasil["idsubsls"].fillna("LUAR")
    hasil["kdkab"] = hasil["kdkab"].astype(str).str.zfill(2)

    return hasil, gdf_sls


# =========================
# LOAD SAFE
# =========================
try:
    hasil, gdf_sls = load_data()
except Exception as e:
    st.error("Gagal load data")
    st.stop()

# =========================
# AGREGASI
# =========================
count_sls = hasil.groupby("idsubsls").size().reset_index(name="jumlah")
gdf_sls = gdf_sls.merge(count_sls, on="idsubsls", how="left")
gdf_sls["jumlah"] = gdf_sls["jumlah"].fillna(0)

# =========================
# FILTER
# =========================
st.sidebar.header("Filter")

kab_list = sorted(hasil["kdkab"].dropna().unique())
kdkab = st.sidebar.selectbox("Pilih Kab/Kota", kab_list)

df_kab = hasil[hasil["kdkab"] == kdkab]
sls_list = sorted(df_kab["idsubsls"].dropna().unique())

# =========================
# SEARCH + PASTE SLS
# =========================
search_sls = st.sidebar.text_input("Cari / Paste IDSUBSLS")

if search_sls:
    filtered_sls = [s for s in sls_list if search_sls.lower() in s.lower()]
else:
    filtered_sls = sls_list

idsls = st.sidebar.selectbox("Pilih SLS", ["ALL"] + filtered_sls)

zoom_lat, zoom_lon = None, None

if search_sls and search_sls in sls_list:
    idsls = search_sls

if idsls != "ALL":
    df_kab = df_kab[df_kab["idsubsls"] == idsls]

    gdf_zoom = gdf_sls[gdf_sls["idsubsls"] == idsls]
    if len(gdf_zoom) > 0:
        centroid = gdf_zoom.geometry.centroid.iloc[0]
        zoom_lat = centroid.y
        zoom_lon = centroid.x

# =========================
# TITIK LUAR
# =========================
show_luar = st.sidebar.checkbox("Tampilkan titik luar SLS")

if show_luar:
    df_luar = hasil[
        (hasil["kdkab"] == kdkab) &
        (hasil["idsubsls"] == "LUAR")
    ]
else:
    df_luar = pd.DataFrame()

# =========================
# WARNA
# =========================
max_val = gdf_sls["jumlah"].max()

def get_color(val):
    if val == 0:
        return [180, 180, 180, 120]

    ratio = val / max_val if max_val > 0 else 0

    if ratio < 0.5:
        return [int(255 * ratio * 2), 255, 0, 140]
    else:
        return [255, int(255 * (1 - (ratio - 0.5) * 2)), 0, 140]

gdf_sls["color"] = gdf_sls["jumlah"].apply(get_color)

# =========================
# MAP
# =========================
st.subheader("Peta Usaha")

gdf_plot = gdf_sls[gdf_sls["kdkab"] == kdkab].copy()
gdf_plot = gdf_plot.explode(index_parts=False)

if idsls != "ALL":
    gdf_plot = gdf_plot[gdf_plot["idsubsls"] == idsls]

geojson = json.loads(gdf_plot.to_json())

polygon_layer = pdk.Layer(
    "GeoJsonLayer",
    geojson,
    get_fill_color="properties.color",
    get_line_color=[0, 0, 0],
    pickable=True
)

point_layer = pdk.Layer(
    "ScatterplotLayer",
    df_kab,
    get_position=["longitude", "latitude"],
    get_radius=20,
    get_fill_color=[0, 0, 255, 120]
)

luar_layer = pdk.Layer(
    "ScatterplotLayer",
    df_luar,
    get_position=["longitude", "latitude"],
    get_radius=25,
    get_fill_color=[0, 0, 0, 200]
)

lat = df_kab["latitude"].mean() if len(df_kab) > 0 else -0.5
lon = df_kab["longitude"].mean() if len(df_kab) > 0 else 117

if zoom_lat:
    lat, lon = zoom_lat, zoom_lon

layers = [polygon_layer, point_layer]

if show_luar:
    layers.append(luar_layer)

deck = pdk.Deck(
    layers=layers,
    initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=11),
    tooltip={"text": "SLS: {idsubsls}\nJumlah: {jumlah}"}
)

st.pydeck_chart(deck)

# =========================
# TABEL
# =========================
st.subheader("Tabel Usaha")

st.dataframe(df_kab[
    ["kdkab","idsubsls","nama_usaha","alamat_usaha","gcs_result","gc_username"]
])

# =========================
# PIVOT
# =========================
st.subheader("Pivot Wilayah")

pivot = pd.pivot_table(
    df_kab,
    index=["nmkec", "nmdesa", "idsubsls"],
    values="nama_usaha",
    aggfunc="count"
).reset_index()

pivot.columns = ["Kecamatan", "Desa", "SLS", "Jumlah Usaha"]

st.dataframe(pivot)

st.bar_chart(pivot.groupby("Kecamatan")["Jumlah Usaha"].sum())
