"""全局配置：全部从环境变量读取，提供合理默认值。"""
import os

# MongoDB 连接串（MONGODB_URI）与数据库名（DB_NAME）
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "survey_db")

# JWT 签名密钥（生产环境必须通过环境变量覆盖）
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me-in-production")
JWT_ALGORITHM = "HS256"
# 令牌有效期（分钟），默认 7 天
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))
