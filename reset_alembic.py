from app import create_app, db
from sqlalchemy import text

app = create_app()

with app.app_context():
    conn = db.engine.connect()
    conn.execute(text("DELETE FROM alembic_version;"))
    conn.close()
    print("Alembic version table cleared.")
