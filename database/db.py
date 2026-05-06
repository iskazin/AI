"""
database/db.py
SQLite база данных — пациенты, консультации, платежи, гайды
"""
import aiosqlite
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "neo_clinic.db")


async def init_db():
    """Инициализация всех таблиц"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Пациенты
        await db.execute("""
            CREATE TABLE IF NOT EXISTS patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT DEFAULT '',
                full_name TEXT DEFAULT '',
                registered_at TEXT DEFAULT (datetime('now')),
                health_index REAL DEFAULT 0,
                compliance_score REAL DEFAULT 0
            )
        """)

        # Консультации (полные ответы по всем фазам)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                telegram_id INTEGER NOT NULL,
                phase1_briefing TEXT DEFAULT '',
                phase2_complaints TEXT DEFAULT '',
                phase3_history TEXT DEFAULT '',
                phase4_followup TEXT DEFAULT '',
                phase5_result TEXT DEFAULT '',
                status TEXT DEFAULT 'in_progress',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (patient_id) REFERENCES patients(id)
            )
        """)

        # Платежи
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT DEFAULT 'KZT',
                payment_type TEXT DEFAULT 'kaspi',
                product_type TEXT DEFAULT 'consultation',
                product_id INTEGER DEFAULT 0,
                product_name TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                receipt_file_id TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                approved_at TEXT DEFAULT ''
            )
        """)

        # Покупки гайдов
        await db.execute("""
            CREATE TABLE IF NOT EXISTS guide_purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                guide_id INTEGER NOT NULL,
                guide_title TEXT DEFAULT '',
                amount INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        await db.commit()


async def get_or_create_patient(telegram_id: int, username: str, full_name: str) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM patients WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)

        await db.execute(
            "INSERT INTO patients (telegram_id, username, full_name) VALUES (?, ?, ?)",
            (telegram_id, username, full_name)
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM patients WHERE telegram_id = ?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row)


async def create_consultation(telegram_id: int) -> int:
    """Создать новую консультацию, вернуть её id"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id FROM patients WHERE telegram_id = ?", (telegram_id,)
        )
        patient = await cursor.fetchone()
        if not patient:
            return 0

        cursor = await db.execute(
            "INSERT INTO consultations (patient_id, telegram_id) VALUES (?, ?)",
            (patient["id"], telegram_id)
        )
        await db.commit()
        return cursor.lastrowid


async def update_consultation_phase(consultation_id: int, phase: str, text: str):
    """Обновить конкретную фазу консультации"""
    allowed = {"phase2_complaints", "phase3_history", "phase4_followup", "phase5_result", "status"}
    if phase not in allowed:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE consultations SET {phase} = ?, updated_at = datetime('now') WHERE id = ?",
            (text, consultation_id)
        )
        await db.commit()


async def get_all_patients(limit: int = 20, offset: int = 0) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT p.*,
                   COUNT(DISTINCT c.id) as consultation_count,
                   COUNT(DISTINCT py.id) as payment_count,
                   SUM(CASE WHEN py.status = 'approved' THEN py.amount ELSE 0 END) as total_paid
            FROM patients p
            LEFT JOIN consultations c ON c.telegram_id = p.telegram_id
            LEFT JOIN payments py ON py.telegram_id = p.telegram_id
            GROUP BY p.id
            ORDER BY p.registered_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_patient_card(telegram_id: int) -> dict:
    """Полная карточка пациента — всё в одном"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            "SELECT * FROM patients WHERE telegram_id = ?", (telegram_id,)
        )
        patient = await cursor.fetchone()
        if not patient:
            return {}
        patient = dict(patient)

        cursor = await db.execute("""
            SELECT * FROM consultations
            WHERE telegram_id = ?
            ORDER BY created_at DESC
            LIMIT 5
        """, (telegram_id,))
        consultations = [dict(r) for r in await cursor.fetchall()]

        cursor = await db.execute("""
            SELECT * FROM payments
            WHERE telegram_id = ?
            ORDER BY created_at DESC
        """, (telegram_id,))
        payments = [dict(r) for r in await cursor.fetchall()]

        return {
            "patient": patient,
            "consultations": consultations,
            "payments": payments
        }


async def get_pending_payments() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT py.*, p.full_name, p.username
            FROM payments py
            LEFT JOIN patients p ON p.telegram_id = py.telegram_id
            WHERE py.status = 'pending'
            ORDER BY py.created_at DESC
        """)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def approve_payment(payment_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET status = 'approved', approved_at = datetime('now') WHERE id = ?",
            (payment_id,)
        )
        await db.commit()


async def reject_payment(payment_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET status = 'rejected' WHERE id = ?",
            (payment_id,)
        )
        await db.commit()


async def create_payment(telegram_id: int, amount: int, product_type: str,
                          product_name: str = "", product_id: int = 0) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO payments (telegram_id, amount, product_type, product_name, product_id)
            VALUES (?, ?, ?, ?, ?)
        """, (telegram_id, amount, product_type, product_name, product_id))
        await db.commit()
        return cursor.lastrowid


async def attach_receipt(payment_id: int, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET receipt_file_id = ? WHERE id = ?",
            (file_id, payment_id)
        )
        await db.commit()


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT COUNT(*) as cnt FROM patients")
        total_patients = (await cursor.fetchone())["cnt"]

        cursor = await db.execute("SELECT COUNT(*) as cnt FROM consultations")
        total_consultations = (await cursor.fetchone())["cnt"]

        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM payments WHERE status = 'pending'"
        )
        pending_payments = (await cursor.fetchone())["cnt"]

        cursor = await db.execute(
            "SELECT COALESCE(SUM(amount), 0) as total FROM payments WHERE status = 'approved'"
        )
        total_revenue = (await cursor.fetchone())["total"]

        cursor = await db.execute("""
            SELECT COUNT(*) as cnt FROM patients
            WHERE registered_at >= datetime('now', '-7 days')
        """)
        new_this_week = (await cursor.fetchone())["cnt"]

        return {
            "total_patients": total_patients,
            "total_consultations": total_consultations,
            "pending_payments": pending_payments,
            "total_revenue": total_revenue,
            "new_this_week": new_this_week
        }
async def save_document(telegram_id: int, file_id: str, file_type: str, file_name: str = ""):
    """Сохранить документ пациента"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS patient_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                file_type TEXT DEFAULT 'photo',
                file_name TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        await db.execute(
            "INSERT INTO patient_documents (telegram_id, file_id, file_type, file_name) VALUES (?, ?, ?, ?)",
            (telegram_id, file_id, file_type, file_name)
        )
        await db.commit()


async def get_patient_documents(telegram_id: int) -> list:
    """Получить все документы пациента"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        try:
            cursor = await db.execute(
                "SELECT * FROM patient_documents WHERE telegram_id = ? ORDER BY created_at DESC",
                (telegram_id,)
            )
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
