from db import get_conn, db_lock
from hashPswd import hash_password

username = "admin"
email = "admin@example.com"
password = "admin123"
hashed_password = hash_password(password)

with db_lock:
    with get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE username = ? OR email = ?",
            [username, email],
        ).fetchone()

        if not exists:
            next_id = conn.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM users"
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO users (id, username, email, password) VALUES (?, ?, ?, ?)",
                [next_id, username, email, hashed_password],
            )
            conn.commit()
            print("✅ Створено користувача:")
            print(f"   Логін: {username}")
            print(f"   Email: {email}")
            print(f"   Пароль: {password}")
        else:
            print("ℹ️  Користувач вже існує. Поточні облікові записи:")
            users = conn.execute("SELECT username, email FROM users").fetchall()
            for existing_username, existing_email in users:
                print(f"   - {existing_username} ({existing_email})")
