import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.subplots as sp
from sqlalchemy import create_engine
import pytz
import datetime
import time

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Suivi Crypto", layout="wide")

# --- STYLE CSS ---
st.markdown("""
<style>
/* Style général pour la sidebar et les alertes */

/* Conteneur pour les boutons toggle dans la sidebar */
div.crypto-btn-container {
    display: flex;
    gap: 10px;
    margin-bottom: 15px;
}

/* On force les boutons à occuper 100% de la largeur de leur colonne */
div.crypto-btn-container > div {
    flex: 1;
}

/* Style de base pour les boutons de sélection */
div.crypto-btn-container button {
    width: 100%;
    border: none;
    border-radius: 5px;
    padding: 5px 10px;
    font-weight: bold;
    color: white !important;
}

/* Attribution des couleurs en fonction de l'ordre des colonnes */
div.crypto-btn-container > div:nth-child(1) button {
    background-color: #F7931A !important;  /* BTC */
}
div.crypto-btn-container > div:nth-child(2) button {
    background-color: #627EEA !important;  /* ETH */
}
div.crypto-btn-container > div:nth-child(3) button {
    background-color: #346AA9 !important;  /* XRP */
}

/* Style des alertes de volatilité : fond assombri */
.alert-card {
    border: 1px solid #555;
    padding: 10px;
    margin-bottom: 10px;
    border-radius: 5px;
    background-color: #2c2c2c; /* fond sombre */
    color: #ffffff;
}
</style>
""", unsafe_allow_html=True)

st.title("📊 Suivi des prix cryptomonnaies")

# --- CONSTANTES ET CONFIGURATION ---
DATABASE_URL = st.secrets["database"]["url"]

# Dictionnaire des couleurs (pour référence)
crypto_colors = {
    "BTC": "#F7931A",  # Bitcoin en orange
    "ETH": "#627EEA",  # Ethereum en bleu
    "XRP": "#346AA9"   # Ripple en bleu foncé
}

def get_database_engine():
    try:
        return create_engine(DATABASE_URL)
    except Exception as e:
        st.error("Erreur lors de la connexion à la base de données.")
        st.exception(e)
        return None

@st.cache_data(ttl=300, show_spinner=True)
def fetch_data():
    engine = get_database_engine()
    if engine:
        query = "SELECT * FROM prices"
        return pd.read_sql_query(query, engine)
    return pd.DataFrame()

def process_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    try:
        df["timestamp"] = df["timestamp"].dt.tz_localize("Europe/Paris", ambiguous="NaT")
    except Exception:
        pass
    tz_paris = pytz.timezone("Europe/Paris")
    current_offset = tz_paris.utcoffset(datetime.datetime.now())
    df["timestamp_local"] = df["timestamp"] + current_offset
    df["timestamp_str"] = df["timestamp_local"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df["price_change"] = df.groupby("crypto")["price"].pct_change() * 100
    return df

def plot_crypto_subplots(df: pd.DataFrame, selected_cryptos: list) -> go.Figure:
    df_filtered = df[df["crypto"].isin(selected_cryptos)]
    nb = len(selected_cryptos)
    fig = sp.make_subplots(rows=nb, cols=1, shared_xaxes=True,
                           vertical_spacing=0.08,
                           subplot_titles=[f"Évolution du prix {c}" for c in selected_cryptos])
    for i, c in enumerate(selected_cryptos, start=1):
        df_c = df_filtered[df_filtered["crypto"] == c]
        fig.add_trace(go.Scatter(x=df_c["timestamp_str"], y=df_c["price"],
                                 mode='lines+markers', name=c), row=i, col=1)
        fig.update_yaxes(title_text="Prix (USD)", row=i, col=1)
    fig.update_layout(height=600 * nb, showlegend=False, template="plotly_dark",
                      title_text=f"Évolution des prix ({', '.join(selected_cryptos)})")
    fig.update_xaxes(title_text="Temps", row=nb, col=1)
    return fig

def display_alerts(df: pd.DataFrame, selected_cryptos: list, threshold: float):
    st.subheader("⚠️ Alertes de volatilité")
    volatile = df[(df["crypto"].isin(selected_cryptos)) & (df["price_change"].abs() > threshold)]
    if not volatile.empty:
        # Tri pour afficher les alertes récentes en premier
        volatile = volatile.sort_values(["crypto", "timestamp_local"], ascending=[True, False])
        for _, row in volatile.iterrows():
            crypto = row["crypto"]
            # Calcul du prix précédent à partir de la variation
            if row["price_change"] != -100:
                previous_price = row["price"] / (1 + row["price_change"] / 100)
            else:
                previous_price = row["price"]
            variation_color = "green" if row["price_change"] > 0 else "red"
            st.markdown(
                f"""
                <div class="alert-card">
                    <div style="display:flex; align-items:center; margin-bottom:8px;">
                        <div style="background-color:{crypto_colors.get(crypto, '#000')}; color:white; border-radius:5px; padding:5px 10px; font-weight:bold; margin-right:10px;">
                            {crypto}
                        </div>
                        <div style="font-size:16px; font-weight:bold;">{row['timestamp_str']}</div>
                    </div>
                    <div style="font-size:14px;">
                        <div>Prix Précédent : <strong>{previous_price:.2f} USD</strong></div>
                        <div>Prix Actuel : <strong>{row['price']:.2f} USD</strong></div>
                        <div>Variation : <strong style="color:{variation_color};">{row['price_change']:.2f}%</strong></div>
                    </div>
                </div>
                """, unsafe_allow_html=True
            )
    else:
        st.info("Aucune alerte de volatilité détectée.")

# --- CHARGEMENT ET TRAITEMENT DES DONNÉES ---
df = fetch_data()
df = process_data(df)
if df.empty:
    st.error("Aucune donnée disponible.")
    st.stop()

# --- BARRE LATÉRALE ---
st.sidebar.title("Configuration")

# --- Boutons toggle pour la sélection des cryptomonnaies ---
# On utilise st.session_state pour mémoriser la sélection.
if "selected_cryptos" not in st.session_state:
    st.session_state.selected_cryptos = []  # initialement vide : si rien n'est sélectionné, on affiche toutes les cryptos

def toggle_crypto(crypto: str):
    if crypto in st.session_state.selected_cryptos:
        st.session_state.selected_cryptos.remove(crypto)
    else:
        st.session_state.selected_cryptos.append(crypto)

st.sidebar.markdown("### Sélection rapide")

# Création d'un conteneur HTML pour les boutons afin de les afficher en ligne
st.sidebar.markdown('<div class="crypto-btn-container">', unsafe_allow_html=True)
cols = st.sidebar.columns(len(crypto_colors))
for idx, crypto in enumerate(sorted(crypto_colors.keys())):
    selected = crypto in st.session_state.selected_cryptos
    label = f"{crypto}" if not selected else f"✅ {crypto}"
    # Chaque bouton est placé dans sa colonne pour un affichage en ligne
    if cols[idx].button(label, key=f"btn_{crypto}", on_click=toggle_crypto, args=(crypto,)):
        pass
st.sidebar.markdown("</div>", unsafe_allow_html=True)

# --- Filtres supplémentaires ---
date_min = df["timestamp_local"].min().date()
date_max = df["timestamp_local"].max().date()
date_range = st.sidebar.date_input("Plage de dates", [date_min, date_max])
if date_range and len(date_range) == 2:
    start_date, end_date = date_range
    df = df[(df["timestamp_local"].dt.date >= start_date) & (df["timestamp_local"].dt.date <= end_date)]
alert_threshold = st.sidebar.number_input("Seuil d'alerte (%)", min_value=0.0, value=5.0, step=0.5)

# --- Bouton Rafraîchir placé en bas de la sidebar ---
st.sidebar.markdown("---")
if st.sidebar.button("Rafraîchir"):
    st.cache_data.clear()
    st.query_params.rerun = str(time.time())

# --- SÉLECTION DES CRYPTOS ---
# Si aucune crypto n'est sélectionnée, on affiche toutes les cryptos par défaut.
if not st.session_state.selected_cryptos:
    selected_cryptos = list(crypto_colors.keys())
else:
    selected_cryptos = st.session_state.selected_cryptos

# --- AFFICHAGE DES INDICATEURS ---
st.markdown(f"**Dernière mise à jour :** {df['timestamp_str'].max()}")
cols_metrics = st.columns(len(selected_cryptos))
for i, crypto in enumerate(selected_cryptos):
    df_crypto = df[df["crypto"] == crypto].sort_values("timestamp_local")
    if not df_crypto.empty:
        latest = df_crypto.iloc[-1]
        previous = df_crypto.iloc[-2] if len(df_crypto) > 1 else latest
        variation = ((latest["price"] - previous["price"]) / previous["price"]) * 100
        cols_metrics[i].metric(label=f"{crypto} - Prix actuel (USD)", value=f"{latest['price']:.2f}",
                               delta=f"{variation:.2f}%")

# --- AFFICHAGE DU GRAPHIQUE ---
if selected_cryptos:
    fig = plot_crypto_subplots(df, selected_cryptos)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Veuillez sélectionner au moins une cryptomonnaie.")

# --- AFFICHAGE DES ALERTES ---
display_alerts(df, selected_cryptos, alert_threshold)