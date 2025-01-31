import psycopg2
import requests
import pandas as pd
import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

app = Flask(__name__)

# Connexion à PostgreSQL sur Railway
DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Création des tables si elles n'existent pas
cursor.execute("""
    CREATE TABLE IF NOT EXISTS prices (
        id SERIAL PRIMARY KEY,
        timestamp TIMESTAMP,
        crypto TEXT,
        price REAL
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id SERIAL PRIMARY KEY,
        user_id TEXT,
        crypto TEXT,
        threshold REAL,
        time_window INTEGER
    )
""")
conn.commit()

# API : Modifier le seuil d’alerte
@app.route('/set_alert', methods=['POST'])
def set_alert():
    data = request.json
    user_id = data.get('user_id', 'default_user')  # Gérer plusieurs utilisateurs
    crypto = data.get('crypto')
    threshold = data.get('threshold')
    time_window = data.get('time_window')

    cursor.execute("INSERT INTO alerts (user_id, crypto, threshold, time_window) VALUES (%s, %s, %s, %s) ON CONFLICT (user_id, crypto) DO UPDATE SET threshold = EXCLUDED.threshold, time_window = EXCLUDED.time_window",
                   (user_id, crypto, threshold, time_window))
    conn.commit()
    return jsonify({"message": "Alerte mise à jour avec succès"}), 200

# Scraper et vérification des alertes
def fetch_prices():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,ripple&vs_currencies=usd"
    data = requests.get(url).json()
    return {
        "BTC": data["bitcoin"]["usd"],
        "ETH": data["ethereum"]["usd"],
        "XRP": data["ripple"]["usd"]
    }

def check_alerts():
    prices = fetch_prices()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for crypto, price in prices.items():
        cursor.execute("INSERT INTO prices (timestamp, crypto, price) VALUES (%s, %s, %s)", (timestamp, crypto, price))

    conn.commit()

    # Récupérer les alertes paramétrées par les utilisateurs
    cursor.execute("SELECT * FROM alerts")
    alerts = cursor.fetchall()

    for alert in alerts:
        user_id, crypto, threshold, time_window = alert[1], alert[2], alert[3], alert[4]

        # Vérifier la variation sur la période choisie
        time_limit = datetime.now() - timedelta(minutes=time_window)
        df = pd.read_sql_query(f"SELECT * FROM prices WHERE crypto = '{crypto}' AND timestamp >= '{time_limit}'", conn)

        if len(df) > 1:
            df["price_change"] = df["price"].pct_change() * 100
            last_change = df["price_change"].iloc[-1]

            if abs(last_change) > threshold:
                send_slack_alert(f"🚨 {crypto} a bougé de {last_change:.2f}% en {time_window} minutes pour {user_id}")

def send_slack_alert(message):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if webhook_url:
        requests.post(webhook_url, json={"text": message})

@app.route('/run_scraper', methods=['POST'])
def run_scraper():
    check_alerts()
    return jsonify({"message": "Scraper exécuté"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)