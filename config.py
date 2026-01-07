import pymysql
from pymysql.err import OperationalError

# ==================== 数据库配置 ====================
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '123456',    # 替换为你的MySQL密码
    'database': 'qingmo_db', # 替换为你的数据库名
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'autocommit': True
}

def get_db_connection():
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except OperationalError as e:
        print(f"数据库连接失败！错误：{e}")
        raise

# ==================== 智普AI配置（关键） ====================
ZHIPU_API_KEY = "60ddba5baf344b42b45f905132b5f20f.9BXJU7s2ft1n9VdU"  # 替换为你的API Key
ZHIPU_CHAT_MODEL = "glm-4v-plus"        # 图文理解/聊天模型
ZHIPU_IMAGE_MODEL = "cogview-4-250304"  # 文生图模型（和你提供的代码一致）

# ==================== 项目基础配置 ====================
UPLOAD_FOLDER = "static/img/upload/"               # 上传图片存储路径
GENERATED_FONT_FOLDER = "static/img/generated_font/"  # AI生成书法图片存储路径
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}  # 允许的上传格式
SECRET_KEY = "qingmo_2026_security_key_123456"     # Flask会话密钥