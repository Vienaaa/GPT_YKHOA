import os
import re
import subprocess
import pyodbc
import pandas as pd
import docx
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy




app = Flask(__name__)
conn_str = (
    r'DRIVER={SQL Server};'
    r'SERVER=TRANVIEN\SQLEXPRESS;'
    r'DATABASE=master;'
    r'UID=sa;'
    r'PWD=081003;'
)
app.secret_key = '08102003'  # Thay 'your_secret_key' bằng một chuỗi bí mật
app.config['SQLALCHEMY_DATABASE_URI'] = 'mssql+pyodbc://sa:081003@TRANVIEN\\SQLEXPRESS/master?driver=SQL+Server'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class ThongTinBenhNhan(db.Model):
    __tablename__ = 'ThongTinBenhNhan'
    
    MaBenhNhan = db.Column(db.String(50), primary_key=True)
    TenBenhNhan = db.Column(db.String(100), nullable=False)
    TuoiBenhNhan = db.Column(db.Integer)
    NgaySinhBN = db.Column(db.Date)
    GioiTinhBN = db.Column(db.String(10))
    DiaChiBN = db.Column(db.String(200))
    SDTBN = db.Column(db.String(15))

class User(db.Model):
    __tablename__ = 'Users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)  # Lưu mật khẩu trực tiếp
    role = db.Column(db.String(50), nullable=False)  # Thêm trường role

class ChanDoanSoBo(db.Model):
    __tablename__ = 'ChuanDoanSoBo'
    MaChuanDoan = db.Column(db.Integer, primary_key=True)
    MaBenhNhan = db.Column(db.String(50))
    NgayChuanDoan = db.Column(db.Date)
    NoiDungChuanDoan = db.Column(db.String)
    


# Đăng ký Người dùng (Thêm bản ghi mới)
def register_user(username, password, role):
    new_user = User(username=username, password=password, role=role)  # Lưu mật khẩu trực tiếp
    db.session.add(new_user)
    db.session.commit()

# Đăng nhập Người dùng (Kiểm tra Tên Đăng nhập và Mật khẩu)
def login_user(username, password):
    user = User.query.filter_by(username=username).first()
    if user and user.password == password:  # So sánh mật khẩu không mã hóa
        return True
    return False



# Đường dẫn lưu trữ tạm thời cho file tải lên
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'txt', 'docx'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Hàm kết nối tới SQL Server
def connect_db():
    try:
        conn = pyodbc.connect(conn_str)
        print("Kết nối thành công!")
        return conn
    except Exception as e:
        print(f"Lỗi kết nối: {e}")

# Kiểm tra và tự động thêm thẻ <a> nếu phản hồi chứa liên kết
def process_response(response_message):
    url_pattern = re.compile(r'(https?://[^\s]+)')
    response_message = re.sub(url_pattern, lambda match: f'<a href="{match.group(0)}" target="_blank">Click vào đây để tải về</a>', response_message)
    response_message = re.sub(r'```python[\s\S]*?```', '', response_message)
    response_message = re.sub(r'[\(\)]', '', response_message)
    return response_message

# Hàm kiểm tra file hợp lệ
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Đọc nội dung file văn bản tải lên
def read_uploaded_file(filepath):
    try:
        if filepath.endswith('.txt'):
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()
        elif filepath.endswith('.docx'):
            doc = docx.Document(filepath)
            content = '\n'.join([para.text for para in doc.paragraphs])
        return content
    except Exception as e:
        return f"Error reading file: {e}"

# Hàm lấy lịch sử hội thoại từ SQL Server
def get_chat_history():
    chat_history = []
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute("SELECT UserMessage, BotResponse FROM ChatHistory ORDER BY ID ASC")
        rows = cursor.fetchall()
        for row in rows:
            chat_history.append(f"User: {row[0]}")
            chat_history.append(f"GPTx: {row[1]}") # Edit your bot's name here
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error fetching chat history: {e}")
    return chat_history

# Trang hiển thị biểu mẫu
@app.route('/GPT')
def bieumau():
    return render_template('chatbot.html')

# Trang chính
@app.route('/')
def home():
    chat_history = get_chat_history()
    return render_template('dangnhap.html', chat_history=chat_history)

@app.route('/chuandoansobo', methods=['GET'])
def chuandoansobo():
    return render_template('chuandoansobo.html')  # Tên file HTML chứa form

# Xử lý tải file
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        content = read_uploaded_file(filepath)
        response_message = f"Bot đã nhận được nội dung file: {content[:200]}..."  # Trả về 200 ký tự đầu tiên
        return jsonify({'response': response_message})

    return jsonify({'error': 'Invalid file format'}), 400

# Xử lý chat
@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({'error': 'No message provided.'}), 400

    # Lấy lịch sử chat và truyền vào ngữ cảnh
    conversation = "\n".join(get_chat_history()) + f"\nUser: {user_message}"

# Phần truyền dữ liệu bệnh nhân vào ngữ cảnh chatbot
    patients = ThongTinBenhNhan.query.all()
    patient_data = "\n".join([
        f"MaBenhNhan: {patient.MaBenhNhan}, TenBenhNhan: {patient.TenBenhNhan}, "
        f"Tuoi: {patient.TuoiBenhNhan}, NgaySinh: {patient.NgaySinhBN}, "
        f"GioiTinh: {patient.GioiTinhBN}, DiaChi: {patient.DiaChiBN}, SDT: {patient.SDTBN}"
        for patient in patients
    ])
    conversation += f"\nThông tin bệnh nhân:\n{patient_data}"

    # Gọi Node.js xử lý tin nhắn với ngữ cảnh cập nhật
    result = subprocess.run(
        ['C:/Program Files/nodejs/node.exe', 'C:/Users/vienm/OneDrive/Desktop/Test/chatbot.js', conversation],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )

    response_message = result.stdout.strip() if result.stdout else "No response from chatbot."

    # Xử lý phản hồi từ bot
    response_message = process_response(response_message)

    # Lưu tin nhắn và phản hồi vào SQL Server
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ChatHistory (UserMessage, BotResponse) VALUES (?, ?)",
            user_message, response_message
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return jsonify({'response': response_message})


@app.route('/api/patients', methods=['GET'])
def get_patient_data():
    # Lấy dữ liệu từ bảng ThongTinBenhNhan
    patients = ThongTinBenhNhan.query.all()
    
    # Chuyển đổi dữ liệu thành danh sách từ điển để dễ dàng chuyển thành JSON
    result = [
        {
            "MaBenhNhan": patient.MaBenhNhan,
            "TenBenhNhan": patient.TenBenhNhan,
            "TuoiBenhNhan": patient.TuoiBenhNhan,
            "NgaySinhBN": patient.NgaySinhBN.strftime('%Y-%m-%d') if patient.NgaySinhBN else None,
            "GioiTinhBN": patient.GioiTinhBN,
            "DiaChiBN": patient.DiaChiBN,
            "SDTBN": patient.SDTBN
        }
        for patient in patients
    ]
    
    return jsonify(result)

@app.route('/patients')
def get_patients():
    patients = ThongTinBenhNhan.query.all()
    result = [
        {
            "MaBenhNhan": patient.MaBenhNhan,
            "TenBenhNhan": patient.TenBenhNhan,
            "TuoiBenhNhan": patient.TuoiBenhNhan,
            "NgaySinhBN": patient.NgaySinhBN.strftime('%Y-%m-%d') if patient.NgaySinhBN else None,
            "GioiTinhBN": patient.GioiTinhBN,
            "DiaChiBN": patient.DiaChiBN,
            "SDTBN": patient.SDTBN
        }
        for patient in patients
    ]
    return jsonify(result)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']  # Lấy vai trò từ form
        
        # Kiểm tra nếu username đã tồn tại
        if User.query.filter_by(username=username).first():
            flash('Username đã tồn tại!')
            return redirect(url_for('register'))
        
        # Nếu không có lỗi, tạo người dùng mới
        register_user(username, password, role)  # Thêm role vào đây
        flash('Đăng ký thành công!')
        return redirect(url_for('login'))
    
    return render_template('dangki.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and user.password == password:
            flash('Đăng nhập thành công!')
            if user.role == 'nhanvienyte':
                return redirect(url_for('nhanvienyte_home'))
            elif user.role == 'bacsi':
                return redirect(url_for('bacsi_home'))
        else:
            flash('Tên đăng nhập hoặc mật khẩu không đúng.')
            return redirect(url_for('login'))
    
    return render_template('dangnhap.html')

@app.route('/nhanvienyte_home')
def nhanvienyte_home():
    # Trang dành cho nhân viên y tế
    return render_template('mainnv.html')

@app.route('/bacsi_home')
def bacsi_home():
    # Trang dành cho bác sĩ
    return render_template('mainbs.html')

@app.route('/patients/view')
def view_patients():
    patients = ThongTinBenhNhan.query.all()
    return render_template('mainnv.html', patients=patients)


@app.route('/submit_ChanDoan', methods=['POST'])
def submit_ChanDoan():
    maChuanDoan = request.form.get('ma_chuandoan')
    maBenhNhan = request.form.get('ma_benhnhan')
    ngayChuanDoan = request.form.get('ngay_chuandoan')
    noiDungChuanDoan = request.form.get('noidung_chuandoan')


    if not maChuanDoan or not maBenhNhan or not ngayChuanDoan or not noiDungChuanDoan:
        flash('Vui lòng điền đầy đủ thông tin.')
        return redirect(url_for('chuandoansobo'))

    # Lưu thông tin vào cơ sở dữ liệu với SQLAlchemy
    try:
        new_diagnosis = ChanDoanSoBo(
            MaChuanDoan=maChuanDoan,
            MaBenhNhan=maBenhNhan,
            NgayChuanDoan=ngayChuanDoan,
            NoiDungChuanDoan=noiDungChuanDoan
        )
        db.session.add(new_diagnosis)
        db.session.commit()
        flash('Chuẩn đoán sơ bộ đã được lưu thành công!')
    except Exception as e:
        db.session.rollback()  # Rollback khi gặp lỗi
        flash(f'Lỗi khi lưu dữ liệu: {str(e)}')

    return redirect(url_for('nhanvienyte_home'))  # Hoặc điều hướng đến trang khác


# Xử lý lưu biểu mẫu vào cơ sở dữ liệu
@app.route('/submit', methods=['POST'])
def submit_contact():
    name = request.form['name']
    email = request.form['email']
    message = request.form['message']
  
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ContactMessages (Name, Email, Message) VALUES (?, ?, ?)",
            name, email, message
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return str(e), 500

    # Thêm vào ngữ cảnh chatbot và gọi Node.js xử lý
    chat_context = f"Name: {name}\nEmail: {email}\nMessage: {message}\n"
    conversation = "\n".join(get_chat_history()) + f"\nForm Submission:\n{chat_context}"

    result = subprocess.run(
        ['C:/Program Files/nodejs/node.exe', 'C:/Users/vienm/OneDrive/Desktop/Test/chatbot.js', conversation],
        capture_output=True,
        text=True,
        encoding='utf-8'
    )

    response_message = result.stdout.strip() if result.stdout else "No response from chatbot."

    # Xử lý phản hồi từ bot
    response_message = process_response(response_message)

    # Lưu lại trong lịch sử hội thoại
    try:
        conn = connect_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ChatHistory (UserMessage, BotResponse) VALUES (?, ?)",
            f"Form Submitted: {chat_context}", response_message
        )
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    return redirect(url_for('bieumau'))

if __name__ == '__main__':
    app.run(debug=True)
