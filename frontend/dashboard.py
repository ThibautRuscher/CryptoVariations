import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.subplots as sp
from sqlalchemy import create_engine
import pytz
import datetime
import time
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
def fetch_data() -> pd.DataFrame:
    with st.spinner("Chargement des données..."):
        engine = get_database_engine()
        if engine:
            try:
                return pd.read_sql_query("SELECT * FROM prices", engine)
            except Exception as e:
                st.error("❌ Erreur lors de la récupération des données")
                st.exception(e)
                return pd.DataFrame()
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

    # Calculs supplémentaires
    df["price_change"] = df.groupby("crypto")["price"].pct_change() * 100
    df["price_change_24h"] = df.groupby("crypto")["price"].pct_change(periods=288) * 100  # 288 = 24h (12 * 24)
    df["volume"] = df.groupby("crypto")["price"].rolling(window=12).std().reset_index(0, drop=True)

    return df

def calculate_statistics(df: pd.DataFrame, crypto: str) -> Dict:
    df_crypto = df[df["crypto"] == crypto].sort_values("timestamp_local")
    if df_crypto.empty:
        return {}

    latest_price = df_crypto["price"].iloc[-1]
    price_24h_ago = df_crypto["price"].iloc[-288] if len(df_crypto) >= 288 else df_crypto["price"].iloc[0]
    high_24h = df_crypto["price"].tail(288).max()
    low_24h = df_crypto["price"].tail(288).min()

    return {
        "prix_actuel": latest_price,
        "variation_24h": ((latest_price - price_24h_ago) / price_24h_ago * 100),
        "plus_haut_24h": high_24h,
        "plus_bas_24h": low_24h,
        "volatilite": df_crypto["volume"].iloc[-1]
    }

def calculate_time_difference(timestamp1, timestamp2) -> str:
    diff = timestamp1 - timestamp2
    minutes = int(diff.total_seconds() / 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes > 1 else ''}"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if hours < 24:
        return f"{hours}h{remaining_minutes:02d}"
    days = hours // 24
    remaining_hours = hours % 24
    return f"{days}j {remaining_hours}h{remaining_minutes:02d}"

# --- COMPOSANTS UI ---
def render_metrics_dashboard(df: pd.DataFrame, selected_cryptos: List[str]):
    st.subheader("📊 Statistiques globales")
    cols = st.columns(len(selected_cryptos))

    for i, crypto in enumerate(selected_cryptos):
        stats = calculate_statistics(df, crypto)
        if stats:
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
        marker_size = 6
    elif timeframe == "7 jours":
        df_filtered = df[df["timestamp_local"] > (now - pd.Timedelta(days=7))]
        marker_size = 4
    elif timeframe == "30 jours":
        df_filtered = df[df["timestamp_local"] > (now - pd.Timedelta(days=30))]
        marker_size = 2
    else:
        df_filtered = df
        marker_size = 1

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

def render_alerts(df: pd.DataFrame, selected_cryptos: List[str], threshold: float):
    st.subheader("⚠️ Alertes de volatilité")

    # Trouver les variations significatives
    volatile_events = []
    for crypto in selected_cryptos:
        df_crypto = df[df["crypto"] == crypto].sort_values("timestamp_local")
        for i in range(1, len(df_crypto)):
            current_row = df_crypto.iloc[i]
            if abs(current_row["price_change"]) > threshold:
                prev_row = df_crypto.iloc[i-1]
                time_diff = calculate_time_difference(
                    current_row["timestamp_local"],
                    prev_row["timestamp_local"]
                )
                volatile_events.append({
                    "crypto": crypto,
                    "start_time": prev_row["timestamp_local"],
                    "start_time_str": prev_row["timestamp_str"],
                    "end_time": current_row["timestamp_local"],
                    "end_time_str": current_row["timestamp_str"],
                    "price": current_row["price"],
                    "prev_price": prev_row["price"],
                    "price_change": current_row["price_change"],
                    "time_diff": time_diff
                })

    if volatile_events:
        # Trier par timestamp décroissant
        volatile_events.sort(key=lambda x: x["end_time"], reverse=True)

        for event in volatile_events:
            variation_color = "green" if event["price_change"] > 0 else "red"
            st.markdown(f"""
            <div class="alert-card">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="background-color:{CRYPTO_COLORS[event['crypto']]}; padding:5px 10px; border-radius:5px;">
                        {event['crypto']}
                    </span>
                    <span>De {event['start_time_str']} à {event['end_time_str']}</span>
                </div>
                <div style="margin-top:10px;">
                    <p>Prix initial: ${event['prev_price']:.2f}</p>
                    <p>Prix final: ${event['price']:.2f}</p>
                    <p>Variation: <span style="color:{variation_color}">{event['price_change']:.2f}%</span></p>
                    <div class="alert-significance">
                        Variation observée sur {event['time_diff']}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Aucune alerte de volatilité détectée avec les critères actuels.")

# --- INTERFACE PRINCIPALE ---
def main():
    st.title("Suivi des prix cryptomonnaies")

    # Chargement des données
    df = fetch_data()
    if df.empty:
        st.error("Aucune donnée disponible.")
        return

    df = process_data(df)

    # Sidebar
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
        # Utilisation de l'emoji "✅" pour les cryptos sélectionnées
        label = f"✅ {crypto}" if selected else crypto
        # On ajoute une classe CSS "selected" si la crypto est cochée
        button_html = f'<div><button class="{"selected" if selected else ""}">{label}</button></div>'
        # On utilise st.markdown pour injecter le HTML et on déclenche le toggle au clic via st.button classique
        if cols[idx].button(label, key=f"btn_{crypto}", on_click=toggle_crypto, args=(crypto,)):
            pass
    st.sidebar.markdown("</div>", unsafe_allow_html=True)

    # Filtres
    st.sidebar.markdown("### Filtres")
    date_range = st.sidebar.date_input(
        "Plage de dates",
        [df["timestamp_local"].min().date(), df["timestamp_local"].max().date()]
    )

    alert_threshold = st.sidebar.number_input(
        "Seuil d'alerte sur 5 minutes (%)",
        min_value=0.0,
        value=2.0,  # Seuil par défaut à 2%
        step=0.5,
        help="Déclenche une alerte si la variation de prix dépasse ce seuil sur une période de 5 minutes"
    )

    # Bouton de rafraîchissement
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Rafraîchir les données"):
        st.cache_data.clear()
        st.experimental_rerun()

    # Sélection des cryptos par défaut (BTC) ou celles cochées par l'utilisateur
    selected_cryptos = st.session_state.selected_cryptos or ["BTC"]

    # Filtrage des données par date
    if len(date_range) == 2:
        start_date, end_date = date_range
        df = df[
            (df["timestamp_local"].dt.date >= start_date) &
            (df["timestamp_local"].dt.date <= end_date)
            ]

    # Interface principale avec onglets
    tab1, tab2 = st.tabs(["Graphiques", "Alertes"])

    with tab1:
        render_metrics_dashboard(df, selected_cryptos)
        render_price_chart(df, selected_cryptos)

    with tab2:
        render_alerts(df, selected_cryptos, alert_threshold)

if __name__ == "__main__":
    main()
