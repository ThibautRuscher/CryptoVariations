import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.subplots as sp
from sqlalchemy import create_engine
import pytz
import datetime
from typing import Dict, List

# --- CONFIGURATION DE LA PAGE ---
st.set_page_config(page_title="Suivi Crypto", layout="wide")

# --- STYLE CSS ---
st.markdown("""
<style>
/* Style général */
div.crypto-btn-container {
    display: flex;
    gap: 10px;
    margin-bottom: 15px;
}

div.crypto-btn-container > div {
    flex: 1;
}

div.crypto-btn-container button {
    width: 100%;
    border: none;
    border-radius: 5px;
    padding: 5px 10px;
    font-weight: bold;
    color: white !important;
}

/* Couleurs des boutons selon la crypto */
div.crypto-btn-container > div:nth-child(1) button {
    background-color: #F7931A !important;
}
div.crypto-btn-container > div:nth-child(2) button {
    background-color: #627EEA !important;
}
div.crypto-btn-container > div:nth-child(3) button {
    background-color: #346AA9 !important;
}

/* Pour distinguer visuellement une crypto sélectionnée */
div.crypto-btn-container button.selected {
    border: 2px solid #ffffff;
}

/* Styles pour les alertes et les cartes de stats */
.alert-card {
    border: 1px solid #555;
    padding: 15px;
    margin-bottom: 15px;
    border-radius: 8px;
    background-color: #2c2c2c;
    color: #ffffff;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.stat-card {
    background-color: #1e1e1e;
    padding: 15px;
    border-radius: 8px;
    margin: 10px 0;
    border: 1px solid #333;
}

.alert-significance {
    background-color: #444;
    padding: 5px 10px;
    border-radius: 4px;
    margin-top: 5px;
    font-size: 0.9em;
}
</style>
""", unsafe_allow_html=True)

# --- CONSTANTES ET CONFIGURATION ---
DATABASE_URL = st.secrets["database"]["url"]
CRYPTO_COLORS = {
    "BTC": "#F7931A",
    "ETH": "#627EEA",
    "XRP": "#346AA9"
}

# --- FONCTIONS UTILITAIRES ---
def get_database_engine():
    try:
        return create_engine(DATABASE_URL)
    except Exception as e:
        st.error("❌ Erreur de connexion à la base de données")
        st.exception(e)
        return None

@st.cache_data(ttl=300)
def fetch_price_data() -> pd.DataFrame:
    with st.spinner("Chargement des données de prix..."):
        engine = get_database_engine()
        if engine:
            try:
                return pd.read_sql_query("SELECT * FROM prices", engine)
            except Exception as e:
                st.error("❌ Erreur lors de la récupération des données")
                st.exception(e)
                return pd.DataFrame()
    return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_stats_data() -> pd.DataFrame:
    with st.spinner("Chargement des statistiques..."):
        engine = get_database_engine()
        if engine:
            try:
                return pd.read_sql_query("SELECT * FROM stats", engine)
            except Exception as e:
                st.error("❌ Erreur lors de la récupération des statistiques")
                st.exception(e)
                return pd.DataFrame()
    return pd.DataFrame()

@st.cache_data(ttl=300)
def fetch_alerts_data() -> pd.DataFrame:
    with st.spinner("Chargement des alertes..."):
        engine = get_database_engine()
        if engine:
            try:
                return pd.read_sql_query("SELECT * FROM alerts", engine)
            except Exception as e:
                st.error("❌ Erreur lors de la récupération des alertes")
                st.exception(e)
                return pd.DataFrame()
    return pd.DataFrame()

def process_price_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # S'assurer que le timestamp est au bon fuseau horaire
    if df["timestamp"].dt.tz is None:
        tz_paris = pytz.timezone("Europe/Paris")
        df["timestamp"] = df["timestamp"].dt.tz_localize(tz_paris, ambiguous="NaT")

    # Créer une version locale du timestamp pour l'affichage
    df["timestamp_local"] = df["timestamp"]
    df["timestamp_str"] = df["timestamp_local"].dt.strftime("%Y-%m-%d %H:%M:%S")

    return df

def process_stats_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # S'assurer que le timestamp est au bon fuseau horaire
    if df["timestamp"].dt.tz is None:
        tz_paris = pytz.timezone("Europe/Paris")
        df["timestamp"] = df["timestamp"].dt.tz_localize(tz_paris, ambiguous="NaT")

    df["timestamp_str"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df

def process_alerts_data(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # S'assurer que le timestamp est au bon fuseau horaire
    if df["timestamp"].dt.tz is None:
        tz_paris = pytz.timezone("Europe/Paris")
        df["timestamp"] = df["timestamp"].dt.tz_localize(tz_paris, ambiguous="NaT")

    df["timestamp_str"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    return df

def get_latest_stats(df: pd.DataFrame, crypto: str) -> Dict:
    df_crypto = df[df["crypto"] == crypto].sort_values("timestamp")
    if df_crypto.empty:
        return {
            "prix_actuel": 0,
            "variation_24h": 0,
            "plus_haut_24h": 0,
            "plus_bas_24h": 0,
            "volatilite": 0
        }

    latest = df_crypto.iloc[-1]
    return {
        "prix_actuel": latest["current_price"],
        "variation_24h": latest["price_change_24h_pct"],
        "plus_haut_24h": latest["high_24h"],
        "plus_bas_24h": latest["low_24h"],
        "volatilite": latest["volume_5min"]
    }

# --- COMPOSANTS UI ---
def render_metrics_dashboard(stats_df: pd.DataFrame, selected_cryptos: List[str]):
    st.subheader("📊 Statistiques globales")
    cols = st.columns(len(selected_cryptos))

    for i, crypto in enumerate(selected_cryptos):
        stats = get_latest_stats(stats_df, crypto)
        with cols[i]:
            st.markdown(f"""
            <div class="stat-card">
                <h3 style="color: {CRYPTO_COLORS[crypto]};">{crypto}</h3>
                <p>Prix: ${stats['prix_actuel']:.2f}</p>
                <p>Variation 24h: {stats['variation_24h']:.2f}%</p>
                <p>Plus haut 24h: ${stats['plus_haut_24h']:.2f}</p>
                <p>Plus bas 24h: ${stats['plus_bas_24h']:.2f}</p>
            </div>
            """, unsafe_allow_html=True)

def render_price_chart(df: pd.DataFrame, selected_cryptos: List[str]):
    st.subheader("📈 Évolution des prix")

    # Sélecteur de période
    timeframe = st.radio(
        "Période d'affichage",
        ["24 heures", "7 jours", "30 jours", "Tout"],
        horizontal=True
    )

    # Filtrer les données selon la période sélectionnée
    now = df["timestamp_local"].max()
    if timeframe == "24 heures":
        df_filtered = df[df["timestamp_local"] > (now - pd.Timedelta(days=1))]
    elif timeframe == "7 jours":
        df_filtered = df[df["timestamp_local"] > (now - pd.Timedelta(days=7))]
    elif timeframe == "30 jours":
        df_filtered = df[df["timestamp_local"] > (now - pd.Timedelta(days=30))]
    else:
        df_filtered = df

    fig = sp.make_subplots(
        rows=len(selected_cryptos),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=[f"Évolution du prix {c}" for c in selected_cryptos]
    )

    for i, crypto in enumerate(selected_cryptos, start=1):
        df_crypto = df_filtered[df_filtered["crypto"] == crypto]
        fig.add_trace(
            go.Scatter(
                x=df_crypto["timestamp_str"],
                y=df_crypto["price"],
                mode='lines',
                name=crypto,
                connectgaps=False,
                line=dict(color=CRYPTO_COLORS[crypto], width=1.5),
                hovertemplate="<b>%{x}</b><br>" +
                              "Prix: $%{y:.2f}<br>" +
                              "<extra></extra>"
            ),
            row=i, col=1
        )
        fig.update_yaxes(title_text="Prix (USD)", row=i, col=1)

    fig.update_layout(
        height=300 * len(selected_cryptos),
        showlegend=False,
        template="plotly_dark",
        margin=dict(l=50, r=50, t=50, b=50)
    )

    st.plotly_chart(fig, use_container_width=True)

def render_alerts(alerts_df: pd.DataFrame, selected_cryptos: List[str]):
    st.subheader("⚠️ Alertes de volatilité")

    if alerts_df.empty:
        st.info("Aucune alerte de volatilité détectée.")
        return

    # Filtrer les alertes par crypto sélectionnées
    filtered_alerts = alerts_df[alerts_df["crypto"].isin(selected_cryptos)]

    if filtered_alerts.empty:
        st.info("Aucune alerte pour les cryptomonnaies sélectionnées.")
        return

    # Trier par timestamp décroissant
    filtered_alerts = filtered_alerts.sort_values("timestamp", ascending=False)

    for _, alert in filtered_alerts.iterrows():
        variation_color = "green" if alert["price_change_pct"] > 0 else "red"
        st.markdown(f"""
        <div class="alert-card">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="background-color:{CRYPTO_COLORS[alert['crypto']]}; padding:5px 10px; border-radius:5px;">
                    {alert['crypto']}
                </span>
                <span>Détectée le {alert['timestamp_str']}</span>
            </div>
            <div style="margin-top:10px;">
                <p>Prix initial: ${alert['start_price']:.2f}</p>
                <p>Prix final: ${alert['end_price']:.2f}</p>
                <p>Variation: <span style="color:{variation_color}">{alert['price_change_pct']:.2f}%</span></p>
                <div class="alert-significance">
                    Variation observée sur {alert['time_interval']}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- INTERFACE PRINCIPALE ---
def main():
    st.title("Suivi des prix cryptomonnaies")

    # Sidebar configuration
    st.sidebar.title("Configuration")

    # Par défaut, seule la crypto BTC est sélectionnée
    if "selected_cryptos" not in st.session_state:
        st.session_state.selected_cryptos = ["BTC"]

    def toggle_crypto(crypto: str):
        if crypto in st.session_state.selected_cryptos:
            st.session_state.selected_cryptos.remove(crypto)
        else:
            st.session_state.selected_cryptos.append(crypto)

    st.sidebar.markdown("### Sélection des cryptomonnaies")
    st.sidebar.markdown('<div class="crypto-btn-container">', unsafe_allow_html=True)
    cols = st.sidebar.columns(len(CRYPTO_COLORS))
    for idx, crypto in enumerate(sorted(CRYPTO_COLORS.keys())):
        selected = crypto in st.session_state.selected_cryptos
        label = f"✅ {crypto}" if selected else crypto
        if cols[idx].button(label, key=f"btn_{crypto}", on_click=toggle_crypto, args=(crypto,)):
            pass
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # Filtres
    st.sidebar.markdown("### Filtres temporels")

    # Chargement des données
    prices_df = fetch_price_data()
    if prices_df.empty:
        st.error("Aucune donnée de prix disponible.")
        return

    prices_df = process_price_data(prices_df)

    date_range = st.sidebar.date_input(
        "Plage de dates",
        [prices_df["timestamp_local"].min().date(), prices_df["timestamp_local"].max().date()]
    )

    # Filtrage des données par date
    if len(date_range) == 2:
        start_date, end_date = date_range
        # Ajouter un jour à la date de fin pour inclure tout ce jour-là
        end_date = end_date + datetime.timedelta(days=1)
        prices_df = prices_df[
            (prices_df["timestamp_local"].dt.date >= start_date) &
            (prices_df["timestamp_local"].dt.date < end_date)
            ]

    # Bouton de rafraîchissement
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Rafraîchir les données"):
        st.cache_data.clear()
        st.rerun()

    # Sélection des cryptos par défaut (BTC) ou celles cochées par l'utilisateur
    selected_cryptos = st.session_state.selected_cryptos or ["BTC"]

    # Chargement des statistiques et alertes
    stats_df = fetch_stats_data()
    if not stats_df.empty:
        stats_df = process_stats_data(stats_df)

    alerts_df = fetch_alerts_data()
    if not alerts_df.empty:
        alerts_df = process_alerts_data(alerts_df)
        # Filtrage des alertes par date également
        if len(date_range) == 2:
            start_date, end_date = date_range
            end_date = end_date + datetime.timedelta(days=1)
            alerts_df = alerts_df[
                (alerts_df["timestamp"].dt.date >= start_date) &
                (alerts_df["timestamp"].dt.date < end_date)
                ]

    # Interface principale avec onglets
    tab1, tab2 = st.tabs(["Graphiques", "Alertes"])

    with tab1:
        render_metrics_dashboard(stats_df, selected_cryptos)
        render_price_chart(prices_df, selected_cryptos)

    with tab2:
        render_alerts(alerts_df, selected_cryptos)

if __name__ == "__main__":
    main()