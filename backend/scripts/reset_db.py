#!/usr/bin/env python3
"""Reset the application's datastore:

- delete the SQLite database file
- delete the vector_store directory (FAISS index + metadata)
- delete the uploads directory
- recreate directories and re-run SQLAlchemy metadata.create_all

Run from the project root or backend folder:
  python backend/scripts/reset_db.py

Be careful: this permanently deletes data.
"""
import os
import sys
import shutil
import logging

# Ensure the backend directory is on sys.path so `import app` works whether the
# script is executed from the project root, the backend folder, or scripts/.
script_dir = os.path.dirname(__file__)
backend_dir = os.path.abspath(os.path.join(script_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reset_db")


def resolve_sqlite_path(db_url: str, backend_dir: str) -> str:
    # Expect formats like sqlite:///./mindcrush.db or sqlite:////absolute/path
    if not db_url.startswith("sqlite:"):
        raise RuntimeError("Only sqlite database URLs are supported by this reset script")

    # strip sqlite:/// or sqlite:////
    if db_url.startswith("sqlite:///"):
        rel = db_url.replace("sqlite:///", "")
        path = os.path.normpath(os.path.join(backend_dir, rel))
        return os.path.abspath(path)

    # fallback
    return os.path.abspath(db_url.replace("sqlite:", ""))


def main():
    # backend directory is one level up from this script
    script_dir = os.path.dirname(__file__)
    backend_dir = os.path.abspath(os.path.join(script_dir, ".."))

    logger.info("Backend dir: %s", backend_dir)

    # Database
    db_url = settings.database_url
    try:
        db_path = resolve_sqlite_path(db_url, backend_dir)
    except Exception as e:
        logger.error("Unsupported database URL: %s", db_url)
        raise

    if os.path.exists(db_path):
        logger.info("Removing database file: %s", db_path)
        os.remove(db_path)
    else:
        logger.info("No database file found at %s", db_path)

    # Vector store
    vector_store_path = os.path.abspath(os.path.join(backend_dir, settings.vector_store_path))
    if os.path.exists(vector_store_path):
        logger.info("Removing vector store directory: %s", vector_store_path)
        shutil.rmtree(vector_store_path)
    else:
        logger.info("No vector store directory at %s", vector_store_path)

    # Uploads
    uploads_path = os.path.abspath(os.path.join(backend_dir, settings.uploads_dir))
    if os.path.exists(uploads_path):
        logger.info("Removing uploads directory: %s", uploads_path)
        shutil.rmtree(uploads_path)
    else:
        logger.info("No uploads directory at %s", uploads_path)

    # Recreate directories
    os.makedirs(vector_store_path, exist_ok=True)
    os.makedirs(uploads_path, exist_ok=True)
    logger.info("Recreated directories: %s, %s", vector_store_path, uploads_path)

    # Recreate database schema
    try:
        from app.models import database as dbmod

        engine = getattr(dbmod, "engine", None)
        Base = getattr(dbmod, "Base", None)
        if engine is None or Base is None:
            logger.error("Could not find engine/Base in app.models.database")
            return

        Base.metadata.create_all(bind=engine)
        logger.info("Database schema created")
    except Exception as e:
        logger.exception("Failed to recreate database schema: %s", e)

    logger.info("Reset complete. Start your server and re-upload files to rebuild vector store and notes.")


if __name__ == "__main__":
    main()
