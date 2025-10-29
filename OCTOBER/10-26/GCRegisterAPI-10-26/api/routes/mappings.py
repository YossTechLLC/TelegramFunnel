#!/usr/bin/env python
"""
🗺️ Mappings Routes for GCRegisterAPI-10-26
Provides currency and network mappings for frontend dropdowns
"""
from flask import Blueprint, jsonify
from database.connection import db_manager

mappings_bp = Blueprint('mappings', __name__)


@mappings_bp.route('/currency-network', methods=['GET'])
def get_currency_network_mappings():
    """
    Get currency to network mappings

    Returns: 200 OK with mapping data
    """
    try:
        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Get all networks with their currency mappings
            cursor.execute("""
                SELECT DISTINCT
                    client_payout_network as network,
                    client_payout_currency as currency
                FROM main_clients_database
                WHERE client_payout_network IS NOT NULL
                    AND client_payout_currency IS NOT NULL
                ORDER BY client_payout_network, client_payout_currency
            """)

            rows = cursor.fetchall()
            cursor.close()

            # Build network_to_currencies mapping
            network_to_currencies = {}
            currency_to_networks = {}
            all_networks = set()
            all_currencies = set()

            for network, currency in rows:
                all_networks.add(network)
                all_currencies.add(currency)

                if network not in network_to_currencies:
                    network_to_currencies[network] = []
                network_to_currencies[network].append({
                    'currency': currency,
                    'currency_name': currency  # Can enhance with full names later
                })

                if currency not in currency_to_networks:
                    currency_to_networks[currency] = []
                currency_to_networks[currency].append({
                    'network': network,
                    'network_name': network
                })

            # If no data in database, return default mapping
            if not network_to_currencies:
                network_to_currencies = {
                    'ETH': [
                        {'currency': 'USDT', 'currency_name': 'Tether USDt'},
                        {'currency': 'USDC', 'currency_name': 'USD Coin'}
                    ],
                    'TRX': [
                        {'currency': 'USDT', 'currency_name': 'Tether USDt'}
                    ],
                    'BTC': [
                        {'currency': 'BTC', 'currency_name': 'Bitcoin'}
                    ],
                    'XMR': [
                        {'currency': 'XMR', 'currency_name': 'Monero'}
                    ]
                }

                currency_to_networks = {
                    'USDT': [
                        {'network': 'ETH', 'network_name': 'Ethereum'},
                        {'network': 'TRX', 'network_name': 'Tron'}
                    ],
                    'USDC': [
                        {'network': 'ETH', 'network_name': 'Ethereum'}
                    ],
                    'BTC': [
                        {'network': 'BTC', 'network_name': 'Bitcoin'}
                    ],
                    'XMR': [
                        {'network': 'XMR', 'network_name': 'Monero'}
                    ]
                }

                all_networks = {'ETH', 'TRX', 'BTC', 'XMR'}
                all_currencies = {'USDT', 'USDC', 'BTC', 'XMR'}

        return jsonify({
            'network_to_currencies': network_to_currencies,
            'currency_to_networks': currency_to_networks,
            'networks_with_names': {net: net for net in all_networks},
            'currencies_with_names': {curr: curr for curr in all_currencies}
        }), 200

    except Exception as e:
        print(f"❌ Error fetching mappings: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
