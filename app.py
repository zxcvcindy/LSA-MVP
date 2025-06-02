import logging
import os

from flask import Flask, request, jsonify, flash, render_template, redirect
import proxmox_api
from dbUtils import *
from dbUtils import delete_vm as db_delete_vm
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required,
)
from flask_cors import CORS

# 正式環境請改成你的前端網域

app = Flask(__name__)
CORS(app, origins=["*"], supports_credentials=True)
# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "replace-with-strong-secret")
app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "replace-with-jwt-secret"
)

# MySQL settings
app.config["MYSQL_HOST"] = os.environ.get("MYSQL_HOST", "localhost")
app.config["MYSQL_USER"] = os.environ.get("MYSQL_USER", "root")
app.config["MYSQL_PASSWORD"] = os.environ.get("MYSQL_PASSWORD", "root")
app.config["MYSQL_DB"] = os.environ.get("MYSQL_DB", "mvp")
app.config["MYSQL_PORT"] = int(os.environ.get("MYSQL_PORT", 3306))

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


@app.route("/login", methods=["GET"])
def login_page():
    return render_template("login.html")


@app.route("/register", methods=["POST"])
def register():
    app.logger.debug("Register route called")
    body = request.get_json() or {}

    username = body.get("username")
    password = body.get("password")
    email = f"s{username}@ncnu.edu.tw"

    if not all([username, password, email]):
        return jsonify(msg="Missing fields"), 400

    user = register_user(username, password, email)
    flash(
        "Registration successful!", "success"
    )  # flash 仍可用，但不再依賴 auth session
    return jsonify(user), 201


@app.route("/login", methods=["POST"])
def login():
    app.logger.debug("Login route called")
    body = request.get_json() or {}

    username = body.get("username")
    password = body.get("password")

    if not username or not password:
        return jsonify(msg="Missing username or password"), 400

    user = validate_login(username, password)
    if not user:
        return jsonify(msg="Invalid credentials"), 401

    access_token = create_access_token(identity=str(user["id"]))
    return jsonify(access_token=access_token)


@app.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """JWT 無伺服器狀態，前端自行丟棄 token 即登出。此端點可作為
    revocation list 或 audit log 之用。"""
    return jsonify(
        msg="Logout successful. Please discard the token on the client side."
    )


# ---------------------------------------------------------------------------
# Proxmox API proxies (some already protected by JWT)
# ---------------------------------------------------------------------------


# @app.route('/myvm/start', methods=['POST'])
# @jwt_required()
# def start_vm():
#     user_id = get_jwt_identity()
#     return jsonify(proxmox_api.start_vm("pve", user_id))
# 啟動 VM --------------------------------------------------------
@app.route("/vm/<node>/<int:vmid>/start", methods=["POST", "OPTIONS"])
@jwt_required()
def start_vm(node, vmid):
    """POST /vm/pve/122/start  →  啟動 VM 122"""
    return jsonify(proxmox_api.start_vm(node, vmid))


@app.route("/vm/<node>/<int:vmid>/stop", methods=["POST"])
@jwt_required()
def stop_vm(node, vmid):
    return jsonify(proxmox_api.stop_vm(node, vmid))


@app.route("/user-vm", methods=["GET"])
@jwt_required()
def list_user_vm_api():
    """回傳目前登入者的 VM 清單（含狀態與 IP）"""
    user_id = get_jwt_identity()  # 取得 JWT 內的帳號資訊

    try:
        # 向 Proxmox 取資料（請依你的實際狀況更名）
        vms = proxmox_api.list_user_vms(node="pve", username=user_id)

        # 只傳前端需要的欄位，避免漏出敏感資訊
        result = [
            {
                "vmid": vm["vmid"],
                "name": vm["name"],
                "status": vm.get("status", "unknown"),
                "ip": vm.get("ip"),  # 若無則前端顯示「-」
            }
            for vm in vms
        ]

        return jsonify(result), 200

    except Exception as e:
        # 可視需求 Log 詳細錯誤
        return jsonify({"msg": f"取得 VM 清單失敗: {e}"}), 500


@app.route("/user-vm/create", methods=["POST"])
@jwt_required()
def create_user_vm_api():
    user_id = get_jwt_identity()  # 目前登入者的帳號
    vmid = create_vm(user_id)  # 建立 VM 時的 VM ID
    data = request.get_json()

    new_vmid = vmid["vmid"]  # 取得新 VM 的 ID
    vm_name = f"vm-{vmid['vm_name']}"  # 取得 VM 名稱
    password = data.get("password", "1234")

    # 1. 建 VM
    result = proxmox_api.create_user_vm(
        node="pve",
        template_vmid=100,
        new_vmid=new_vmid,
        vm_name=vm_name,
        username=f"s{user_id}",
        password=password,
    )

    # 2. 若成功，再取 IPv6 / SSH 並一起回傳
    if result.get("ok"):
        netinfo = proxmox_api.build_ssh6_cmd("pve", new_vmid, vm_name)
        return jsonify({**result, **netinfo}), 201

    # 3. 失敗照原格式回傳
    return jsonify(result), 500


@app.route("/vm/<node>/<int:vmid>/ssh6", methods=["GET"])
@jwt_required()
def get_vm_ssh6(node, vmid):
    username = get_jwt_identity()
    return jsonify(proxmox_api.build_ssh6_cmd(node, vmid, username))


# @app.route('/vm/<node>/<int:vmid>', methods=['DELETE','OPTIONS'])
# @jwt_required()
# def delete_vm(node, vmid):
#     return jsonify(proxmox_api.delete_vm(node, vmid))
# 刪除 VM ── 用 POST 方法


@app.route("/vm/<node>/<int:vmid>/delete", methods=["POST", "OPTIONS"])
@jwt_required()
def delete_vm(node, vmid):
    if request.method == "OPTIONS":
        return "", 204

    user_id = get_jwt_identity()
    db, _ = get_db()

    result = proxmox_api.delete_vm(node, vmid)

    if result.get("ok"):
        db_delete_vm(user_id, id)  # <-- 這裡改掉
        db.commit()
        return jsonify({"ok": True}), 200

    db.rollback()
    current_app.logger.error("DELETE VM %s failed: %s", id, result.get("error"))
    return jsonify({"ok": False, "error": result.get("error", "Unknown")}), 500

@app.route("/vm/<node>/<int:vmid>/restart", methods=["POST"])
@jwt_required()
def restart_vm(node, vmid):
    return jsonify(proxmox_api.restart_vm(node, vmid))


@app.route("/vm/<node>/<int:vmid>/status", methods=["GET"])
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
    user_id = get_jwt_identity()

    # 1) 先從本地 DB 撈出所有 vmid
    local_vms = list_allvms(user_id)  # ⇢ list[dict]

    if not local_vms:
        return jsonify([])  # 使用者沒有任何 VM

    vm_infos = []  # 最後要回前端的陣列

    # 2) 逐台去 Proxmox 拿即時 status / ip / mem …
    for vm in local_vms:
        vmid = int(vm["id"])
        try:
            info = proxmox_api.get_vm_info(node="pve", vmid=vmid)
            if not info or not isinstance(info, dict):
                continue  # 取不到就跳過

            # 你可以把 DB 的名稱覆蓋掉 PVE 回來的 name
            info["name"] = vm["name"]
            vm_infos.append(info)

        except Exception as exc:
            current_app.logger.error("get_vm_info(%s) failed: %s", vmid, exc)
            # 照需求可把錯誤記下來或加到 vm_infos

    return jsonify(vm_infos)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, port=5002)
