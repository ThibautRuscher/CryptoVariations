# Pour tester en local
#from dotenv import load_dotenv
#load_dotenv()  # Charge les variables depuis .env

import psycopg2
import requests
import pandas as pd
import os
from datetime import datetime, timedelta
import pytz
import numpy as np

# Configuration
variation_alert_threshold = 2
DATABASE_URL = os.getenv("DATABASE_URL")

def get_connection():
    conn = psycopg2.connect(DATABASE_URL)

    # Ajouter un adaptateur pour les types NumPy
    psycopg2.extensions.register_adapter(np.float64, lambda x: psycopg2.extensions.AsIs(float(x)))
    psycopg2.extensions.register_adapter(np.int64, lambda x: psycopg2.extensions.AsIs(int(x)))

    return conn

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Table principale des prix
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prices (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP WITH TIME ZONE,
            crypto TEXT,
            price REAL
        )
    """)

    # Table pour les statistiques calculées
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP WITH TIME ZONE,
            crypto TEXT,
            current_price REAL,
            price_change_pct REAL,
            price_change_24h_pct REAL,
            volume_5min REAL,
            high_24h REAL,
            low_24h REAL
        )
    """)

    # Table pour les alertes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP WITH TIME ZONE,
            crypto TEXT,
            start_price REAL,
            end_price REAL,
            price_change_pct REAL,
            time_interval TEXT
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

def fetch_prices():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,ripple&vs_currencies=usd"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Erreur dans la requête: {response.status_code}")
        return {}
    data = response.json()
    return {
        "BTC": data["bitcoin"]["usd"],
        "ETH": data["ethereum"]["usd"],
        "XRP": data["ripple"]["usd"]
    }

def send_slack_alert(message):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if webhook_url:
        requests.post(webhook_url, json={"text": message})

def calculate_stats(conn, current_timestamp):
    cursor = conn.cursor()

    # Récupérer les dernières 24h de données pour chaque crypto
    timestamp_24h_ago = current_timestamp - timedelta(days=1)

    cursor.execute("""
        SELECT * FROM prices 
        WHERE timestamp >= %s
        ORDER BY crypto, timestamp
    """, (timestamp_24h_ago,))

    rows = cursor.fetchall()
    if not rows:
        return

    # Créer un DataFrame à partir des résultats
    columns = ['id', 'timestamp', 'crypto', 'price']
    df = pd.DataFrame(rows, columns=columns)
    df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True).dt.tz_convert('Europe/Paris')

    # Convert timestamp_24h_ago to pandas datetime
    pd_timestamp_24h_ago = pd.Timestamp(timestamp_24h_ago)

    for crypto in df['crypto'].unique():
        df_crypto = df[df['crypto'] == crypto].sort_values('timestamp')

        if len(df_crypto) < 2:
            continue

        # Prix actuel et précédent
        current_price = df_crypto['price'].iloc[-1]
        previous_price = df_crypto['price'].iloc[-2]

        # Variation depuis le dernier relevé
        price_change_pct = ((current_price - previous_price) / previous_price) * 100

        # Trouver le prix il y a 24h ou le premier disponible
        df_24h = df_crypto[df_crypto['timestamp'] >= pd_timestamp_24h_ago]
        if not df_24h.empty:
            price_24h_ago = df_24h['price'].iloc[0]
            price_change_24h_pct = ((current_price - price_24h_ago) / price_24h_ago) * 100
        else:
            price_change_24h_pct = 0

        # Statistiques sur 24h
        high_24h = df_crypto['price'].max()
        low_24h = df_crypto['price'].min()

        # Volatilité sur les 5 dernières minutes (si disponible)
        recent_prices = df_crypto.tail(6)  # Généralement 6 points pour 30 minutes avec une mesure toutes les 5 minutes
        volume_5min = recent_prices['price'].std() if len(recent_prices) >= 2 else 0

        # Enregistrer les statistiques
        cursor.execute("""
            INSERT INTO stats (timestamp, crypto, current_price, price_change_pct, 
                            price_change_24h_pct, volume_5min, high_24h, low_24h)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (current_timestamp, crypto, current_price, price_change_pct,
              price_change_24h_pct, volume_5min, high_24h, low_24h))

def check_for_alerts(conn, variation_threshold):
    cursor = conn.cursor()

    # Récupérer les 50 derniers points de données pour chaque crypto
    cursor.execute("""
        WITH ranked_prices AS (
            SELECT id, timestamp, crypto, price,
                   ROW_NUMBER() OVER (PARTITION BY crypto ORDER BY timestamp DESC) as rn
            FROM prices
        )
        SELECT id, timestamp, crypto, price
        FROM ranked_prices
        WHERE rn <= 50
        ORDER BY crypto, timestamp
    """)

    rows = cursor.fetchall()
    if not rows:
        return []

    columns = ['id', 'timestamp', 'crypto', 'price']
    df = pd.DataFrame(rows, columns=columns)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    alerts = []

    for crypto, group in df.groupby('crypto'):
        group = group.sort_values('timestamp')

        # Vérifier les variations significatives
        for i in range(1, len(group)):
            current_row = group.iloc[i]
            prev_row = group.iloc[i-1]

            price_change = ((current_row['price'] - prev_row['price']) / prev_row['price']) * 100

            if abs(price_change) > variation_threshold:
                time_diff = current_row['timestamp'] - prev_row['timestamp']
                time_diff_str = str(time_diff).split('.')[0]  # Conversion en format hh:mm:ss

                alert = {
                    'crypto': crypto,
                    'timestamp': current_row['timestamp'],
                    'start_price': prev_row['price'],
                    'end_price': current_row['price'],
                    'price_change_pct': price_change,
                    'time_interval': time_diff_str
                }

                # Enregistrer l'alerte dans la base de données
                cursor.execute("""
                    INSERT INTO alerts (timestamp, crypto, start_price, end_price, price_change_pct, time_interval)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (current_row['timestamp'], crypto, prev_row['price'],
                      current_row['price'], price_change, time_diff_str))

                alerts.append(alert)

    return alerts

def format_alerts_for_slack(alerts):
    if not alerts:
        return None

    message = "🔔 *Alerte Volatilité* 🔔:\n\n"
    for alert in alerts:
        message += f"*Crypto*          : {alert['crypto']}\n"
        message += f"*Heure*           : {alert['timestamp']}\n"
        message += f"*Prix Précédent*  : {alert['start_price']} USD\n"
        message += f"*Prix Actuel*     : {alert['end_price']} USD\n"
        message += f"*Variation*       : {alert['price_change_pct']:.2f}%\n"
        message += f"*Intervalle*      : {alert['time_interval']}\n"
        message += "---------------------------------------\n"

    return message

def run_scraper():
    # Initialiser la base de données si nécessaire
    initialize_db()

    # Connexion pour cette exécution
    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Récupérer les prix actuels
        prices = fetch_prices()
        current_timestamp = datetime.now(pytz.timezone('Europe/Paris'))

        # Insérer les nouveaux prix
        for crypto, price in prices.items():
            cursor.execute("""
                INSERT INTO prices (timestamp, crypto, price) 
                VALUES (%s, %s, %s)
            """, (current_timestamp, crypto, price))

        # Calculer et enregistrer les statistiques
        calculate_stats(conn, current_timestamp)

        # Vérifier et enregistrer les alertes
        alerts = check_for_alerts(conn, variation_alert_threshold)

        # Envoyer les alertes à Slack si nécessaire
        if alerts:
            slack_message = format_alerts_for_slack(alerts)
            send_slack_alert(slack_message)

        # Commit toutes les modifications
        conn.commit()
        print(f"Scraper exécuté avec succès à {current_timestamp}")

    except Exception as e:
        conn.rollback()
        print(f"Erreur lors de l'exécution du scraper: {e}")
    finally:
        cursor.close()
        conn.close()

# Point d'entrée principal
if __name__ == "__main__":
    run_scraper()
    print("Script terminé.")