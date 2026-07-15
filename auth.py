"""
Modul autentikasi sederhana berbasis SQLite.
Password TIDAK PERNAH disimpan dalam bentuk plaintext -
disimpan sebagai PBKDF2-HMAC-SHA256 hash + salt unik per user.
"""
import hashlib
import os
import secrets
import string
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "exam.db"

PBKDF2_ITERATIONS = 200_000


# ----------------------------------------------------------------------------
# Password hashing
# ----------------------------------------------------------------------------
def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Return (hash_hex, salt_hex). Generates a new salt if not provided."""
    if salt is None:
        salt_bytes = os.urandom(16)
        salt = salt_bytes.hex()
    else:
        salt_bytes = bytes.fromhex(salt)

    hashed = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS
    )
    return hashed.hex(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, stored_hash)


def generate_random_password(length: int = 10) -> str:
    """Generate a readable-but-strong random password (letters + digits)."""
    alphabet = string.ascii_letters + string.digits
    # Ensure at least one digit and one letter for a bit of predictability
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(c.isdigit() for c in pwd) and any(c.isalpha() for c in pwd):
            return pwd


# ----------------------------------------------------------------------------
# DB connection helper
# ----------------------------------------------------------------------------
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ----------------------------------------------------------------------------
# User operations
# ----------------------------------------------------------------------------
def get_user(username: str) -> sqlite3.Row | None:
    conn = get_conn()
    try:
        cur = conn.execute("SELECT * FROM users WHERE username = ?", (username,))
        return cur.fetchone()
    finally:
        conn.close()


def set_user_password(username: str, password: str):
    """Hash + store a new password for a user, clearing first-login flag."""
    hashed, salt = hash_password(password)
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE users
               SET password_hash = ?, salt = ?, is_first_login = 0, updated_at = ?
               WHERE username = ?""",
            (hashed, salt, now_iso(), username),
        )
        conn.commit()
    finally:
        conn.close()


def reset_user_password(username: str):
    """Admin action: clear a student's password so they must regenerate on next login."""
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE users
               SET password_hash = NULL, salt = NULL, is_first_login = 1, updated_at = ?
               WHERE username = ?""",
            (now_iso(), username),
        )
        conn.commit()
    finally:
        conn.close()


def authenticate(username: str, password: str) -> tuple[bool, str]:
    """Returns (success, message)."""
    user = get_user(username)
    if user is None:
        return False, "Akun tidak ditemukan."
    if user["password_hash"] is None:
        return False, "FIRST_LOGIN"
    if verify_password(password, user["password_hash"], user["salt"]):
        return True, "OK"
    return False, "Password salah."


# ----------------------------------------------------------------------------
# Forgot-password requests (student self-service -> admin approval)
# ----------------------------------------------------------------------------
def create_reset_request(nim: str) -> tuple[bool, str]:
    """Student submits a forgot-password request. Blocks duplicate pending requests."""
    conn = get_conn()
    try:
        user = conn.execute(
            "SELECT * FROM users WHERE username = ? AND role = 'student'", (nim,)
        ).fetchone()
        if user is None:
            return False, "NIM tidak ditemukan pada data mahasiswa."

        existing = conn.execute(
            "SELECT 1 FROM reset_requests WHERE nim = ? AND status = 'pending'", (nim,)
        ).fetchone()
        if existing is not None:
            return False, "Anda sudah memiliki permintaan reset yang belum diproses admin."

        conn.execute(
            """INSERT INTO reset_requests (nim, requested_at, status, resolved_at)
               VALUES (?, ?, 'pending', NULL)""",
            (nim, now_iso()),
        )
        conn.commit()
        return True, "Permintaan reset password telah dikirim ke admin."
    finally:
        conn.close()


def get_pending_requests():
    """Return pending reset requests joined with student name/kelas."""
    conn = get_conn()
    try:
        cur = conn.execute(
            """SELECT r.id, r.nim, r.requested_at, s.nama, s.kelas
               FROM reset_requests r
               JOIN students s ON s.nim = r.nim
               WHERE r.status = 'pending'
               ORDER BY r.requested_at ASC"""
        )
        return cur.fetchall()
    finally:
        conn.close()


def resolve_reset_request(request_id: int, approve: bool):
    """Mark a request resolved. If approve=True, also clears the student's password."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT nim FROM reset_requests WHERE id = ?", (request_id,)
        ).fetchone()
        if row is None:
            return
        conn.execute(
            "UPDATE reset_requests SET status = ?, resolved_at = ? WHERE id = ?",
            ("approved" if approve else "rejected", now_iso(), request_id),
        )
        conn.commit()
    finally:
        conn.close()

    if approve:
        reset_user_password(row["nim"])
