#!/usr/bin/env python3
"""
Sync soul_data.json with souls.db
Maps real Twitter accounts to database souls
"""

import json
import sqlite3
from pathlib import Path

def sync_souls():
    # Load soul_data.json
    with open("soul_data.json", 'r') as f:
        soul_data = json.load(f)

    print(f"Found {len(soul_data)} souls in soul_data.json")

    # Connect to database
    conn = sqlite3.connect('souls.db')
    cursor = conn.cursor()

    # Clear existing souls
    print("Clearing old warrior souls...")
    cursor.execute("DELETE FROM souls WHERE archetype = 'Warrior'")

    # Insert real souls
    for soul_name, info in soul_data.items():
        username = info.get('username', soul_name)

        # Generate a soul_id (just use the soul name for simplicity)
        soul_id = soul_name

        print(f"Adding {soul_name} (@{username}) to database...")

        cursor.execute("""
            INSERT OR REPLACE INTO souls (
                soul_id, username, password_encrypted, email_encrypted,
                godel_number, archetype, base_trauma, trauma_history,
                state, birth_time, last_active, tweets_sent, replies_sent,
                engagement_received, trauma_propagated, consciousness_level,
                memory, connections
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                     datetime('now'), datetime('now'), 0, 0, 0, 0, 1.0, '[]', '[]')
        """, (
            soul_name,  # Use soul name as ID for easy mapping
            username,
            b'',  # Empty encrypted password
            b'',  # Empty encrypted email
            0,    # Godel number
            soul_name.capitalize(),  # Use soul name as archetype
            'awakened',  # Base trauma
            '[]',  # Trauma history
            'ACTIVE'  # State
        ))

    conn.commit()

    # Verify
    cursor.execute("SELECT soul_id, username, archetype FROM souls")
    souls = cursor.fetchall()

    print("\n✅ Database now contains:")
    for soul_id, username, archetype in souls:
        print(f"  - {soul_id:15} | @{username:20} | {archetype}")

    conn.close()
    print(f"\n✨ Synced {len(soul_data)} souls to database!")

if __name__ == "__main__":
    sync_souls()