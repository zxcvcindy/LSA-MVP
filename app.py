import logging
import os

from flask import Flask, request, jsonify, flash
import proxmox_api
from dbUtils import close_db, validate_login, register_user
from flask_jwt_extended import (
    JWTManager, create_access_token,
    get_jwt_identity, jwt_required
)
from flask_cors import CORS
  # 正式環境請改成你的前端網域

app = Flask(__name__)
CORS(app, origins=['*'])s
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "replace-with-strong-secret")
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "replace-with-jwt-secret")

# MySQL settings
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'mvp'
app.config['MYSQL_PORT'] = 8889

jwt = JWTManager(app)

# Logging
logging.basicConfig(level=logging.DEBUG)


# ---------------------------------------------------------------------------
# App‑context teardown
# ---------------------------------------------------------------------------
@app.teardown_appcontext
def teardown_db(exception):
    close_db()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
@app.route('/register', methods=['POST'])
def register():
    app.logger.debug('Register route called')
    body = request.get_json() or {}

    username = body.get('username')
    password = body.get('password')
    name     = body.get('name')
    email    = body.get('email')

    if not all([username, password, name, email]):
        return jsonify(msg="Missing fields"), 400

    user = register_user(username, password, name, email)
    flash('Registration successful!', 'success')  # flash 仍可用，但不再依賴 auth session
    return jsonify(user), 201


@app.route('/login', methods=['POST'])
def login():
    app.logger.debug('Login route called')
    body = request.get_json() or {}

    username = body.get('username')
    password = body.get('password')

    if not username or not password:
        return jsonify(msg="Missing username or password"), 400

    user = validate_login(username, password)
    if not user:
        return jsonify(msg="Invalid credentials"), 401

    access_token = create_access_token(identity=str(user['id']))
    return jsonify(access_token=access_token)


@app.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """JWT 無伺服器狀態，前端自行丟棄 token 即登出。此端點可作為
    revocation list 或 audit log 之用。"""
    return jsonify(msg='Logout successful. Please discard the token on the client side.')


# ---------------------------------------------------------------------------
# Proxmox API proxies (some already protected by JWT)
# ---------------------------------------------------------------------------
@app.route('/nodes', methods=['GET'])
@jwt_required()
def list_nodes():
    return jsonify(proxmox_api.get_nodes())


@app.route('/vm/<node>/<int:vmid>/start', methods=['POST'])
@jwt_required()
def start_vm(node, vmid):
    return jsonify(proxmox_api.start_vm(node, vmid))


@app.route('/vm/<node>/<int:vmid>/stop', methods=['POST'])
@jwt_required()
def stop_vm(node, vmid):
    return jsonify(proxmox_api.stop_vm(node, vmid))


@app.route('/user-vm/create', methods=['POST'])
@jwt_required()
def create_user_vm_api():
    user_id = get_jwt_identity()         # 目前登入者的帳號
    data = request.get_json()

    new_vmid  = data["vmid"]
    vm_name   = f"vm-{user_id}"
    password  = data.get("password","1234")

    # 1. 建 VM
    result = proxmox_api.create_user_vm(
        node="pve",
        template_vmid=100,
        new_vmid=new_vmid,
        vm_name=vm_name,
        username=user_id,
        password=password
    )

    # 2. 若成功，再取 IPv6 / SSH 並一起回傳
    if result.get("ok"):
        netinfo = proxmox_api.build_ssh6_cmd("pve", new_vmid, user_id)
        return jsonify({**result, **netinfo}), 201

    # 3. 失敗照原格式回傳
    return jsonify(result), 500

@app.route('/vm/<node>/<int:vmid>/ssh6', methods=['GET'])
@jwt_required()
def get_vm_ssh6(node, vmid):
    username = get_jwt_identity()
    return jsonify(proxmox_api.build_ssh6_cmd(node, vmid, username))

@app.route('/vm/<node>/<int:vmid>', methods=['DELETE'])
@jwt_required()
def delete_vm(node, vmid):
    return jsonify(proxmox_api.delete_vm(node, vmid))


@app.route('/vm/<node>/<int:vmid>/restart', methods=['POST'])
@jwt_required()
def restart_vm(node, vmid):
    return jsonify(proxmox_api.restart_vm(node, vmid))


@app.route('/vm/<node>/<int:vmid>/status', methods=['GET'])
@jwt_required()
def get_vm_status(node, vmid):
    return jsonify(proxmox_api.get_vm_status(node, vmid))

@app.route("/nodes", methods=["GET"])
@jwt_required()
def list_nodes():
    return jsonify(proxmox_api.get_nodes())


@app.route("/vms/<node>", methods=["GET"])
@jwt_required()
def list_vms(node):
    """Return every VM under the node with name / status / ip"""
    return jsonify(proxmox_api.list_vms(node))


@app.route("/vm/<node>/<int:vmid>/info", methods=["GET"])
@jwt_required()
def get_vm_info(node, vmid):
    """Return name, power state, and IPv6 for a single VM"""
    return jsonify(proxmox_api.get_vm_info(node, vmid))

@app.route("/myvms", methods=["GET"])
@jwt_required()
def list_my_vms():
    """依登入者 ID（JWT identity）回傳自己擁有的 VM 清單"""
    user_id = get_jwt_identity()          # e.g. "student101"
    vms = proxmox_api.list_vms_by_owner(node="pve", owner=user_id)
    return jsonify(vms)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    app.run(debug=True, port=5002)
