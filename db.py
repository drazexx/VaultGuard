import sqlite3
import time
from contextlib import contextmanager

import config

schema = """
CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channelMsgId INTEGER NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'NEW',
    createdAt INTEGER NOT NULL,
    resolvedAt INTEGER
);

CREATE TABLE IF NOT EXISTS reporters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticketId INTEGER NOT NULL REFERENCES tickets(id),
    userId INTEGER NOT NULL,
    username TEXT,
    firstName TEXT,
    reportedAt INTEGER NOT NULL,
    UNIQUE(ticketId, userId)
);

CREATE INDEX IF NOT EXISTS idxTicketsMsgId ON tickets(channelMsgId);
CREATE INDEX IF NOT EXISTS idxReportersTicket ON reporters(ticketId);
"""


@contextmanager
def getConn():
    conn = sqlite3.connect(config.dbPath)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def initDb():
    with getConn() as conn:
        conn.executescript(schema)


def findOpenTicketForMessage(channelMsgId: int):
    with getConn() as conn:
        row = conn.execute(
            "SELECT * FROM tickets WHERE channelMsgId = ? AND status = 'NEW' "
            "ORDER BY createdAt DESC LIMIT 1",
            (channelMsgId,),
        ).fetchone()
        return dict(row) if row else None


def createTicket(channelMsgId: int, reason: str) -> int:
    with getConn() as conn:
        cur = conn.execute(
            "INSERT INTO tickets (channelMsgId, reason, status, createdAt) VALUES (?, ?, 'NEW', ?)",
            (channelMsgId, reason, int(time.time())),
        )
        return cur.lastrowid


def addReporter(ticketId: int, userId: int, username: str, firstName: str) -> bool:
    with getConn() as conn:
        try:
            conn.execute(
                "INSERT INTO reporters (ticketId, userId, username, firstName, reportedAt) "
                "VALUES (?, ?, ?, ?, ?)",
                (ticketId, userId, username, firstName, int(time.time())),
            )
            return True
        except sqlite3.IntegrityError:
            return False


def getTicket(ticketId: int):
    with getConn() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticketId,)).fetchone()
        return dict(row) if row else None


def getReporters(ticketId: int):
    with getConn() as conn:
        rows = conn.execute(
            "SELECT * FROM reporters WHERE ticketId = ? ORDER BY reportedAt ASC",
            (ticketId,),
        ).fetchall()
        return [dict(r) for r in rows]


def setTicketStatus(ticketId: int, status: str, resolved: bool = False):
    with getConn() as conn:
        if resolved:
            conn.execute(
                "UPDATE tickets SET status = ?, resolvedAt = ? WHERE id = ?",
                (status, int(time.time()), ticketId),
            )
        else:
            conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticketId))