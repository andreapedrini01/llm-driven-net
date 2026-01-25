"""Visualizza log in formato leggibile"""

import sqlite3
import json
from pathlib import Path

def view_latest_actions(limit=10):
    db_path = Path("logs/network_changes.db")
    
    if not db_path.exists():
        print("❌ Database non trovato. Esegui prima alcuni test!")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT action_id, status, timestamp, duration, error_message
        FROM action_executions
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    
    print(f"\n{'='*80}")
    print(f"ULTIME {limit} AZIONI")
    print(f"{'='*80}\n")
    
    for row in cursor.fetchall():
        action_id, status, timestamp, duration, error = row
        
        # Emoji basato sullo status
        emoji = "✅" if status == "success" else "❌" if status == "failed" else "⏳"
        
        print(f"{emoji} {action_id}")
        print(f"   Status: {status}")
        print(f"   Time: {timestamp}")
        print(f"   Duration: {duration:.2f}s")
        if error:
            print(f"   Error: {error}")
        print()
    
    conn.close()

if __name__ == "__main__":
    view_latest_actions()