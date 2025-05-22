import logging
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from functools import wraps
import os, proxmox_api
from dbUtils import get_db, close_db, validate_login, get_user, register_user
from flask_jwt_extended import create_access_token
from flask_jwt_extended import get_jwt_identity
from flask_jwt_extended import jwt_required
from flask_jwt_extended import JWTManager

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 設置數據庫配置
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'mvp'
app.config['MYSQL_PORT'] = 8889
app.config["JWT_SECRET_KEY"] = "secret"
app.secret_key = "replace-with-strong-secret"
app.config["JWT_SECRET_KEY"] = "replace-with-jwt-secret"
jwt = JWTManager(app) 
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
    app.logger.debug('Register form submitted')
    body = request.get_json()
    username = body['username'] # 從提交的表單中獲取用戶名和密碼
    password = body['password'] 
    name = body['name'] 
    email = body['email'] 
    user = register_user(username, password, name, email) # db裡，處理用戶註冊
    flash('Registration successful!', 'success')
    return user

@app.route('/login', methods=['GET', 'POST'])
def login():
    app.logger.debug('Login route called')
    app.logger.debug('Login form submitted')
    body = request.get_json()
    password = body['password']
    username = body['username'] 
    user = validate_login(username, password) # db裡，驗證用戶名和密碼
    if user:
        access_token = create_access_token(identity=str(user['id']))  # ✅ 傳 string
        return jsonify(access_token=access_token)
        

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

#proxmox_api

@app.route('/nodes', methods=['GET'])
def list_nodes():
    return jsonify(proxmox_api.get_nodes())

@app.route('/vm/<node>/<int:vmid>/start', methods=['POST'])
def start_vm(node, vmid):
    return jsonify(proxmox_api.start_vm(node, vmid))

@app.route('/vm/<node>/<int:vmid>/stop', methods=['POST'])
def stop_vm(node, vmid):
    return jsonify(proxmox_api.stop_vm(node, vmid))

@app.route('/user-vm/create', methods=['POST'])
@jwt_required()
def create_user_vm_api():
    user_id = get_jwt_identity()  # 這裡會拿到登入者的 ID
    
    data = request.get_json()
    new_vmid = data["vmid"]
    vm_name = f"vm-{user_id}"
    password = data.get("password", "1234")

    result = proxmox_api.create_user_vm(
        node="pve",
        template_vmid=110,
        new_vmid=new_vmid,
        vm_name=vm_name,
        username=user_id,
        password=password
    )
    return jsonify(result)


@app.route('/vm/<node>/<int:vmid>', methods=['DELETE'])
def delete_vm(node, vmid):
    return jsonify(proxmox_api.delete_vm(node, vmid))

@app.route('/vm/<node>/<int:vmid>/restart', methods=['POST'])
def restart_vm(node, vmid):
    return jsonify(proxmox_api.restart_vm(node, vmid))


@app.route('/vm/<node>/<int:vmid>/status', methods=['GET'])
def get_vm_status(node, vmid):
    return jsonify(proxmox_api.get_vm_status(node, vmid))


if __name__ == '__main__':
    app.run(debug=True, port=5002)