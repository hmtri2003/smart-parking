import sqlite3
import os
import datetime
from typing import List, Dict, Optional, Tuple

from paths import get_path

class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = get_path("data", "parking.db")
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Cards table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    card_uid TEXT PRIMARY KEY,
                    owner_name TEXT DEFAULT 'KhÃ¡ch vÃ£ng lai',
                    vehicle_type TEXT DEFAULT 'Motorbike',
                    status TEXT DEFAULT 'Active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Parking Records table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS parking_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    card_uid TEXT NOT NULL,
                    plate_in TEXT NOT NULL,
                    plate_out TEXT,
                    image_in_path TEXT,
                    image_out_path TEXT,
                    crop_in_path TEXT,
                    crop_out_path TEXT,
                    entry_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    exit_time TIMESTAMP,
                    fee INTEGER DEFAULT 0,
                    vehicle_type TEXT DEFAULT 'Motorbike',
                    status TEXT DEFAULT 'IN_PARK',
                    notes TEXT
                )
            """)

            # Tariff settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Default settings
            default_settings = {
                "motorbike_base_fee": "5000",   # 5k/block
                "motorbike_hourly_fee": "2000", # 2k/h after base
                "car_base_fee": "20000",        # 20k/block
                "car_hourly_fee": "10000",      # 10k/h after base
                "serial_port": "COM3",
                "baud_rate": "115200",
                "camera_index": "0"
            }

            for key, val in default_settings.items():
                cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))

            conn.commit()

    # --- Setting Operations ---
    def get_setting(self, key: str, default: str = "") -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()

    # --- Card Operations ---
    def register_or_get_card(self, card_uid: str, vehicle_type: str = "Motorbike") -> Dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards WHERE card_uid = ?", (card_uid,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            
            # Auto-register new card
            cursor.execute(
                "INSERT INTO cards (card_uid, owner_name, vehicle_type, status) VALUES (?, ?, ?, ?)",
                (card_uid, f"KhÃ¡ch tháº» {card_uid[-4:]}", vehicle_type, "Active")
            )
            conn.commit()
            return {
                "card_uid": card_uid,
                "owner_name": f"KhÃ¡ch tháº» {card_uid[-4:]}",
                "vehicle_type": vehicle_type,
                "status": "Active"
            }

    def get_all_cards(self) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM cards ORDER BY created_at DESC")
            return [dict(r) for r in cursor.fetchall()]

    def update_card(self, card_uid: str, owner_name: str, vehicle_type: str, status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE cards SET owner_name = ?, vehicle_type = ?, status = ? WHERE card_uid = ?",
                (owner_name, vehicle_type, status, card_uid)
            )
            conn.commit()

    # --- Parking Record Operations ---
    def find_active_record_by_card(self, card_uid: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM parking_records WHERE card_uid = ? AND status = 'IN_PARK' ORDER BY entry_time DESC LIMIT 1",
                (card_uid,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_entry_record(self, card_uid: str, plate_in: str, image_in_path: str, crop_in_path: str, vehicle_type: str = "Motorbike") -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO parking_records (card_uid, plate_in, image_in_path, crop_in_path, vehicle_type, entry_time, status)
                VALUES (?, ?, ?, ?, ?, ?, 'IN_PARK')
            """, (card_uid, plate_in, image_in_path, crop_in_path, vehicle_type, now_str))
            conn.commit()
            return cursor.lastrowid

    def complete_exit_record(self, record_id: int, plate_out: str, image_out_path: str, crop_out_path: str, fee: int, notes: str = ""):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                UPDATE parking_records
                SET plate_out = ?, image_out_path = ?, crop_out_path = ?, exit_time = ?, fee = ?, status = 'COMPLETED', notes = ?
                WHERE id = ?
            """, (plate_out, image_out_path, crop_out_path, now_str, fee, notes, record_id))
            conn.commit()

    def get_parking_records(self, search_term: str = "", status_filter: str = "ALL", limit: int = 200) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM parking_records WHERE 1=1"
            params = []

            if search_term:
                query += " AND (plate_in LIKE ? OR plate_out LIKE ? OR card_uid LIKE ?)"
                like_term = f"%{search_term}%"
                params.extend([like_term, like_term, like_term])

            if status_filter != "ALL":
                query += " AND status = ?"
                params.append(status_filter)

            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(r) for r in cursor.fetchall()]

    def get_statistics(self) -> Dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM parking_records WHERE status = 'IN_PARK'")
            in_park = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*), COALESCE(SUM(fee), 0) FROM parking_records WHERE status = 'COMPLETED'")
            completed_row = cursor.fetchone()
            completed_count = completed_row[0]
            total_revenue = completed_row[1]

            cursor.execute("SELECT COUNT(*) FROM cards")
            total_cards = cursor.fetchone()[0]

            return {
                "in_park_count": in_park,
                "completed_count": completed_count,
                "total_revenue": total_revenue,
                "total_cards": total_cards
            }

