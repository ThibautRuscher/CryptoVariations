# Crypto Price Tracker

## Overview
A real-time cryptocurrency price monitoring system that tracks Bitcoin (BTC), Ethereum (ETH), and Ripple (XRP) prices. The project demonstrates full-stack development capabilities, data engineering practices, and cloud deployment expertise.

Live Demo: [Access the Dashboard](https://cryptovariations-truscher.streamlit.app/)

![Project Architecture](insert-architecture-diagram-url)

## Features
- **Real-time Price Tracking**: Monitors BTC, ETH, and XRP prices using the CoinGecko API
- **Interactive Dashboard**:
    - Dynamic price charts with multiple timeframes
    - Customizable volatility alerts to monitor price fluctuations
    - Real-time price updates
    - Multi-cryptocurrency comparison
- **Automated Alert System**:
    - Slack notifications for significant price movements (over 2% in 5 minutes)
- **Data Persistence**: Historical price data stored in PostgreSQL

## Technical Architecture

### Frontend (Streamlit)
- Built with Python/Streamlit for rapid development and deployment
- Interactive data visualization using Plotly
- Responsive design with custom CSS styling
- Real-time data updates and caching mechanisms
- Deployed on Streamlit Cloud for continuous availability

### Backend (Python)
- Automated data collection using CoinGecko API
- PostgreSQL database integration for data persistence
- Deployed on Railway for reliable execution
- Scheduled tasks running every 5 minutes (with RailWay)
- Slack integration for automated alerts

### Data Engineering
- Automated ETL pipeline
- Data validation and transformation
- Historical data management
- Real-time data processing
- Efficient data storage and retrieval

## Technologies Used
- **Frontend**:
    - Streamlit
    - Plotly
    - Pandas
    - Custom CSS
- **Backend**:
    - Python
    - Flask
    - psycopg2
    - requests
- **Database**:
    - PostgreSQL
- **Deployment**:
    - Streamlit Cloud
    - Railway
- **APIs**:
    - CoinGecko API
    - Slack Webhooks

## Implementation Highlights
- **Scalable Architecture**: Designed for easy integration of additional cryptocurrencies
- **Performance Optimization**: Implemented caching and efficient data retrieval
- **Error Handling**: Robust error management and logging
- **Real-time Processing**: Efficient handling of real-time data streams
- **Security**: Environment variable management for sensitive information

## Skills Demonstrated
- Full-stack Development
- Data Engineering
- ETL Pipeline Design
- Cloud Deployment
- API Integration
- Database Management
- Real-time Data Processing
- Data Visualization
- UI/UX Design
- System Architecture
- DevOps Practices

## Deployment
- Frontend is deployed on Streamlit Cloud
- Backend and database are hosted on Railway
- Automated deployment with continuous updates

## Future Enhancements
- Additional cryptocurrency support
- Advanced technical analysis indicators
- Possibility to enter your Slack webhook URL
- Possibility to edit the alert threshold in order to affect directly the Slack notifications

## Contact
Thibaut RUSCHER - thibruscher@gmail.com

Project Link: [https://github.com/ThibautRuscher/CryptoVariations](https://github.com/ThibautRuscher/CryptoVariations)

## License
This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.