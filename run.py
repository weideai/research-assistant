import os
from pathlib import Path

from app import create_app, db
from app.migration_service import run_migrations_with_backup


app = create_app()


if __name__ == "__main__":
    run_migrations_with_backup(app, db, Path(__file__).resolve().parent / "migrations")
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5001")),
        debug=app.config["APP_ENV"] != "production",
    )
