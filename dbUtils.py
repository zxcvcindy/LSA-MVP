import mysql.connector
from flask import current_app, g

def connect_db(): #建立到 MySQL 數據庫的連接
    if 'db' not in g:
        try:
            g.db = mysql.connector.connect(
                host=current_app.config['MYSQL_HOST'],
                user=current_app.config['MYSQL_USER'],
                password=current_app.config['MYSQL_PASSWORD'],
                database=current_app.config['MYSQL_DB'],
                port=current_app.config['MYSQL_PORT']
            )
            g.cursor = g.db.cursor(dictionary=True)
            current_app.logger.debug('Database connection established')
        except mysql.connector.Error as e:
            current_app.logger.error(f"Error connecting to DB: {e}")
            exit(1)
    return g.db, g.cursor

def get_db(): 
    db, cursor = connect_db()
    return db, cursor

def close_db(e=None):
    db = g.pop('db', None)
    cursor = g.pop('cursor', None)
    if cursor is not None:
        cursor.close()
    if db is not None:
        db.close()
def validate_login(name: str, raw_password: str):
    """
    用 users.name + 明文密碼登入。
    找到就回傳使用者 dict（不含 password）；否則 None。
    """
    _, cursor = get_db()
    cursor.execute(
        "SELECT id, name, password, email, create_time "
        "FROM users WHERE name = %s AND password = %s",
        (name, raw_password),
    )
    user = cursor.fetchone()
    if user:
        user.pop("password", None)        # 移除密碼再回傳
        return user
    return None


def get_user(user_id: int):
    """依 id 取得使用者（不含 password）。"""
    _, cursor = get_db()
    cursor.execute(
        "SELECT id, name, email, create_time FROM users WHERE id = %s",
        (user_id,),
    )
    return cursor.fetchone()


def register_user(name: str, raw_password: str, email: str):
    """
    註冊新使用者（明文密碼）：
    1. name 必須唯一
    2. 成功回傳使用者 dict
    """
    db, cursor = get_db()

    # 檢查 name 是否重複
    cursor.execute("SELECT 1 FROM users WHERE name = %s", (name,))
    if cursor.fetchone():
        raise ValueError("Name already taken")

    cursor.execute(
        """
        INSERT INTO users (name, password, email)
        VALUES (%s, %s, %s)
        """,
        (name, raw_password, email),
    )
    db.commit()
    new_user_id = cursor.lastrowid
    return get_user(new_user_id)


# ---------- VM 相關（參考） ---------- #
def create_vm(user_id: int):
    db, cursor = get_db()

    # 查出使用者名稱
    cursor.execute("SELECT name FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise ValueError("找不到使用者")

    base_name = user["name"]

    # 查出已有的同名 VM 數量
    cursor.execute(
        "SELECT COUNT(*) AS count FROM vms WHERE user_id = %s AND name LIKE %s",
        (user_id, f"{base_name}-%",)
    )
    count = cursor.fetchone()["count"]

    # 建立新 VM 名稱（例如：小明-1、小明-2）
    vm_name = f"{base_name}-{count + 1}"

    # 插入資料
    cursor.execute(
        "INSERT INTO vms (user_id, name) VALUES (%s, %s)",
        (user_id, vm_name),
    )
    db.commit()
    vmid = cursor.lastrowid

    return {
        "vmid": vmid,
        "vm_name": vm_name
    }


def list_allvms(user_id: int) -> list[dict]:
    """
    從 DB 取出 user_id 擁有的所有 VM。
    回傳格式範例：
        [
            {"id": 120, "name": "alice-120"},
            {"id": 131, "name": "alice-131"},
            ...
        ]
    """
    db, cursor = get_db()
    cursor.execute(
        "SELECT id, name FROM vms WHERE user_id = %s ORDER BY id",
        (user_id,),
    )
    rows = cursor.fetchall()        # rows already list[dict] (because cursor=dict=True)
    return rows

def delete_vm(user_id: int, vmid: int):
    """
    刪除指定 VM 的資料庫紀錄。
    1. 先從 Proxmox 刪除 VM
    2. 再從本地 DB 刪除紀錄
    """
    db, cursor = get_db()

    # Step 1: 刪除 Proxmox 上的 VM
    try:
        from proxmox_api import delete_vm as proxmox_delete_vm
        upid = proxmox_delete_vm(node="pve", vmid=vmid)
    except Exception as e:
        current_app.logger.error("Failed to delete VM %s: %s", vmid, e)
        return {"ok": False, "error": str(e)}, 500

    # Step 2: 等待 Proxmox 任務完成
    try:
        from proxmox_api import wait_task_ok
        wait_task_ok(node="pve", upid=upid, timeout=120)
    except Exception as e:
        current_app.logger.error("Failed to wait for task %s: %s", upid, e)
        return {"ok": False, "error": str(e)}, 500

    # Step 3: 刪除本地 DB 紀錄
    try:
        cursor.execute("DELETE FROM vms WHERE id = %s", (vmid))
        db.commit()
        return {"ok": True}, 200
    except Exception as e:
        db.rollback()
        current_app.logger.error("Failed to delete VM %s from DB: %s", vmid, e)
        return {"ok": False, "error": str(e)}, 500
    
