import logging
from flask import Flask, render_template, redirect, url_for, request, session, flash
from functools import wraps
import os
from dbUtils import get_db, close_db, validate_login, get_user, register_user, get_user_auctions, create_auction, get_auction, update_auction, delete_auction, get_all_auctions, get_auction_bids, place_bid

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 設置數據庫配置
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'auction_db'
app.config['MYSQL_PORT'] = 8889

# 設置日誌
logging.basicConfig(level=logging.DEBUG)

@app.teardown_appcontext
def teardown_db(exception):
    close_db()

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

@app.route('/register', methods=['GET', 'POST'])
def register():
    app.logger.debug('Register route called') #在日誌中記錄(會出現在終端機，讓你檢查的)
    if request.method == 'POST': #若if成立，表單提交
        app.logger.debug('Register form submitted')
        username = request.json['username'] # 從提交的表單中獲取用戶名和密碼
        password = request.json['password'] 
        name = request.json['name'] 
        email = request.json['email'] 
        register_user(username, password) # db裡，處理用戶註冊
        flash('Registration successful!', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    app.logger.debug('Login route called')
    if request.method == 'POST': # 檢查請求方法是否為 POST。如果是，表示用戶提交了登入表單
        app.logger.debug('Login form submitted')
        username = request.form['username']
        password = request.form['password']
        user = validate_login(username, password) # db裡，驗證用戶名和密碼
        if user: # user['id'] 的值存儲在 session 對象中，名為 'user_id'。 之後就可以通過 session['user_id'] 來獲取當前登入用戶的 ID。
            session['user_id'] = user['id']
            flash('Login successful!', 'success')
            return redirect(url_for('index'))  # 重定向到 index 視圖函數
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/') #首頁
@login_required
def index():
    user = get_user(session['user_id']) # db裡
    auctions = get_user_auctions(user['id'])
    return render_template('index.html', auctions=auctions)