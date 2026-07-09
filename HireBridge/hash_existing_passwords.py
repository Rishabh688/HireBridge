from flask_bcrypt import Bcrypt # type: ignore
from db import get_connection

bcrypt = Bcrypt()

conn = get_connection()
cur = conn.cursor(dictionary=True)

cur.execute("SELECT user_id, password FROM users")
users = cur.fetchall()

for user in users:
    plain_password = user["password"]

    if plain_password.startswith("$2b$"):
        continue

    hashed = bcrypt.generate_password_hash(plain_password).decode("utf-8")

    cur.execute(
        "UPDATE users SET password=%s WHERE user_id=%s",
        (hashed, user["user_id"])
    )

conn.commit()
cur.close()
conn.close()

print("All passwords successfully hashed")

