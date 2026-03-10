import streamlit as st
import pandas as pd
import pydeck as pdk
from pathlib import Path

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(layout="wide", page_title="Crop Tour Soja - Performance Mode")

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

st.title("Mapa de Amostragem: Crop Tour Soja 2026")

FOTOS_DIR = Path("fotos")


# --- 1. DADOS ---
@st.cache_data
def load_data():
    df = pd.read_csv("crop_tour_soja.csv")
    df.columns = df.columns.str.strip()
    df = df.rename(columns={'_latitude': 'latitude', '_longitude': 'longitude', 'localidade': 'localidade_'})

    # Mantém apenas quem tem coordenadas (obrigatório para o mapa)
    df = df.dropna(subset=['latitude', 'longitude'])

    # --- TRATAMENTO ROBUSTO PARA ESPAÇOS E "SEM INFORMAÇÃO" ---
    # O regex r'\s+' transforma qualquer espaço duplo ou invisível no meio do texto em 1 espaço normal
    df['condicao_da_lavoura'] = (
        df['condicao_da_lavoura']
        .fillna("Sem Info")
        .astype(str)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
        .replace(["nan", "None", "", "Nan", "NaN"], "Sem Info")
    )

    df['estadio_fenologico'] = (
        df['estadio_fenologico']
        .fillna("Sem Info")
        .astype(str)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
        .replace(["nan", "None", "", "Nan", "NaN"], "Sem Info")
    )

    color_map = {
        "1. Muito Ruim": [139, 0, 0, 230],
        "2. Ruim": [231, 76, 60, 230],  # Laranja avermelhado
        "3. Media": [241, 196, 15, 230],
        "4. Boa": [46, 204, 113, 230],
        "5. Excelente": [142, 68, 173, 230],
        "Sem Info": [128, 128, 128, 160],  # Cinza
    }

    # Atribui a cor
    df['base_color'] = df['condicao_da_lavoura'].apply(
        lambda x: color_map.get(x, color_map["Sem Info"])
    )

    df.insert(0, 'ID', range(1, len(df) + 1))
    return df


@st.cache_resource(ttl=300)  # Remapeia a cada 5 minutos
def get_image_index():
    index = {}
    if not FOTOS_DIR.exists():
        return index
    for path in FOTOS_DIR.glob("*"):
        if path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            index[path.stem] = str(path)
    return index


df = load_data()
image_index = get_image_index()

# --- 2. SIDEBAR ---
st.sidebar.markdown("### Legenda - Condição")
st.sidebar.markdown("""
- 🔴 **1. Muito Ruim**\n- 🟠 **2. Ruim**\n- 🟡 **3. Media**\n- 🟢 **4. Boa**\n- 🟣 **5. Excelente** \n- ⚪ **Sem Informação**
""")
st.sidebar.header("Filtros de Safra")

opcoes_condicao = sorted(df["condicao_da_lavoura"].unique())
condition = st.sidebar.multiselect(
    "Condição da Lavoura:",
    options=opcoes_condicao,
    default=opcoes_condicao
)

opcoes_estadios = sorted(df["estadio_fenologico"].unique())
stages = st.sidebar.multiselect(
    "Estádio Fenológico:",
    options=opcoes_estadios,
    default=opcoes_estadios
)

df_filtered = df[
    (df["condicao_da_lavoura"].isin(condition)) &
    (df["estadio_fenologico"].isin(stages))
    ].copy().reset_index(drop=True)

st.sidebar.divider()
st.sidebar.metric("Amostras Filtradas", len(df_filtered))

# --- 3. SESSION STATE ---
if "selected_idx" not in st.session_state:
    st.session_state["selected_idx"] = None

st.session_state["_df_len"] = len(df_filtered)


def on_map_select():
    raw = st.session_state.get("pydeck_map")
    if not raw:
        st.session_state["selected_idx"] = None
        return

    indices = raw.get("selection", {}).get("indices", {})
    all_idx = []
    if isinstance(indices, dict):
        for v in indices.values():
            all_idx.extend(v)
    elif isinstance(indices, list):
        all_idx = indices

    df_len = st.session_state.get("_df_len", 0)
    if all_idx and 0 <= all_idx[0] < df_len:
        st.session_state["selected_idx"] = all_idx[0]
    else:
        st.session_state["selected_idx"] = None


# --- 4. MAPA ---
selected_idx = st.session_state["selected_idx"]

if selected_idx is not None and selected_idx >= len(df_filtered):
    selected_idx = None
    st.session_state["selected_idx"] = None


def build_display_data(data, sel_idx):
    display = data.copy()
    if sel_idx is not None and 0 <= sel_idx < len(display):
        display['fill_color'] = display['base_color'].apply(lambda c: [c[0], c[1], c[2], 70])
        display['point_radius'] = 15000
        display.at[sel_idx, 'fill_color'] = [255, 255, 255, 255]
        display.at[sel_idx, 'point_radius'] = 32000
    else:
        display['fill_color'] = display['base_color']
        display['point_radius'] = 15000
    return display


def render_map(data, sel_idx):
    display = build_display_data(data, sel_idx)

    view_state = pdk.ViewState(
        latitude=data['latitude'].mean() if not data.empty else -15.78,
        longitude=data['longitude'].mean() if not data.empty else -47.93,
        zoom=4, pitch=0,
    )

    layer = pdk.Layer(
        "ScatterplotLayer",
        display,
        get_position='[longitude, latitude]',
        get_fill_color='fill_color',
        get_radius='point_radius',
        pickable=True,
        auto_highlight=True,
        highlight_color=[255, 255, 255, 60],
        radius_min_pixels=6,
    )

    tooltip = {
        "html": """
            <div style="font-family:sans-serif;font-size:13px;line-height:1.7">
                <b style="font-size:15px">📍 {localidade_}</b><br/>
                <span style="opacity:.75">ID:</span> <b>{ID}</b><br/>
                <span style="opacity:.75">Condição:</span> <b>{condicao_da_lavoura}</b><br/>
                <span style="opacity:.75">Estádio:</span> <b>{estadio_fenologico}</b><br/>
                <span style="opacity:.75">Produtividade:</span> <b>{graosha_k} K grãos/ha</b>
            </div>
        """,
        "style": {
            "backgroundColor": "#1a1a2e",
            "color": "white",
            "border": "1px solid #4a4a8a",
            "borderRadius": "8px",
            "padding": "10px",
        }
    }

    return pdk.Deck(layers=[layer], initial_view_state=view_state, map_style=None, tooltip=tooltip)


st.subheader("Visualização Espacial")
st.caption("Passe o mouse para ver detalhes • Clique para fixar a amostra")

st.pydeck_chart(
    render_map(df_filtered, selected_idx),
    on_select=on_map_select,
    selection_mode="single-object",
    width='stretch',
    key="pydeck_map",
)

# --- 5. DOWNLOAD ---
st.divider()
csv = df_filtered.to_csv(index=False).encode('utf-8')
st.download_button("⬇️ Baixar Dados Filtrados (CSV)", csv, "crop_tour.csv", "text/csv")

# --- 6. DETALHES ---
st.divider()
st.markdown('<div id="detail-anchor"></div>', unsafe_allow_html=True)

selected_row = None
if selected_idx is not None and 0 <= selected_idx < len(df_filtered):
    selected_row = df_filtered.iloc[selected_idx]

if selected_row is not None:
    st.markdown("""
        <script>
            document.getElementById('detail-anchor')?.scrollIntoView({behavior:'smooth', block:'start'});
        </script>
    """, unsafe_allow_html=True)

    badge_colors = {
        "1. Muito Ruim": "#8B0000",
        "2. Ruim": "#E74C3C",
        "3. Media": "#F1C40F",
        "4. Boa": "#2ECC71",
        "5. Excelente": "#8E44AD",
        "Sem Info": "#808080",
    }

    cond = selected_row['condicao_da_lavoura']
    color = badge_colors.get(cond, "#888")

    with st.spinner("Carregando detalhes..."):
        st.markdown('<div class="detail-card">', unsafe_allow_html=True)
        c1, c2 = st.columns([1, 1])

        with c1:
            st.markdown(f"""
                <div style="background:{color}22;border-left:4px solid {color};
                            border-radius:6px;padding:12px 16px;margin-bottom:12px;">
                    <span style="font-size:18px;font-weight:700">📍 Amostra ID {int(selected_row['ID'])}</span><br/>
                    <span style="font-size:13px;opacity:.8">{selected_row['localidade_']}</span>
                </div>
            """, unsafe_allow_html=True)
            st.markdown(f"**Condição:** `{cond}`")
            st.markdown(f"**Estádio Fenológico:** `{selected_row['estadio_fenologico']}`")

            # Evita erro caso 'graosha_k' seja nulo
            prod_val = selected_row.get('graosha_k', 0)
            st.markdown(f"**Produtividade:** `{prod_val:.2f}K grãos/ha`")

        with c2:
            foto_ids = [id.strip() for id in str(selected_row.get("fotos", "")).split(",") if id.strip() != "nan"]
            foto_paths = [image_index.get(id) for id in foto_ids]
            fotos_validas = [(id, path) for id, path in zip(foto_ids, foto_paths) if path]

            if fotos_validas:
                if len(fotos_validas) > 1:
                    tabs = st.tabs([f"Foto {i + 1}" for i in range(len(fotos_validas))])
                    for tab, (foto_id, foto_path) in zip(tabs, fotos_validas):
                        with tab:
                            st.image(foto_path, caption=f"Foto {foto_id}", width='stretch')
                else:
                    st.image(fotos_validas[0][1], caption=f"Foto da Amostra {int(selected_row['ID'])}", width='stretch')
            else:
                st.markdown("""
                    <div style="background:#1e1e1e;border-radius:8px;height:200px;
                                display:flex;align-items:center;justify-content:center;
                                color:#666;font-size:14px;">
                        📷 Foto não disponível
                    </div>
                """, unsafe_allow_html=True)

            obs_raw = selected_row.get("observacoes", None)
            obs = (
                "Sem observações"
                if pd.isna(obs_raw) or str(obs_raw).strip() in ["", "nan", "None"]
                else str(obs_raw).strip()
            )
            st.markdown(f"""
                <div style="margin-top:12px;background:#1a1a2e;border-left:3px solid #4a4a8a;
                            border-radius:6px;padding:10px 14px;font-size:13px;color:#ccc;">
                    <span style="font-weight:600;color:#888;font-size:11px;text-transform:uppercase;
                                 letter-spacing:.6px;">💬 Observações</span><br/>
                    <span style="color:{'#666' if obs == 'Sem observações' else '#eee'};
                                 font-style:{'italic' if obs == 'Sem observações' else 'normal'};">
                        {obs}
                    </span>
                </div>
            """, unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

else:
    st.markdown("""
        <div style="text-align:center;padding:32px;background:#0e1117;
                    border-radius:10px;border:1px dashed #333;color:#666;">
            🗺️ <b>Clique em um ponto no mapa</b> para ver os detalhes da amostra
        </div>
    """, unsafe_allow_html=True)

# --- 7. TABELA ---
with st.expander("Visualizar Tabela de Dados Completa"):
    st.dataframe(df_filtered, width='stretch')