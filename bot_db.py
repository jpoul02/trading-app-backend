import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "bot_state.db")

DEFAULT_STATE = {
    "running": 1,
    "kill_switch_tripped": 0,
    "disabled_reason": None,
    "day_start_balance": None,
    "day_start_date": None,
    "account_start_balance": None,
    "symbols": "EURUSD,GBPUSD,USDJPY,USDCHF",
    "timeframe": "M15",
    "risk_pct": 0.01,
    "daily_loss_limit_pct": 0.03,
    "max_drawdown_pct": 0.10,
    "magic": 424001,
    "trend_enabled": 1,
    "mean_reversion_enabled": 1,
}

STATE_COLUMNS = list(DEFAULT_STATE.keys())

TRADE_COLUMNS = [
    "ticket", "symbol", "action", "volume", "price", "sl", "tp",
    "signal_reason", "status", "profit", "opened_at", "closed_at",
    "mode", "obsidian_path",
]


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    conn = _connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                running INTEGER NOT NULL,
                kill_switch_tripped INTEGER NOT NULL,
                disabled_reason TEXT,
                day_start_balance REAL,
                day_start_date TEXT,
                account_start_balance REAL,
                symbols TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                risk_pct REAL NOT NULL,
                daily_loss_limit_pct REAL NOT NULL,
                max_drawdown_pct REAL NOT NULL,
                magic INTEGER NOT NULL,
                trend_enabled INTEGER NOT NULL DEFAULT 1,
                mean_reversion_enabled INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket INTEGER,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL,
                volume REAL NOT NULL,
                price REAL NOT NULL,
                sl REAL,
                tp REAL,
                signal_reason TEXT,
                status TEXT NOT NULL,
                profit REAL,
                opened_at TEXT,
                closed_at TEXT
            )
        """)
        existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(bot_trades)").fetchall()}
        for col in ("mode", "obsidian_path"):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE bot_trades ADD COLUMN {col} TEXT")

        state_cols = {row["name"] for row in conn.execute("PRAGMA table_info(bot_state)").fetchall()}
        for col in ("trend_enabled", "mean_reversion_enabled"):
            if col not in state_cols:
                conn.execute(f"ALTER TABLE bot_state ADD COLUMN {col} INTEGER NOT NULL DEFAULT 1")

        existing = conn.execute("SELECT id FROM bot_state WHERE id = 1").fetchone()
        if existing is None:
            cols = ", ".join(STATE_COLUMNS)
            placeholders = ", ".join(f":{c}" for c in STATE_COLUMNS)
            values = dict(DEFAULT_STATE)
            values["updated_at"] = datetime.now(timezone.utc).isoformat()
            conn.execute(
                f"INSERT INTO bot_state (id, {cols}, updated_at) VALUES (1, {placeholders}, :updated_at)",
                values,
            )
        conn.commit()
    finally:
        conn.close()


def get_state(db_path: str = DB_PATH) -> dict:
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT * FROM bot_state WHERE id = 1").fetchone()
        return dict(row)
    finally:
        conn.close()


def update_state(db_path: str = DB_PATH, **fields) -> None:
    if not fields:
        return
    conn = _connect(db_path)
    try:
        fields = dict(fields)
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        conn.execute(f"UPDATE bot_state SET {set_clause} WHERE id = 1", fields)
        conn.commit()
    finally:
        conn.close()


def log_trade(db_path: str = DB_PATH, **fields) -> int:
    conn = _connect(db_path)
    try:
        fields = {c: fields.get(c) for c in TRADE_COLUMNS}
        if fields.get("opened_at") is None:
            fields["opened_at"] = datetime.now(timezone.utc).isoformat()
        cols = ", ".join(fields.keys())
        placeholders = ", ".join(f":{c}" for c in fields.keys())
        cur = conn.execute(f"INSERT INTO bot_trades ({cols}) VALUES ({placeholders})", fields)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_trade(db_path: str, trade_id: int, **fields) -> None:
    if not fields:
        return
    conn = _connect(db_path)
    try:
        set_clause = ", ".join(f"{k} = :{k}" for k in fields)
        fields = dict(fields)
        fields["trade_id"] = trade_id
        conn.execute(f"UPDATE bot_trades SET {set_clause} WHERE id = :trade_id", fields)
        conn.commit()
    finally:
        conn.close()


def get_open_trades(db_path: str = DB_PATH) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM bot_trades WHERE status = 'open'").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def list_trades(db_path: str = DB_PATH, limit: int = 50, offset: int = 0) -> list[dict]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM bot_trades ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count_trades(db_path: str = DB_PATH) -> int:
    conn = _connect(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM bot_trades").fetchone()[0]
    finally:
        conn.close()
