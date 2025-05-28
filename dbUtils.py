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

def validate_login(username, password):
    db, cursor = get_db()
    cursor.execute("SELECT * FROM users WHERE id = %s AND password = %s", (username, password))
    user = cursor.fetchone()
    if user:
        return get_user(username)
    return None


def get_user(user_id): #根據用戶 ID 獲取用戶信息
    db, cursor = get_db()
    cursor.execute("SELECT id, name, email FROM users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    return user

def register_user(username, password, email): #註冊新用戶
    db, cursor = get_db()
    cursor.execute("INSERT INTO users (id, password, email) VALUES (%s, %s, %s)", (username, password, email))
    db.commit()
    return get_user(username)