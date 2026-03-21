import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "db" / "buildiq.db"


def init_rag_tables():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS regulation_chunks (
        chunk_id TEXT PRIMARY KEY,
        source_file TEXT NOT NULL,
        rule_id TEXT,
        go_number TEXT,
        verified_date TEXT,
        authority TEXT,
        category TEXT,
        page_number INTEGER,
        chunk_index INTEGER,
        text TEXT NOT NULL,
        char_start INTEGER,
        char_end INTEGER,
        word_count INTEGER,
        confidence TEXT DEFAULT 'HIGH'
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS ingestion_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_file TEXT,
        chunks_created INTEGER,
        ingested_at TEXT,
        status TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS architects (
        id INTEGER PRIMARY KEY,
        name TEXT,
        area TEXT,
        tnca_reg TEXT,
        specialisation TEXT,
        rating REAL,
        submissions_count INTEGER,
        response_hours INTEGER,
        phone TEXT,
        active INTEGER DEFAULT 1
    )
    """)

    c.executemany(
        "INSERT OR IGNORE INTO architects VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (1, 'R. Karthikeyan', 'RS Puram, Coimbatore', 'TN-2847',
             'Residential CCMC submissions', 4.9, 142, 2, '+919876543210', 1),
            (2, 'S. Priyanka', 'Peelamedu, Coimbatore', 'TN-3156',
             'CCMC + DTCP', 4.8, 98, 4, '+919876543211', 1),
            (3, 'M. Venkatesh', 'Ganapathy, Coimbatore', 'TN-2991',
             'G+1 residential', 4.7, 67, 1, '+919876543212', 1),
        ]
    )

    c.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_name TEXT NOT NULL,
        owner_phone TEXT NOT NULL,
        architect_name TEXT NOT NULL,
        architect_phone TEXT NOT NULL,
        compliance_status TEXT,
        plot_details TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()
    print("RAG tables created")


if __name__ == "__main__":
    init_rag_tables()
