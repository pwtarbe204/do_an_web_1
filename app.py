from flask import Flask, flash, render_template, redirect, url_for, request, session, jsonify
from authlib.integrations.flask_client import OAuth
from flask_mail import Mail, Message
from flask import Flask
import random
import os
import dbo
import uuid
from dotenv import load_dotenv
import json
from werkzeug.utils import secure_filename
from datetime import datetime
import traceback
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'abcabc'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

conn, cursor = dbo.connect("localhost", "doan3_demo", "postgres", "123456")


oauth = OAuth(app)

google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

#################################################################################################################
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
mail = Mail(app)

# Gửi mã xác minh
def send_verification_email(email, code):
    msg = Message('Mã xác minh tài khoản', sender=app.config['MAIL_USERNAME'], recipients=[email])
    msg.body = f'Mã xác minh của bạn là: {code}'
    mail.send(msg)

@app.route('/send-code', methods=['POST'])
def send_code():
    email = request.form.get('email')
    if not email:
        return redirect(url_for('index'))

    code = str(random.randint(100000, 999999))
    session['verification_code'] = code
    session['email'] = email

    send_verification_email(email, code)
    return redirect(url_for('verify'))


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        code_entered = request.form.get('code')
        if code_entered == session.get('verification_code'):
            email = session.get('email')

            # Kiểm tra xem email đã có trong Users chưa
            cursor.execute("SELECT id FROM Users WHERE email = %s", (email,))
            existing_user = cursor.fetchone()

            if existing_user:
                user_id = existing_user[0]
                flash("Đăng nhập thành công!", "success")
            else:
                user_id = str(uuid.uuid4())
                # cursor.execute("INSERT INTO Users (id, email) VALUES (%s, %s)", 
                #                (user_id, email))
                cursor.execute("INSERT INTO Users (id, email, type) VALUES (%s, %s, %s)", 
               (user_id, email, 'email'))
                conn.commit()
                flash("Đăng ký thành công!", "success")

            # Đảm bảo EmailUsers tồn tại
            cursor.execute("SELECT * FROM EmailUsers WHERE user_id = %s", (user_id,))
            email_user = cursor.fetchone()

            if not email_user:
                cursor.execute("INSERT INTO EmailUsers (user_id, last_login_code, verified) VALUES (%s, %s, %s)",
                               (user_id, code_entered, True))
                conn.commit()

            session['user'] = {
                'type': 'email',
                'email': email,
                'picture': url_for('static', filename='user.png')
            }

            return redirect(url_for('index'))
        else:
            flash("❌ Mã xác minh không đúng!", "error")
    return render_template('verify.html')

#####################################


@app.route('/edit_post/<uuid:post_id>', methods=['GET'])
def edit_post(post_id):
    if 'user' not in session:
        return redirect(url_for('dangkydangnhap'))

    # Lấy bài viết
    cursor.execute("""
        SELECT id, title, description, image, ingredients, serving_size, cooking_time, category_id
        FROM posts
        WHERE id = %s
    """, (str(post_id),))
    post_row = cursor.fetchone()

    if not post_row:
        return "Bài viết không tồn tại", 404

    image_filename = os.path.basename(str(post_row[3])) if post_row[3] else ''

    # Lấy các bước
    cursor.execute("""
        SELECT step_number, description, image
        FROM steps
        WHERE post_id = %s
        ORDER BY step_number
    """, (str(post_id),))
    steps = cursor.fetchall()

    # Xử lý dữ liệu trả về
    post = {
        'id': post_row[0],
        'title': post_row[1],
        'description': post_row[2],
        'image_url': url_for('static', filename=f"uploads/{image_filename}") if image_filename else '',
        'ingredients': post_row[4],
        'serving_size': post_row[5],
        'cooking_time': post_row[6],
        'category_id': post_row[7],
        'steps': [
            {
                'step_number': s[0],
                'description': s[1],
                'image_url': url_for('static', filename=f"uploads/{os.path.basename(s[2])}") if s[2] else ''
            }
            for s in steps
        ]
    }

    return render_template('edit_baiviet.html', post=post)



# @app.route('/update_post/<uuid:post_id>', methods=['POST'])
# def update_post(post_id):
#     if 'user' not in session:
#         return redirect(url_for('dangkydangnhap'))

#     title = request.form.get('title')
#     description = request.form.get('description')
#     ingredients = request.form.get('ingredients')
#     serving_size = request.form.get('serving_size')
#     cooking_time = request.form.get('cooking_time')
#     category_id = request.form.get('category_id')

#     # Cập nhật bài viết
#     cursor.execute("""
#         UPDATE posts
#         SET title=%s, description=%s, ingredients=%s, serving_size=%s, cooking_time=%s, category_id=%s
#         WHERE id=%s
#     """, (title, description, ingredients, serving_size, cooking_time, category_id, str(post_id)))
#     conn.commit()

#     # Cập nhật các bước (xóa cũ rồi thêm lại)
#     cursor.execute("DELETE FROM steps WHERE post_id = %s", (str(post_id),))
#     step_descriptions = request.form.getlist('step_description[]')

#     for i, desc in enumerate(step_descriptions):
#         cursor.execute("""
#             INSERT INTO steps (post_id, step_number, description)
#             VALUES (%s, %s, %s)
#         """, (str(post_id), i+1, desc))

#     conn.commit()

#     flash("Bài viết đã được cập nhật!", "success")
#     return redirect(url_for('danhsach_baidang'))
@app.route('/update_post/<uuid:post_id>', methods=['POST'])
def update_post(post_id):
    if 'user' not in session:
        return jsonify({"error": "Bạn chưa đăng nhập"}), 401

    try:
        title = request.form.get('title')
        description = request.form.get('description')
        ingredients = request.form.get('ingredients')
        serving_size = request.form.get('serving_size')
        cooking_time = request.form.get('cooking_time')
        category_id = request.form.get('category_id')

        # Nếu có ảnh mới cho món chính thì lưu (luu path giống upload_post -> 'static/uploads/..')
        image_db_path = None
        if 'image' in request.files and request.files['image'] and request.files['image'].filename:
            file = request.files['image']
            filename = secure_filename(file.filename)
            ext = os.path.splitext(filename)[1]
            new_filename = f"{uuid.uuid4()}{ext}"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)  # 'static/uploads/..'
            file.save(save_path)
            image_db_path = save_path

        # Cập nhật posts (nếu có ảnh mới thì cập nhật cột image, nếu không thì giữ nguyên)
        if image_db_path:
            cursor.execute("""
                UPDATE posts
                SET title=%s, description=%s, ingredients=%s, serving_size=%s,
                    cooking_time=%s, category_id=%s, image=%s
                WHERE id=%s
            """, (title, description, ingredients, serving_size,
                  cooking_time, category_id, image_db_path, str(post_id)))
        else:
            cursor.execute("""
                UPDATE posts
                SET title=%s, description=%s, ingredients=%s, serving_size=%s,
                    cooking_time=%s, category_id=%s
                WHERE id=%s
            """, (title, description, ingredients, serving_size,
                  cooking_time, category_id, str(post_id)))
        conn.commit()

        # Xóa bước cũ (xóa tất cả rồi insert lại theo thứ tự mới)
        cursor.execute("DELETE FROM steps WHERE post_id = %s", (str(post_id),))
        conn.commit()

        # Lấy steps từ JSON (frontend gửi: step_number, description, image_field, existing_image)
        steps_json = request.form.get('steps')
        if steps_json:
            steps = json.loads(steps_json)
            for step in steps:
                step_number = step.get('step_number')
                step_desc = step.get('description')
                image_field = step.get('image_field')         # key file nếu user upload file mới
                existing_image = step.get('existing_image')   # url hiện tại của ảnh (nếu có) để giữ lại

                step_image_db = None
                # 1) nếu user upload file mới cho bước thì lưu file mới
                if image_field in request.files and request.files[image_field] and request.files[image_field].filename:
                    f = request.files[image_field]
                    filename = secure_filename(f.filename)
                    ext = os.path.splitext(filename)[1]
                    new_filename = f"{uuid.uuid4()}{ext}"
                    save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
                    f.save(save_path)
                    step_image_db = save_path
                # 2) nếu user không upload file mới nhưng bước cũ có ảnh (existing_image), giữ lại ảnh cũ
                elif existing_image:
                    # existing_image có thể là full url hoặc '/static/uploads/xxx', lấy basename -> build lại path DB 'static/uploads/xxx'
                    basename = os.path.basename(existing_image)
                    step_image_db = os.path.join(app.config['UPLOAD_FOLDER'], basename)

                cursor.execute("""
                    INSERT INTO steps (post_id, step_number, description, image)
                    VALUES (%s, %s, %s, %s)
                """, (str(post_id), step_number, step_desc, step_image_db))
        conn.commit()

        return jsonify({"message": "Bài viết đã được cập nhật!"}), 200

    except Exception as e:
        conn.rollback()
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

######################################################3
@app.route('/favorite/<uuid:post_id>', methods=['POST'])
def add_favorite(post_id):
    if 'user' not in session:
        return jsonify({'redirect': url_for('dangkydangnhap')}), 401

    email = session['user']['email']
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()
    if not user_row:
        return jsonify({'error': 'Không tìm thấy người dùng'}), 404

    user_id = user_row[0]

    try:
        cursor.execute("""
            INSERT INTO favorite_posts (user_id, post_id)
            VALUES (%s, %s)
            ON CONFLICT (user_id, post_id) DO NOTHING
        """, (user_id, str(post_id)))
        conn.commit()
        return jsonify({'success': True, 'message': 'Đã thêm vào danh sách yêu thích!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500


@app.route('/favorites')
def list_favorites():
    if 'user' not in session:
        return redirect(url_for('dangkydangnhap'))

    email = session['user']['email']
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()
    if not user_row:
        return "Không tìm thấy người dùng", 404

    user_id = user_row[0]
    cursor.execute("""
        SELECT p.id, p.title, p.image, p.created_at
        FROM favorite_posts f
        JOIN posts p ON f.post_id = p.id
        WHERE f.user_id = %s
        ORDER BY f.created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()

    favorites = [{
        'id': row[0],
        'title': row[1],
        'image': row[2] if row[2] else '/static/default.jpg',
        'created_at': row[3].strftime('%d/%m/%Y')
    } for row in rows]

    return render_template('favorites.html', favorites=favorites, user=session.get('user'))


@app.route('/favorite/<uuid:post_id>', methods=['DELETE'])
def remove_favorite(post_id):
    if 'user' not in session:
        return jsonify({'error': 'Bạn cần đăng nhập'}), 401

    email = session['user']['email']
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()
    if not user_row:
        return jsonify({'error': 'Không tìm thấy người dùng'}), 404

    user_id = user_row[0]

    try:
        cursor.execute("""
            DELETE FROM favorite_posts
            WHERE user_id = %s AND post_id = %s
        """, (user_id, str(post_id)))
        conn.commit()
        return jsonify({'success': True, 'message': 'Đã xóa khỏi danh sách yêu thích!'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': str(e)}), 500


##########################################################################################################3
# @app.route("/search")
# def search():
#     q = request.args.get("q", "").strip()
#     if not q:
#         return redirect(url_for("index"))

#     cursor.execute("""
#         SELECT id, title, description, image
#         FROM posts
#         WHERE title ILIKE %s OR description ILIKE %s OR ingredients ILIKE %s
#         ORDER BY created_at DESC
#     """, (f"%{q}%", f"%{q}%", f"%{q}%"))
    
#     posts = cursor.fetchall()

#     return render_template("search_result.html", posts=posts, search_query=q)

@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect(url_for("index"))
    user = session.get('user')
    cursor.execute("""
        SELECT id, title, description, image
        FROM posts
        WHERE title ILIKE %s
        ORDER BY created_at DESC
    """, (f"%{q}%",))
    
    posts = cursor.fetchall()

    return render_template("search_result.html", posts=posts, user=user, search_query=q)


@app.route('/category/<int:category_id>')
def posts_by_category(category_id):
    user = session.get('user')

    cursor.execute("""
        SELECT id, title, image, created_at, description
        FROM posts
        WHERE category_id = %s
        ORDER BY created_at DESC
    """, (category_id,))
    rows = cursor.fetchall()

    posts = [{
        'id': row[0],
        'title': row[1],
        'image': row[2] if row[2] else '/static/default.jpg',
        'created_at': row[3].strftime('%d/%m/%Y'),
        'description': row[4]
    } for row in rows]

    # Lấy tên danh mục
    cursor.execute("SELECT name FROM categories WHERE id = %s", (category_id,))
    category_name = cursor.fetchone()
    category_name = category_name[0] if category_name else "Danh mục"

    return render_template('posts_by_category.html',
                           posts=posts,
                           category_name=category_name,
                           user=user)




@app.route('/post/<uuid:post_id>/comment', methods=['POST'])
def add_comment(post_id):
    if 'user' not in session:
        # Lưu URL hiện tại để quay lại sau khi đăng nhập
        session['next_url'] = url_for('view_post', post_id=post_id)
        return jsonify({'redirect': url_for('dangkydangnhap')}), 401

    data = request.get_json()
    content = data.get('content', '').strip()
    if not content:
        return jsonify({'success': False, 'error': 'Nội dung bình luận không được để trống.'}), 400

    email = session['user']['email']
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()
    if not user_row:
        return jsonify({'success': False, 'error': 'Không tìm thấy người dùng.'}), 404

    user_id = user_row[0]
    comment_id = str(uuid.uuid4())

    cursor.execute("""
        INSERT INTO comments (id, post_id, user_id, content)
        VALUES (%s, %s, %s, %s)
    """, (comment_id, str(post_id), user_id, content))
    conn.commit()

    return jsonify({'success': True})


@app.route('/post/<uuid:post_id>')
def view_post(post_id):
    # Truy xuất bài viết kèm tên danh mục
    cursor.execute("""
        SELECT 
            posts.id, posts.title, posts.description, posts.image, posts.created_at,
            posts.ingredients, posts.serving_size, posts.cooking_time,
            users.email, users.type,
            categories.id AS category_id,
            categories.name AS category_name
        FROM posts
        JOIN users ON posts.user_id = users.id
        LEFT JOIN categories ON posts.category_id = categories.id
        WHERE posts.id = %s
    """, (str(post_id),))
    post_row = cursor.fetchone()

    if not post_row:
        return "Bài viết không tồn tại", 404

    post = {
        'id': post_row[0],
        'title': post_row[1],
        'description': post_row[2],
        'image': post_row[3],
        'created_at': post_row[4].strftime('%d/%m/%Y'),
        'ingredients': post_row[5],
        'serving_size': post_row[6],
        'cooking_time': post_row[7],
        'author': post_row[8],
        'type': post_row[9],
        'category_id': post_row[10],
        'category_name': post_row[11]
    }

    # Truy xuất các bước
    cursor.execute("""
        SELECT step_number, description, image
        FROM steps
        WHERE post_id = %s
        ORDER BY step_number ASC
    """, (str(post_id),))
    steps = cursor.fetchall()

    # ✅ Truy vấn 4 bài viết cùng danh mục (loại trừ bài hiện tại)
    cursor.execute("""
        SELECT id, title, image
        FROM posts
        WHERE category_id = %s AND id != %s
        ORDER BY created_at DESC
        LIMIT 4
    """, (post['category_id'], str(post_id)))
    related_posts = cursor.fetchall()

    cursor.execute("""
        SELECT 
            c.content, 
            c.created_at, 
            u.email, 
            u.type,
            gu.picture
        FROM comments c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN GoogleUsers gu ON u.id = gu.user_id
        WHERE c.post_id = %s
        ORDER BY c.created_at DESC
    """, (str(post_id),))
    raw_comments = cursor.fetchall()

    comments = []
    for content, created_at, email, acc_type, picture in raw_comments:
        if acc_type == 'google' and picture:
            avatar = picture
        else:
            avatar = url_for('static', filename='user.png')
        comments.append({
            'content': content,
            'created_at': created_at,
            'email': email,
            'avatar': avatar
        })


    # Lấy user từ session
    user = session.get('user')

    # Truyền dữ liệu vào template
    return render_template(
        'post_detail.html',
        post=post,
        steps=steps,
        related_posts=related_posts,
        user=user,
        comments=comments
    )

# @app.route('/edit_post/<uuid:post_id>')
# def edit_post(post_id):
#     # TODO: Load bài viết và chuyển đến form chỉnh sửa
#     return f'Chỉnh sửa bài viết {post_id}'

@app.route('/delete_post/<uuid:post_id>', methods=['POST'])
def delete_post(post_id):
    cursor.execute("DELETE FROM posts WHERE id = %s", (str(post_id),))
    conn.commit()
    flash("Đã xoá bài viết.", "success")
    return redirect(url_for('danhsach_baidang'))

# @app.route('/')
# def index():
#     user = session.get('user')
    
#     cursor.execute("""
#         SELECT posts.id, title, image, created_at, description
#         FROM posts
#         ORDER BY created_at DESC
#         LIMIT 20
#     """)
#     post_rows = cursor.fetchall()
#     posts = [{
#         'id': row[0],
#         'title': row[1],
#         'image': row[2] if row[2] else '/static/default.jpg',
#         'created_at': row[3],
#         'description': row[4]
#     } for row in post_rows]

#     return render_template('index.html', user=user, posts=posts)

@app.route('/')
def index():
    user = session.get('user')

    cursor.execute("""
        SELECT id, title, image, created_at, description, category_id, category_name
        FROM (
            SELECT p.id, p.title, p.image, p.created_at, p.description, p.category_id, c.name AS category_name,
                   ROW_NUMBER() OVER (PARTITION BY p.category_id ORDER BY p.created_at DESC) as rn
            FROM posts p
            JOIN categories c ON p.category_id = c.id
        ) sub
        WHERE rn <= 10
        ORDER BY category_id, created_at DESC
    """)
    
    post_rows = cursor.fetchall()

    # categories = defaultdict(list)
    # for row in post_rows:
    #     categories[row[6]].append({
    #         'id': row[0],
    #         'title': row[1],
    #         'image': row[2] if row[2] else '/static/default.jpg',
    #         'created_at': row[3],
    #         'description': row[4]
    #     })

    categories = defaultdict(list)
    for row in post_rows:
        categories[(row[5], row[6])].append({   # key = (category_id, category_name)
            'id': row[0],
            'title': row[1],
            'image': row[2] if row[2] else '/static/default.jpg',
            'created_at': row[3],
            'description': row[4]
    })

    return render_template('index.html', user=user, categories=categories)


@app.route('/danhsach_baidang')
def danhsach_baidang():
    if 'user' not in session:

        return redirect(url_for('dangkydangnhap'))

    email = session['user']['email']
    cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
    user_row = cursor.fetchone()
    if not user_row:
        return "Không tìm thấy người dùng", 404
    user = session.get('user')
    user_id = user_row[0]

    # Truy vấn các bài viết của người dùng
    cursor.execute("""
        SELECT id, title, image, created_at
        FROM posts
        WHERE user_id = %s
        ORDER BY created_at DESC
    """, (user_id,))
    rows = cursor.fetchall()

    my_posts = [{
        'id': row[0],
        'title': row[1],
        'image': row[2] if row[2] else '/static/default.jpg',
        'created_at': row[3].strftime('%d/%m/%Y')
    } for row in rows]

    return render_template('danhsach_baidang.html', my_posts=my_posts, user=user)




@app.route('/dangky-dangnhap')
def dangkydangnhap():
    return render_template('dangky-dangnhap.html')

@app.route('/vietmonmoi',methods=['POST', 'GET'])
def vietmonmoi():
    if 'user' not in session:
        session['next_url'] = url_for('vietmonmoi')
        return render_template('dangky-dangnhap.html')
        #return redirect(url_for('dangky-dangnhap'))
    
    return render_template('vietmonmoi.html')

#############################            Phần login bằng google          ######################################
######## xử lý nút nhấn đăng nhập google #######
@app.route('/login')              
def login():
    # Tạo nonce và lưu vào session
    nonce = uuid.uuid4().hex
    session['nonce'] = nonce

    redirect_uri = url_for('auth_callback', _external=True)
    return google.authorize_redirect(redirect_uri, nonce=nonce)


@app.route('/auth/callback')
def auth_callback():
    token = google.authorize_access_token()
    nonce = session.pop('nonce', None)
    if not nonce:
        return 'Missing nonce', 400

    user = google.parse_id_token(token, nonce=nonce)
    email = user.get('email')
    sub = user.get('sub')
    name = user.get('name')
    picture = user.get('picture')

    # Kiểm tra email đã có chưa trong bảng Users
    cursor.execute("SELECT id FROM Users WHERE email = %s", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        user_id = existing_user[0]
    else:
        user_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO Users (id, email, type) VALUES (%s, %s, %s)", 
               (user_id, email, 'google'))
        # cursor.execute("INSERT INTO Users (id, email) VALUES (%s, %s)", 
        #                (user_id, email))
        conn.commit()

    # Đảm bảo GoogleUsers tồn tại
    cursor.execute("SELECT * FROM GoogleUsers WHERE sub = %s", (sub,))
    google_user = cursor.fetchone()

    if not google_user:
        cursor.execute("""
            INSERT INTO GoogleUsers (user_id, sub, name, picture)
            VALUES (%s, %s, %s, %s)
        """, (user_id, sub, name, picture))
        conn.commit()

    # Lưu vào session
    session['user'] = {
        'type': 'google',
        'email': email,
        'name': name,
        'picture': picture
    }

    return redirect(url_for('index'))



####################################### Đăng xuất #######################################################
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

######################################## Đăng nhập bằng google ############################################
@app.route('/upload_post', methods=['POST'])
def upload_post():
    print("ok")
    try:
        if 'user' not in session:
            return jsonify({'error': 'Bạn chưa đăng nhập.'}), 401

        email = session['user']['email']
        cursor.execute("SELECT id FROM Users WHERE email = %s", (email,))
        user_row = cursor.fetchone()
        if not user_row:
            return jsonify({'error': 'Không tìm thấy người dùng.'}), 404
        user_id = user_row[0]
        print("ok roi")
        # Lấy dữ liệu từ form
        post_id = str(uuid.uuid4())
        title = request.form.get('title')
        description = request.form.get('description')
        ingredients = request.form.get('ingredients')
        serving_size = request.form.get('serving_size')
        cooking_time = request.form.get('cooking_time')
        category_id = int(request.form.get('category_id') or 0)
        image_file = request.files.get('image')
        status = 'đã đăng'
        image_path = None
        if image_file:
            filename = f"{post_id}_main_{secure_filename(image_file.filename)}"
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)

        # Lưu bài đăng
        # cursor.execute("""
        #     INSERT INTO posts (id, user_id, category_id, title, description, ingredients,
        #                        serving_size, cooking_time, image, created_at)
        #     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        # """, (
        #     post_id, user_id, category_id, title, description, ingredients,
        #     serving_size, cooking_time, image_path
        # ))
        print("đến upload")

        cursor.execute("""
         INSERT INTO posts (id, user_id, category_id, title, description, ingredients,
                    serving_size, cooking_time, image, created_at, status)
         VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
         """, (
            post_id, user_id, category_id, title, description, ingredients,
            serving_size, cooking_time, image_path, status
        ))

        print("đến upload 2")
        # Xử lý các bước
        steps_raw = request.form.get('steps')
        steps = json.loads(steps_raw)
        print("đến upload 3")
        for step in steps:
            step_number = step['step_number']
            step_desc = step['description']
            image_field = step['image_field']
            step_img_file = request.files.get(image_field)

            step_img_path = None
            if step_img_file:
                filename = f"{post_id}_step{step_number}_{secure_filename(step_img_file.filename)}"
                step_img_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                step_img_file.save(step_img_path)

            cursor.execute("""
                INSERT INTO steps (post_id, step_number, description, image)
                VALUES (%s, %s, %s, %s)
            """, (post_id, step_number, step_desc, step_img_path))

        conn.commit()
        return jsonify({'message': 'Đăng món ăn thành công!'}), 200

    except Exception as e:
          print("Lỗi:", e)
    traceback.print_exc()  # In chi tiết lỗi
    return jsonify({'error': str(e)}), 500  # Chỉ để debug


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
