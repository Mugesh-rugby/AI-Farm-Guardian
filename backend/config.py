import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("MYSQL_USER", "root").strip(),
    password=os.getenv("MYSQL_PASSWORD", ""),
    host=os.getenv("MYSQL_HOST", "127.0.0.1").strip(),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    database=os.getenv("MYSQL_DATABASE", "farm_guardian").strip(),
    query={"charset": "utf8mb4"},
)
JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
if not JWT_SECRET or len(JWT_SECRET.encode("utf-8")) < 32:
    raise RuntimeError("Set JWT_SECRET to a private value of at least 32 bytes in backend/.env.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()
GROQ_VISION_MODEL = os.getenv("GROQ_VISION_MODEL", "qwen/qwen3.8-27b").strip()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "").strip()
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = "none" if COOKIE_SECURE else "lax"
UPLOAD_DIR = BASE_DIR / "uploads"
MODEL_CHECKPOINT = Path(
    os.getenv("MODEL_CHECKPOINT", str(BASE_DIR / "models" / "efficientnetv2_s.pth"))
).expanduser()
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
