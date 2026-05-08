import streamlit as st
import pandas as pd
import pydeck as pdk
from pathlib import Path

# --- PAGE CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Crop Tour - Brazil 2026")

st.markdown("""
<style>
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(16px); }
        to   { opacity: 1; transform: translateY(0); }
    }
    .detail-card { animation: fadeInUp 0.35s ease; }
    .stDeckGlJsonChart > div { border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

st.title("Sampling Map: Safrinha Crop Tour 2026")

FOTOS_DIR = Path("fotos")
CSV_FILE = "crop_tour_safrinha.csv"


# --- 1. DATA LOADING ---
@st.cache_data
def load_data(csv_file):
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip()
    df = df.rename(columns={'_latitude': 'latitude', '_longitude': 'longitude', 'localidade': 'localidade_'})
    df = df.dropna(subset=['latitude', 'longitude'])

    # Handle different column names for different crops
    if 'estdio_fenolgico' in df.columns and 'estadio_fenologico' not in df.columns:
        df = df.rename(columns={'estdio_fenolgico': 'estadio_fenologico'})
    if 'condio_da_lavoura' in df.columns:
        pass  # Already correct
    if 'espaamento_cm' in df.columns and 'espacamento_de_linha_cm' not in df.columns:
        pass  # Safrinha uses espaamento_cm

    # Normalização de strings (Regex para espaços duplos/invisíveis)
    if not df.empty and 'condicao_da_lavoura' in df.columns:
        df['condicao_da_lavoura'] = (
            df['condicao_da_lavoura']
            .fillna("Sem Info")
            .astype(str)
            .str.replace(r'\s+', ' ', regex=True)
            .str.strip()
            .replace(["nan", "None", "", "Nan", "NaN"], "Sem Info")
        )

    if not df.empty and 'estadio_fenologico' in df.columns:
        df['estadio_fenologico'] = (
            df['estadio_fenologico']
            .fillna("Sem Info")
            .astype(str)
            .str.replace(r'\s+', ' ', regex=True)
            .str.strip()
            .replace(["nan", "None", "", "Nan", "NaN"], "Sem Info")
        )

    if not df.empty and 'condicao_da_lavoura' in df.columns:
        color_map = {
            "1. Muito Ruim": [139, 0, 0, 230],
            "2. Ruim": [231, 76, 60, 230],
            "3. Media": [241, 196, 15, 230],
            "4. Boa": [46, 204, 113, 230],
            "5. Excelente": [142, 68, 173, 230],
            "Sem Info": [128, 128, 128, 160],
        }
        df['base_color'] = df['condicao_da_lavoura'].apply(
            lambda x: color_map.get(x, color_map["Sem Info"])
        )
    else:
        df['base_color'] = [[128, 128, 128, 160]] * len(df)

    df.insert(0, 'ID', range(1, len(df) + 1))
    return df


@st.cache_resource(ttl=300)
def get_image_index():
    index = {}
    if not FOTOS_DIR.exists(): return index
    for path in FOTOS_DIR.glob("*"):
        if path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            index[path.stem] = str(path)
    return index


df = load_data(CSV_FILE)
image_index = get_image_index()

# --- 2. SIDEBAR (LEGEND & FILTERS) ---
st.sidebar.markdown("### Legend - Condition")
st.sidebar.markdown("""
- 🔴 **1. Muito Ruim** (Very Poor)
- 🟠 **2. Ruim** (Poor)
- 🟡 **3. Media** (Average)
- 🟢 **4. Boa** (Good)
- 🟣 **5. Excelente** (Excellent)
- ⚪ **Sem Info** (No Information)
""")

if not df.empty:
    st.sidebar.header("Crop Filters")

    condition = st.sidebar.multiselect(
        "Condition:",
        options=sorted(df["condicao_da_lavoura"].unique()) if "condicao_da_lavoura" in df.columns else [],
        default=df["condicao_da_lavoura"].unique().tolist() if "condicao_da_lavoura" in df.columns else []
    )

    stages = st.sidebar.multiselect(
        "Growth Stage:",
        options=sorted(df["estadio_fenologico"].unique()) if "estadio_fenologico" in df.columns else [],
        default=df["estadio_fenologico"].unique().tolist() if "estadio_fenologico" in df.columns else []
    )

    if condition and stages:
        df_filtered = df[
            (df["condicao_da_lavoura"].isin(condition)) &
            (df["estadio_fenologico"].isin(stages))
            ].copy().reset_index(drop=True)
    else:
        df_filtered = df.copy().reset_index(drop=True)
else:
    df_filtered = df.copy()

st.sidebar.divider()
st.sidebar.metric("Total Samples", len(df_filtered))

# --- 3. SESSION STATE ---
if "selected_idx" not in st.session_state:
    st.session_state["selected_idx"] = None
st.session_state["_df_len"] = len(df_filtered)


def on_map_select():
    raw = st.session_state.get("pydeck_map")
    if not raw: return
    indices = raw.get("selection", {}).get("indices", {})
    all_idx = []
    if isinstance(indices, dict):
        for v in indices.values(): all_idx.extend(v)
    elif isinstance(indices, list):
        all_idx = indices

    if all_idx and 0 <= all_idx[0] < st.session_state["_df_len"]:
        st.session_state["selected_idx"] = all_idx[0]
    else:
        st.session_state["selected_idx"] = None


# --- 4. MAP ---
selected_idx = st.session_state["selected_idx"]
if selected_idx is not None and selected_idx >= len(df_filtered):
    selected_idx = None


def render_map(data, sel_idx):
    if data.empty:
        view_state = pdk.ViewState(latitude=-15.78, longitude=-47.93, zoom=4, pitch=0)
        return pdk.Deck(initial_view_state=view_state)

    display = data.copy()
    display['fill_color'] = display['base_color']
    display['point_radius'] = 15000
    if sel_idx is not None and 0 <= sel_idx < len(display):
        display['fill_color'] = display['base_color'].apply(lambda c: [c[0], c[1], c[2], 70])
        display.at[sel_idx, 'fill_color'] = [255, 255, 255, 255]
        display.at[sel_idx, 'point_radius'] = 32000

    view_state = pdk.ViewState(
        latitude=data['latitude'].mean(),
        longitude=data['longitude'].mean(),
        zoom=4, pitch=0,
    )

    layer = pdk.Layer(
        "ScatterplotLayer", display,
        get_position='[longitude, latitude]',
        get_fill_color='fill_color',
        get_radius='point_radius',
        pickable=True, auto_highlight=True, radius_min_pixels=6,
    )

    tooltip_html = "<b>Location:</b> {municipio}<br/><b>Condition:</b> {condicao_da_lavoura}"
    if "produtividade_estimada_clculo_automtico_kghectare" in data.columns:
        tooltip_html += "<br/><b>Yield:</b> {produtividade_estimada_clculo_automtico_kghectare} kg/ha"

    return pdk.Deck(layers=[layer], initial_view_state=view_state, tooltip={
        "html": tooltip_html,
        "style": {"backgroundColor": "#1a1a2e", "color": "white", "borderRadius": "8px"}
    })


st.subheader("Spatial Visualization")
st.pydeck_chart(render_map(df_filtered, selected_idx), on_select=on_map_select, selection_mode="single-object",
                key="pydeck_map")

# --- 5. DETAILS (FORMATTING RESTORED) ---
st.divider()
if selected_idx is not None and selected_idx < len(df_filtered):
    selected_row = df_filtered.iloc[selected_idx]

    badge_colors = {
        "1. Muito Ruim": "#8B0000", "2. Ruim": "#E74C3C", "3. Media": "#F1C40F",
        "4. Boa": "#2ECC71", "5. Excelente": "#8E44AD", "Sem Info": "#808080"
    }
    condition_val = selected_row.get('condicao_da_lavoura', 'Sem Info')
    color = badge_colors.get(condition_val, "#888")

    st.markdown('<div class="detail-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 1])

    with c1:
        location = selected_row.get('municipio', selected_row.get('localidade_', 'Unknown'))
        st.markdown(f"""
            <div style="background:{color}22;border-left:4px solid {color};padding:12px;border-radius:6px;margin-bottom:15px;">
                <span style="font-weight:700;font-size:18px;">📍 Sample ID {int(selected_row['ID'])}</span><br/>
                <span style="font-size:14px;opacity:0.8;">{location}</span>
            </div>
        """, unsafe_allow_html=True)

        if 'condicao_da_lavoura' in selected_row.index:
            st.markdown(f"**Condition:** `{selected_row['condicao_da_lavoura']}`")
        if 'estadio_fenologico' in selected_row.index:
            st.markdown(f"**Growth Stage:** `{selected_row['estadio_fenologico']}`")

        yield_val = selected_row.get('graosha_k', selected_row.get('produtividade_estimada_clculo_automtico_kghectare'))
        if yield_val:
            try:
                st.markdown(f"**Estimated Yield:** `{float(yield_val):.2f} kg/ha`")
            except:
                st.markdown("**Estimated Yield:** Not available")
        else:
            st.markdown("**Estimated Yield:** Not available")

        obs_raw = selected_row.get("observacoes", "")
        obs = "No observations available." if pd.isna(obs_raw) or str(obs_raw).strip() in ["", "nan"] else str(
            obs_raw).strip()
        st.markdown(f"""
            <div style="margin-top:20px; padding:10px; background:#1a1a2e; border-radius:5px; border-left: 3px solid #4a4a8a;">
                <small style="color:#888; text-transform:uppercase;">Notes</small><br/>
                <span style="font-size:14px; color:#ddd;">{obs}</span>
            </div>
        """, unsafe_allow_html=True)

    with c2:
        # Collect photos from different columns depending on crop
        all_foto_ids = []

        # For soja
        if "fotos" in selected_row.index:
            fotos_raw = str(selected_row.get("fotos", ""))
            all_foto_ids.extend([id.strip() for id in fotos_raw.split(",") if id.strip() not in ["nan", ""]])

        # For safrinha
        for col in ["fotos_das_espigas_cap_do_carro", "foto_das_linhas", "fotos_adicionais"]:
            if col in selected_row.index:
                fotos_raw = str(selected_row.get(col, ""))
                all_foto_ids.extend([id.strip() for id in fotos_raw.split(",") if id.strip() not in ["nan", ""]])

        foto_paths = [image_index.get(id) for id in all_foto_ids]
        valid_fotos = [(id, path) for id, path in zip(all_foto_ids, foto_paths) if path]

        if valid_fotos:
            if len(valid_fotos) > 1:
                tabs = st.tabs([f"Photo {i + 1}" for i in range(len(valid_fotos))])
                for tab, (f_id, f_path) in zip(tabs, valid_fotos):
                    with tab: st.image(f_path, width='stretch', caption=f"Photo ID: {f_id}")
            else:
                st.image(valid_fotos[0][1], width='stretch', caption=f"Sample Photo")
        else:
            st.info("📷 No photos found for this sample.")
    st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("🗺️ Select a point on the map to view detailed field information and photos.")