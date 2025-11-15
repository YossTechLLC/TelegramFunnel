#!/usr/bin/env python
"""
🗺️ Mappings Routes for PGP_WEBAPI_v1
Provides currency and network mappings for frontend dropdowns
"""
from flask import Blueprint, jsonify
from database.connection import db_manager

mappings_bp = Blueprint('mappings', __name__)


@mappings_bp.route('/currency-network', methods=['GET'])
def get_currency_network_mappings():
    """
    Get currency to network mappings from currency_to_network table
    Mirrors the exact logic from GCRegister10-26/database_manager.py

    Returns: 200 OK with mapping data structured for bidirectional filtering
    """
    try:
        with db_manager.get_db() as conn:
            cursor = conn.cursor()

            # Query currency_to_network table (same as original GCRegister10-26)
            print("🔍 [API] Fetching currency-to-network mappings from currency_to_network table")
            cursor.execute("""
                SELECT currency, network, currency_name, network_name
                FROM currency_to_network
                ORDER BY network, currency
            """)

            rows = cursor.fetchall()
            cursor.close()

            # Build data structures for bidirectional filtering (same as original)
            mappings = []
            network_to_currencies = {}
            currency_to_networks = {}
            networks_with_names = {}
            currencies_with_names = {}

            for currency, network, currency_name, network_name in rows:
                # Add to mappings list
                mappings.append({
                    'currency': currency,
                    'network': network,
                    'currency_name': currency_name or currency,  # Fallback to code if name is NULL
                    'network_name': network_name or network      # Fallback to code if name is NULL
                })

                # Build network -> currencies mapping
                if network not in network_to_currencies:
                    network_to_currencies[network] = []
                network_to_currencies[network].append({
                    'currency': currency,
                    'currency_name': currency_name or currency
                })

                # Build currency -> networks mapping
                if currency not in currency_to_networks:
                    currency_to_networks[currency] = []
                currency_to_networks[currency].append({
                    'network': network,
                    'network_name': network_name or network
                })

                # Build lookup tables for names
                if network not in networks_with_names:
                    networks_with_names[network] = network_name or network
                if currency not in currencies_with_names:
                    currencies_with_names[currency] = currency_name or currency

            print(f"✅ [API] Fetched {len(mappings)} currency-network mappings with friendly names")
            print(f"📊 [API] {len(network_to_currencies)} unique networks")
            print(f"📊 [API] {len(currency_to_networks)} unique currencies")

        return jsonify({
            'network_to_currencies': network_to_currencies,
            'currency_to_networks': currency_to_networks,
            'networks_with_names': networks_with_names,
            'currencies_with_names': currencies_with_names
        }), 200

    except Exception as e:
        print(f"❌ [API] Error fetching currency-network mappings: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500
