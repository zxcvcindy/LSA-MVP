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
def create_vm(user_id: int, vm_name: str):
    """建立 VM；vmid 自動從 100 起遞增。"""
    db, cursor = get_db()
    cursor.execute(
        "INSERT INTO vms (user_id, name) VALUES (%s, %s)",
        (user_id, vm_name),
    )
    db.commit()
    vmid = cursor.lastrowid
    cursor.execute(
        "SELECT vmid, user_id, name FROM vms WHERE vmid = %s",
        (vmid,),
    )
    return cursor.fetchone()


def list_vms(user_id: int):
    """列出指定使用者的所有 VM。"""
    _, cursor = get_db()
    cursor.execute(
        "SELECT vmid, name FROM vms WHERE user_id = %s ORDER BY vmid",
        (user_id,),
    )
    return cursor.fetchall()