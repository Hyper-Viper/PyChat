# Updated server.py to add client login system with password and online status check

import socket
import threading
import mysql.connector

# ========== MySQL SETUP ==========
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password@123",  # Replace with your MySQL root password
)
cursor = db.cursor()

cursor.execute("CREATE DATABASE IF NOT EXISTS pychat")
cursor.execute("USE pychat")

# Create tables if they don't exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS chats (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    chat_name VARCHAR(255),
    sender VARCHAR(255),
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    online BOOLEAN DEFAULT FALSE
)
""")

cursor.execute("UPDATE users SET online=FALSE")

db.commit()

# ========== SERVER CONFIG ==========
HOST = '::'
PORT = 1060

clients = {}     # {client_socket: (username, chat_name)}
chats = {}       # {chat_name: [client_sockets]}


# ========== UTILITIES ==========
def ensure_chat_exists(chat_name):
    cursor.execute("SELECT id FROM chats WHERE name = %s", (chat_name,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO chats (name) VALUES (%s)", (chat_name,))
        db.commit()


def load_chat_history(chat_name):
    cursor.execute("""
    SELECT sender, content FROM messages
    WHERE chat_name = %s
    ORDER BY timestamp ASC
    """, (chat_name,))
    return cursor.fetchall()


def save_message(chat_name, sender, content):
    cursor.execute("""
    INSERT INTO messages (chat_name, sender, content)
    VALUES (%s, %s, %s)
    """, (chat_name, sender, content))
    db.commit()


def broadcast(message, chat_name, sender_socket):
    if chat_name in chats:
        for client in chats[chat_name]:
            try:
                client.send((message + "\n").encode())
            except:
                client.close()
                if client in chats[chat_name]:
                    chats[chat_name].remove(client)


def handle_client(client_socket):
    try:
        auth = client_socket.recv(1024).decode()
        if not auth.startswith("/auth|"):
            client_socket.send("ERROR: Invalid authentication format.\n".encode())
            client_socket.close()
            return

        _, username, password = auth.split("|")

        # Check if user exists
        cursor.execute("SELECT password, online FROM users WHERE username = %s", (username,))
        row = cursor.fetchone()
        if row:
            stored_password, online = row
            if online:
                client_socket.send("ERROR: User is online already.\n".encode())
                client_socket.close()
                return
            if stored_password != password:
                client_socket.send("ERROR: Invalid password.\n".encode())
                client_socket.close()
                return
            cursor.execute("UPDATE users SET online = TRUE WHERE username = %s", (username,))
        else:
            cursor.execute("INSERT INTO users (username, password, online) VALUES (%s, %s, TRUE)",
                           (username, password))

        db.commit()
        client_socket.send("LOGIN_SUCCESS\n".encode())

        while True:
            data = client_socket.recv(1024).decode()
            if not data:
                break

            if data.startswith("/join"):
                _, username, chat = data.split("|")
                ensure_chat_exists(chat)
                clients[client_socket] = (username, chat)
                if client_socket not in chats.setdefault(chat, []):
                    chats[chat].append(client_socket)
                print(f"[+] {username} joined chat '{chat}'")

                # Send chat history
                history = load_chat_history(chat)
                for sender, msg in history:
                    formatted = f"{sender}: {msg}\n"
                    client_socket.send(formatted.encode())
                continue

            username, chat, msg = data.split("|", 2)
            save_message(chat, username, msg)
            full_msg = f"{username}: {msg}"
            broadcast(full_msg, chat, client_socket)
    except ConnectionResetError:
        print(f"[!] {username} disconnected abruptly.")
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        if client_socket in clients:
            _, chat = clients[client_socket]
            print(f"[-] {username} left chat '{chat}'")
            if chat in chats and client_socket in chats[chat]:
                chats[chat].remove(client_socket)
            del clients[client_socket]

        # ✅ Mark user offline even if they crash
        if username:
            try:
                cursor.execute("UPDATE users SET online = FALSE WHERE username = %s", (username,))
                db.commit()
            except Exception as e:
                print(f"[!] Failed to update online status: {e}")

        client_socket.close()


# ========== MAIN SERVER ==========
server = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
server.bind((HOST, PORT, 0, 0))
server.listen()

print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")

while True:
    client_socket, addr = server.accept()
    print(f"[NEW CONNECTION] {addr}")
    thread = threading.Thread(target=handle_client, args=(client_socket,))
    thread.start()
