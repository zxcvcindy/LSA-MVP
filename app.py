import logging
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from functools import wraps
import os, proxmox_api
from dbUtils import get_db, close_db, validate_login, get_user, register_user

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 設置數據庫配置
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'mvp'
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
    if user: # user['id'] 的值存儲在 session 對象中，名為 'user_id'。 之後就可以通過 session['user_id'] 來獲取當前登入用戶的 ID。
        session['user_id'] = user['id']
        flash('Login successful!', 'success')
        return  user

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

@app.route('/vm/<node>/create', methods=['POST'])
def create_vm(node):
    data = request.get_json()
    vmid = data.get("vmid")
    name = data.get("name")
    cores = data.get("cores", 1)
    memory = data.get("memory", 512)
    storage = data.get("storage", "local-lvm")
    iso = data.get("iso")  # 範例：local:iso/debian-12.iso

    if not all([vmid, name, iso]):
        return jsonify({"error": "vmid, name, and iso are required."}), 400

    return jsonify(proxmox_api.create_vm(node, vmid, name, cores, memory, storage, iso))

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