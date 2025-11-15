#!/usr/bin/env python
"""
📺 Channel Service for GCRegisterAPI-10-26
Handles channel CRUD operations
"""
from typing import List, Optional, Dict
from decimal import Decimal


class ChannelService:
    """Handles channel management operations"""

    @staticmethod
    def count_user_channels(conn, user_id: str) -> int:
        """
        Count channels owned by a user

        Args:
            conn: Database connection
            user_id: User UUID

        Returns:
            Number of channels owned by user
        """
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*)
            FROM main_clients_database
            WHERE client_id = %s
        """, (user_id,))
        count = cursor.fetchone()[0]
        cursor.close()
        return count

    @staticmethod
    def register_channel(conn, user_id: str, username: str, channel_data) -> bool:
        """
        Register a new channel

        Args:
            conn: Database connection
            user_id: User UUID (from JWT)
            username: Username (for created_by audit trail)
            channel_data: ChannelRegistrationRequest object

        Returns:
            True if successful

        Raises:
            ValueError: If channel ID already exists
        """
        try:
            cursor = conn.cursor()

            # Check if channel already exists
            cursor.execute("""
                SELECT open_channel_id
                FROM main_clients_database
                WHERE open_channel_id = %s
            """, (channel_data.open_channel_id,))

            if cursor.fetchone():
                raise ValueError('Channel ID already registered')

            # Insert channel (🆕 includes notification fields)
            cursor.execute("""
                INSERT INTO main_clients_database (
                    open_channel_id,
                    open_channel_title,
                    open_channel_description,
                    closed_channel_id,
                    closed_channel_title,
                    closed_channel_description,
                    closed_channel_donation_message,
                    sub_1_price,
                    sub_1_time,
                    sub_2_price,
                    sub_2_time,
                    sub_3_price,
                    sub_3_time,
                    client_wallet_address,
                    client_payout_currency,
                    client_payout_network,
                    payout_strategy,
                    payout_threshold_usd,
                    notification_status,
                    notification_id,
                    client_id,
                    created_by
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                channel_data.open_channel_id,
                channel_data.open_channel_title,
                channel_data.open_channel_description,
                channel_data.closed_channel_id,
                channel_data.closed_channel_title,
                channel_data.closed_channel_description,
                channel_data.closed_channel_donation_message,
                channel_data.sub_1_price,
                channel_data.sub_1_time,
                channel_data.sub_2_price,
                channel_data.sub_2_time,
                channel_data.sub_3_price,
                channel_data.sub_3_time,
                channel_data.client_wallet_address,
                channel_data.client_payout_currency,
                channel_data.client_payout_network,
                channel_data.payout_strategy,
                channel_data.payout_threshold_usd,
                channel_data.notification_status,
                channel_data.notification_id,
                user_id,
                username
            ))

            cursor.close()
            print(f"✅ Channel {channel_data.open_channel_id} registered with notification settings")
            return True

        except Exception as e:
            print(f"❌ Error registering channel: {e}")
            raise

    @staticmethod
    def get_user_channels(conn, user_id: str) -> List[Dict]:
        """
        Get all channels owned by a user

        Args:
            conn: Database connection
            user_id: User UUID

        Returns:
            List of channel dicts
        """
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                m.open_channel_id,
                m.open_channel_title,
                m.open_channel_description,
                m.closed_channel_id,
                m.closed_channel_title,
                m.closed_channel_description,
                m.closed_channel_donation_message,
                m.sub_1_price,
                m.sub_1_time,
                m.sub_2_price,
                m.sub_2_time,
                m.sub_3_price,
                m.sub_3_time,
                m.client_wallet_address,
                m.client_payout_currency,
                m.client_payout_network,
                m.payout_strategy,
                m.payout_threshold_usd,
                m.notification_status,
                m.notification_id,
                b.id AS broadcast_id
            FROM main_clients_database m
            LEFT JOIN broadcast_manager b
                ON m.open_channel_id = b.open_channel_id
                AND m.closed_channel_id = b.closed_channel_id
            WHERE m.client_id = %s
            ORDER BY m.open_channel_id DESC
        """, (user_id,))

        rows = cursor.fetchall()
        cursor.close()

        channels = []
        for row in rows:
            # Calculate tier_count dynamically
            tier_count = 0
            if row[7] is not None:  # sub_1_price (index shifted by 1)
                tier_count += 1
            if row[9] is not None:  # sub_2_price (index shifted by 1)
                tier_count += 1
            if row[11] is not None:  # sub_3_price (index shifted by 1)
                tier_count += 1

            channels.append({
                'open_channel_id': row[0],
                'open_channel_title': row[1],
                'open_channel_description': row[2],
                'closed_channel_id': row[3],
                'closed_channel_title': row[4],
                'closed_channel_description': row[5],
                'closed_channel_donation_message': row[6],
                'tier_count': tier_count,
                'sub_1_price': float(row[7]) if row[7] else None,
                'sub_1_time': row[8],
                'sub_2_price': float(row[9]) if row[9] else None,
                'sub_2_time': row[10],
                'sub_3_price': float(row[11]) if row[11] else None,
                'sub_3_time': row[12],
                'client_wallet_address': row[13],
                'client_payout_currency': row[14],
                'client_payout_network': row[15],
                'payout_strategy': row[16],
                'payout_threshold_usd': float(row[17]) if row[17] else None,
                'notification_status': row[18],
                'notification_id': row[19],
                'broadcast_id': str(row[20]) if row[20] else None,  # 🆕 Broadcast Manager ID
                'accumulated_amount': None  # TODO: Calculate from payout_accumulation table
            })

        return channels

    @staticmethod
    def get_channel_by_id(conn, channel_id: str) -> Optional[Dict]:
        """
        Get channel by ID

        Args:
            conn: Database connection
            channel_id: Channel ID

        Returns:
            Channel dict or None
        """
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                open_channel_id,
                open_channel_title,
                open_channel_description,
                closed_channel_id,
                closed_channel_title,
                closed_channel_description,
                closed_channel_donation_message,
                sub_1_price,
                sub_1_time,
                sub_2_price,
                sub_2_time,
                sub_3_price,
                sub_3_time,
                client_wallet_address,
                client_payout_currency,
                client_payout_network,
                payout_strategy,
                payout_threshold_usd,
                notification_status,
                notification_id,
                client_id
            FROM main_clients_database
            WHERE open_channel_id = %s
        """, (channel_id,))

        row = cursor.fetchone()
        cursor.close()

        if not row:
            return None

        # Calculate tier_count dynamically
        tier_count = 0
        if row[7] is not None:  # sub_1_price (index shifted by 1)
            tier_count += 1
        if row[9] is not None:  # sub_2_price (index shifted by 1)
            tier_count += 1
        if row[11] is not None:  # sub_3_price (index shifted by 1)
            tier_count += 1

        return {
            'open_channel_id': row[0],
            'open_channel_title': row[1],
            'open_channel_description': row[2],
            'closed_channel_id': row[3],
            'closed_channel_title': row[4],
            'closed_channel_description': row[5],
            'closed_channel_donation_message': row[6],
            'tier_count': tier_count,
            'sub_1_price': float(row[7]) if row[7] else None,
            'sub_1_time': row[8],
            'sub_2_price': float(row[9]) if row[9] else None,
            'sub_2_time': row[10],
            'sub_3_price': float(row[11]) if row[11] else None,
            'sub_3_time': row[12],
            'client_wallet_address': row[13],
            'client_payout_currency': row[14],
            'client_payout_network': row[15],
            'payout_strategy': row[16],
            'payout_threshold_usd': float(row[17]) if row[17] else None,
            'notification_status': row[18],
            'notification_id': row[19],
            'client_id': str(row[20])
        }

    @staticmethod
    def update_channel(conn, channel_id: str, update_data) -> bool:
        """
        Update a channel

        Args:
            conn: Database connection
            channel_id: Channel ID
            update_data: ChannelUpdateRequest object

        Returns:
            True if successful
        """
        # Build dynamic UPDATE query
        update_fields = []
        values = []

        for field, value in update_data.model_dump(exclude_unset=True).items():
            update_fields.append(f"{field} = %s")
            values.append(value)

        if not update_fields:
            return True  # No updates needed

        # Add updated_at
        update_fields.append("updated_at = NOW()")
        values.append(channel_id)

        cursor = conn.cursor()
        query = f"""
            UPDATE main_clients_database
            SET {', '.join(update_fields)}
            WHERE open_channel_id = %s
        """
        cursor.execute(query, values)
        cursor.close()

        print(f"✅ Channel {channel_id} updated successfully")
        return True

    @staticmethod
    def delete_channel(conn, channel_id: str) -> bool:
        """
        Delete a channel

        Args:
            conn: Database connection
            channel_id: Channel ID

        Returns:
            True if successful
        """
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM main_clients_database
            WHERE open_channel_id = %s
        """, (channel_id,))
        cursor.close()

        print(f"✅ Channel {channel_id} deleted successfully")
        return True
