from flask import Flask, render_template, request, redirect, url_for, flash, session
import config
import os
import base64
import requests
from datetime import datetime, date
import random
import pymysql
# 导入智普官方SDK
from zai import ZhipuAiClient

# ==================== 全局初始化 ====================
# 初始化智普AI客户端（使用官方SDK）
zhipu_client = ZhipuAiClient(api_key=config.ZHIPU_API_KEY)

# 全局关闭SSL证书验证（解决部分网络环境下的接口调用问题）
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

# 初始化Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER
app.config['GENERATED_FONT_FOLDER'] = config.GENERATED_FONT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 最大上传10MB

# 确保必要文件夹存在
os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(config.GENERATED_FONT_FOLDER, exist_ok=True)


# ==================== 工具函数 ====================
# 检查上传文件格式是否合法
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS


# 1. 识别书法作品的字体类型（楷书/行书/草书等）
def recognize_font_type(img_path):
    try:
        # 图片转Base64
        with open(img_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        # 调用智普图文模型识别字体
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}},
                    {"type": "text",
                     "text": "请精准识别这张书法作品的字体类型，仅返回字体名称（如楷书、行书、草书、隶书、瘦金体、篆书），不要任何多余内容。"}
                ]
            }
        ]
        response = zhipu_client.chat.completions.create(
            model=config.ZHIPU_CHAT_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=20
        )
        font_type = response.choices[0].message.content.strip()

        # 标准化字体名称
        standard_fonts = ["楷书", "行书", "草书", "隶书", "瘦金体", "篆书"]
        return font_type if font_type in standard_fonts else "楷书"

    except Exception as e:
        print(f"字体识别失败：{e}")
        return "楷书"


# 2. AI书法打分（结合识别出的字体）
def ai_calligraphy_score(img_path, font_type):
    try:
        # 图片转Base64
        with open(img_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        # 调用智普AI打分
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}},
                    {"type": "text", "text": f"""你是专业的{font_type}书法评委，请完成以下任务：
1. 首先明确输出字体识别结果：{font_type}；
2. 对上传的{font_type}作品打0-10分的分数（保留1位小数）；
3. 从「笔画、结构、章法」3个维度各给出1条针对{font_type}的具体改进建议；
4. 语言简洁专业，不要多余内容。"""}
                ]
            }
        ]
        response = zhipu_client.chat.completions.create(
            model=config.ZHIPU_CHAT_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"AI评分失败：{e}\n\n字体识别结果：{font_type}\n默认评分：8.0分\n改进建议：\n1. 练习{font_type}基本笔画\n2. 参考名家碑帖调整结构\n3. 注意整体章法布局"


# 3. 图片主题解读 + 生成应景古诗（核心：用SDK实现）
def interpret_image_and_generate_poetry(img_path):
    try:
        # 图片转Base64
        with open(img_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")

        # 调用智普图文模型，同时完成“解读主题+生成古诗”
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}},
                    {"type": "text", "text": """请严格按照以下要求完成：
1. 第一行：简洁描述这张图片的主题（不超过50字，通俗易懂）；
2. 第二行开始：根据图片主题创作一首贴合书法艺术的五言律诗，仅返回古诗内容，分行显示，无标题、无解释。"""}
                ]
            }
        ]
        response = zhipu_client.chat.completions.create(
            model=config.ZHIPU_CHAT_MODEL,
            messages=messages,
            temperature=0.8,
            max_tokens=300
        )
        result = response.choices[0].message.content.strip()

        # 拆分主题和古诗（按换行分隔）
        parts = result.split('\n', 1)
        img_interpretation = parts[0] if len(parts) >= 1 else "无法解读图片主题"
        poetry_content = parts[1].strip() if len(parts) >= 2 else "墨韵凝香纸上行，笔锋流转意含情。\n千秋文脉凭君续，一砚清池照古今。"
        return img_interpretation, poetry_content

    except Exception as e:
        print(f"古诗生成失败：{e}")
        return "无法解读图片主题", "墨韵凝香纸上行，笔锋流转意含情。\n千秋文脉凭君续，一砚清池照古今。"


# 4. 调用智普SDK生成古诗对应的书法图片（核心：和你提供的代码一致）
def generate_font_image_with_zhipu_sdk(poetry_content, selected_font):
    try:
        # 构造书法生成的提示词（精准控制风格）
        prompt = f"""将以下古诗以{selected_font}书法风格书写在米黄色宣纸上：
{poetry_content}
要求：
1. {selected_font}风格特征明显（楷书工整方正、行书流畅自然、草书豪放洒脱、瘦金体纤细挺拔）；
2. 字体大小适中，笔画清晰可辨，适合书法临摹；
3. 无多余装饰，背景仅为纯色宣纸，无边框、无水印。"""

        # 调用智普官方SDK的文生图接口（和你提供的代码完全一致）
        response = zhipu_client.images.generations(
            model=config.ZHIPU_IMAGE_MODEL,
            prompt=prompt,
            n=1,  # 生成1张图片
            size="1024x1024"  # 图片尺寸
        )
        img_url = response.data[0].url

        # 下载生成的图片并保存到本地
        img_filename = f"zhipu_font_{datetime.now().strftime('%Y%m%d%H%M%S_%f')}.png"
        img_save_path = os.path.join(config.GENERATED_FONT_FOLDER, img_filename)
        img_response = requests.get(img_url, timeout=60)  # 延长超时时间
        with open(img_save_path, "wb") as f:
            f.write(img_response.content)

        # 返回图片的访问URL（供前端展示）
        return url_for('static', filename=f'img/generated_font/{img_filename}')

    except Exception as e:
        print(f"书法图片生成失败：{e}")
        return ""


# ==================== 路由函数 ====================
# 登录页
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not username or not password:
            flash("用户名和密码不能为空！")
            return render_template('login.html')

        # 验证用户
        conn = config.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM user WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash("登录成功！")
            return redirect(url_for('index'))
        else:
            flash("用户名或密码错误！")

    return render_template('login.html')


# 注册页
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        confirm_pwd = request.form.get('confirm_pwd', '').strip()

        # 校验输入
        if not username or not password:
            flash("用户名和密码不能为空！")
            return render_template('register.html')
        if password != confirm_pwd:
            flash("两次密码输入不一致！")
            return render_template('register.html')

        # 注册用户
        conn = config.get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO user (username, password) VALUES (%s, %s)", (username, password))
            flash("注册成功！请登录")
            return redirect(url_for('login'))
        except pymysql.IntegrityError:
            flash("用户名已存在！")
        finally:
            cursor.close()
            conn.close()

    return render_template('register.html')


# 忘记密码页
@app.route('/forget_pwd', methods=['GET', 'POST'])
def forget_pwd():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        new_pwd = request.form.get('new_pwd', '').strip()

        if not username or not new_pwd:
            flash("用户名和新密码不能为空！")
            return render_template('forget_pwd.html')

        # 修改密码
        conn = config.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE user SET password = %s WHERE username = %s", (new_pwd, username))
        if cursor.rowcount > 0:
            flash("密码修改成功！请登录")
            return redirect(url_for('login'))
        else:
            flash("用户名不存在！")
        cursor.close()
        conn.close()

    return render_template('forget_pwd.html')


# 退出登录
@app.route('/logout')
def logout():
    session.clear()
    flash("已退出登录！")
    return redirect(url_for('login'))


# 首页
@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = config.get_db_connection()
    cursor = conn.cursor()

    # 每日推荐字帖（春节特殊推荐）
    today = date.today()
    if today.month == 1 and today.day == 1:
        cursor.execute("SELECT * FROM zitie WHERE title LIKE '%元日%' LIMIT 1")
    else:
        cursor.execute("SELECT * FROM zitie ORDER BY RAND() LIMIT 1")
    daily_recommend = cursor.fetchone()

    # 朝代时间轴
    cursor.execute("SELECT * FROM dynasty ORDER BY start_year")
    dynasties = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('index.html',
                           daily_recommend=daily_recommend,
                           dynasties=dynasties)


# 朝代查询页
@app.route('/dynasty', methods=['GET'])
def dynasty():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    dynasty_id = request.args.get('id', '').strip()
    conn = config.get_db_connection()
    cursor = conn.cursor()

    # 获取所有朝代
    cursor.execute("SELECT * FROM dynasty ORDER BY start_year")
    all_dynasties = cursor.fetchall()

    # 获取选中朝代的古诗
    poetry_list = []
    if dynasty_id and dynasty_id.isdigit():
        cursor.execute("""
            SELECT p.*, d.name as dynasty_name 
            FROM poetry p LEFT JOIN dynasty d ON p.dynasty_id = d.id 
            WHERE p.dynasty_id = %s
        """, (dynasty_id,))
        poetry_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('dynasty.html',
                           dynasties=all_dynasties,
                           poetry_list=poetry_list,
                           selected_id=dynasty_id)


# 字帖库页
@app.route('/zitie')
def zitie():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    dynasty_id = request.args.get('dynasty_id', '').strip()
    conn = config.get_db_connection()
    cursor = conn.cursor()

    # 获取所有朝代
    cursor.execute("SELECT * FROM dynasty ORDER BY start_year")
    all_dynasties = cursor.fetchall()

    # 获取字帖列表
    zitie_list = []
    if dynasty_id and dynasty_id.isdigit():
        cursor.execute("SELECT * FROM zitie WHERE dynasty_id = %s", (dynasty_id,))
    else:
        cursor.execute("SELECT * FROM zitie")
    zitie_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('zitie.html',
                           dynasties=all_dynasties,
                           zitie_list=zitie_list,
                           selected_dynasty=dynasty_id)


# 书法字典页
@app.route('/dictionary', methods=['GET', 'POST'])
def dictionary():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    search_type = request.args.get('type', 'title')
    keyword = request.args.get('keyword', '').strip()
    dictionary_list = []

    conn = config.get_db_connection()
    cursor = conn.cursor()

    # 多条件搜索
    if keyword:
        if search_type == 'title':
            cursor.execute("SELECT * FROM zitie WHERE title LIKE %s", (f"%{keyword}%",))
        elif search_type == 'author':
            cursor.execute("SELECT * FROM zitie WHERE author LIKE %s", (f"%{keyword}%",))
        elif search_type == 'character':
            cursor.execute("SELECT * FROM zitie WHERE content LIKE %s", (f"%{keyword}%",))
        dictionary_list = cursor.fetchall()
    else:
        # 默认显示前10个
        cursor.execute("SELECT * FROM zitie LIMIT 10")
        dictionary_list = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('dictionary.html',
                           dictionary_list=dictionary_list,
                           search_type=search_type,
                           keyword=keyword)


# AI功能页（核心修改：全流程用SDK实现）
@app.route('/ai', methods=['GET', 'POST'])
def ai():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 初始化页面变量
    score_result = ""
    poetry_result = ""
    score_img_path = ""
    poetry_img_path = ""
    font_type = ""
    font_image_url = ""  # AI生成的书法图片URL
    selected_font = ""
    img_interpretation = ""

    # 处理书法打分请求
    if request.method == 'POST' and 'score_img' in request.files:
        file = request.files['score_img']
        if file and file.filename != '' and allowed_file(file.filename):
            # 保存上传的图片
            filename = f"score_{datetime.now().strftime('%Y%m%d%H%M%S_%f')}_{file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            score_img_path = url_for('static', filename=f'img/upload/{filename}')

            # 识别字体 + 生成评分
            font_type = recognize_font_type(file_path)
            score_result = ai_calligraphy_score(file_path, font_type)

    # 处理古诗+书法图片生成请求
    elif request.method == 'POST' and 'poetry_img' in request.files:
        file = request.files['poetry_img']
        if file and file.filename != '' and allowed_file(file.filename):
            # 保存参考图片
            filename = f"poetry_{datetime.now().strftime('%Y%m%d%H%M%S_%f')}_{file.filename}"
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            poetry_img_path = url_for('static', filename=f'img/upload/{filename}')

            # 获取用户选择的书法字体
            selected_font = request.form.get('font_type', '楷书')

            # 核心流程：解读图片→生成古诗→生成书法图片
            img_interpretation, poetry_result = interpret_image_and_generate_poetry(file_path)
            font_image_url = generate_font_image_with_zhipu_sdk(poetry_result, selected_font)

    # 渲染页面（保留所有状态）
    return render_template('ai.html',
                           score_result=score_result,
                           score_img_path=score_img_path,
                           font_type=font_type,
                           poetry_result=poetry_result,
                           poetry_img_path=poetry_img_path,
                           font_image_url=font_image_url,
                           selected_font=selected_font,
                           img_interpretation=img_interpretation)


# 404页面
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# 主函数
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)