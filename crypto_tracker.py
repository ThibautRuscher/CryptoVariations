import psycopg2
import requests
import pandas as pd
import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify

# Pourcentage de variation à partir du quel une alerte est envoyée
variation_value = 2

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
conn.commit()

# Scraper et vérification des alertes
def fetch_prices():
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,ripple&vs_currencies=usd"
    data = requests.get(url).json()
    return {
        "BTC": data["bitcoin"]["usd"],
        "ETH": data["ethereum"]["usd"],
        "XRP": data["ripple"]["usd"]
    }

def run_scraper():
    prices = fetch_prices()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for crypto, price in prices.items():
        cursor.execute("INSERT INTO prices (timestamp, crypto, price) VALUES (%s, %s, %s)", (timestamp, crypto, price))

    conn.commit()

    # Vérification des variations de prix
    df = pd.read_sql_query("SELECT * FROM prices", conn)
    df["price_change"] = df.groupby("crypto")["price"].pct_change() * 100
    volatile = df[df["price_change"].abs() > variation_value]

    # Envoi d'alerte Slack si besoin
    # if not volatile.empty:
    #    send_slack_alert("🚨 Alerte Volatilité !\n" + volatile.to_string(index=False))

def send_slack_alert(message):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if webhook_url:
        requests.post(webhook_url, json={"text": message})


# Exécuter directement le scraper au lancement
if __name__ == "__main__":
    run_scraper()
    cursor.close()
    conn.close()
    print("Script terminé.")
