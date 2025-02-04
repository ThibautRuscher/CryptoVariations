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
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Erreur dans la requête: {response.status_code}")
        return {}
    data = response.json()
    print("Données reçues:", data)  # Pour débugger la réponse
    return {
        "BTC": data["bitcoin"]["usd"],
        "ETH": data["ethereum"]["usd"],
        "XRP": data["ripple"]["usd"]
    }

def send_slack_alert(message):
    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if webhook_url:
        requests.post(webhook_url, json={"text": message})

def run_scraper():
    prices = fetch_prices()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for crypto, price in prices.items():
        cursor.execute("INSERT INTO prices (timestamp, crypto, price) VALUES (%s, %s, %s)", (timestamp, crypto, price))

    conn.commit()

    # Récupérer toutes les données en les triant par timestamp
    df = pd.read_sql_query("SELECT * FROM prices ORDER BY timestamp", conn)

    alerts = []

    # Pour chaque crypto, comparer uniquement les deux derniers enregistrements
    for crypto, group in df.groupby("crypto"):
        group = group.sort_values("timestamp")
        if len(group) >= 2:
            dernier = group.iloc[-1]
            precedent = group.iloc[-2]
            variation = ((dernier["price"] - precedent["price"]) / precedent["price"]) * 100
            if abs(variation) > variation_value:
                alerts.append({
                    "crypto": crypto,
                    "timestamp": dernier["timestamp"],
                    "previous_price": precedent["price"],
                    "current_price": dernier["price"],
                    "price_change": variation
                })

    if alerts:
        # Formatage du message pour Slack avec une mise en forme lisible
        message = "🔔 *Alerte Volatilité* 🔔:\n\n"
        for alert in alerts:
            message += f"*Crypto*          : {alert['crypto']}\n"
            message += f"*Heure*           : {alert['timestamp']}\n"
            message += f"*Prix Précédent*  : {alert['previous_price']} USD\n"
            message += f"*Prix Actuel*     : {alert['current_price']} USD\n"
            message += f"*Variation*       : {alert['price_change']:.2f}%\n"
            message += "---------------------------------------\n"

        send_slack_alert(message)

# Exécuter directement le scraper au lancement
if __name__ == "__main__":
    run_scraper()
    cursor.close()
    conn.close()
    print("Script terminé.")
