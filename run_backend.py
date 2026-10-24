import os
import sys
import subprocess


def main():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    venv_win = os.path.join(root_dir, "backend", ".venv", "Scripts", "python.exe")
    venv_nix = os.path.join(root_dir, "backend", ".venv", "bin", "python")

    if os.path.isfile(venv_win):
        python_exe = venv_win
    elif os.path.isfile(venv_nix):
        python_exe = venv_nix
    else:
        python_exe = sys.executable

    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    try:
        from backend.database import engine
        from backend.config import DATABASE_URL

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        database_name = getattr(DATABASE_URL, "database", None) if "DATABASE_URL" in locals() else None
        target = f"database '{database_name}'" if database_name else "configured MySQL database"
        print(
            f"Cannot connect to local MySQL {target}. Check MYSQL_PASSWORD in backend/.env "
            "and make sure MySQL is running.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"[AI Farm Guardian] Starting backend server using: {python_exe}")
    cmd = [
        python_exe, "-m", "uvicorn", "main:app",
        "--app-dir", "backend",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    sys.exit(subprocess.call(cmd, cwd=root_dir))

if __name__ == "__main__":
    main()
