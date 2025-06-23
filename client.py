import socket
import threading
import tkinter as tk
from tkinter import simpledialog, scrolledtext, messagebox

HOST = '127.0.0.1'
PORT = 12345

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

# Prompt for credentials
name = simpledialog.askstring("Login", "Enter your username:").strip()
if not name:
    messagebox.showerror("Error", "Username cannot be empty.")
    exit()
if not name.isalnum():
    messagebox.showerror("Error", "Username can only have alphanumeric value.")
    exit()

password = simpledialog.askstring("Login", "Enter your password:", show="*")
if password is None:
    messagebox.showerror("Error", "Password cannot be empty.")
    exit()

# Authenticate
client.send(f"/auth|{name}|{password}".encode())
response = client.recv(1024).decode()

if not response.startswith("LOGIN_SUCCESS"):
    messagebox.showerror("Login Failed", response)
    client.close()
    exit()

current_chat = None

# GUI setup
window = tk.Tk()
window.title("pyChat")

# Chat list
chat_frame_left = tk.Frame(window)
chat_frame_left.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)

tk.Label(chat_frame_left, text="Chats").pack()
chat_listbox = tk.Listbox(chat_frame_left)
chat_listbox.pack(fill=tk.BOTH, expand=True)

# Chat area
chat_frame_right = tk.Frame(window)
chat_frame_right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

messages = scrolledtext.ScrolledText(chat_frame_right)
messages.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
messages.config(state='disabled')

msg_entry = tk.Entry(chat_frame_right)
msg_entry.pack(padx=10, pady=(0, 10), fill=tk.X)

# Send message
def send_msg(event=None):
    global current_chat
    msg = msg_entry.get().strip()
    if msg and current_chat:
        full_msg = f"{name}|{current_chat}|{msg}"
        client.send(full_msg.encode())
        msg_entry.delete(0, tk.END)

# Chat select
def join_selected_chat(event):
    global current_chat
    selection = chat_listbox.curselection()
    if not selection:
        return
    selected = chat_listbox.get(selection[0])
    current_chat = selected
    messages.config(state='normal')
    messages.delete('1.0', tk.END)
    messages.insert(tk.END, f"Joined chat: {selected}\n")
    messages.config(state='disabled')
    join_msg = f"/join|{name}|{selected}"
    client.send(join_msg.encode())
    window.title(f"Chat: {selected}")

# Receive messages
def receive():
    while True:
        try:
            data = client.recv(1024).decode()
            if not data:
                break
            lines = data.splitlines()
            messages.config(state='normal')
            for line in lines:
                if line.startswith(name):
                    display = "You" + line.replace(name, "", 1)
                else:
                    display = line
                messages.insert(tk.END, display + "\n")
            messages.config(state='disabled')
            messages.yview(tk.END)
        except:
            break

# Static list of chats (could be dynamic later)
default_chats = ["General", "Gaming", "Study", "Music", "Projects"]
for chat in default_chats:
    chat_listbox.insert(tk.END, chat)

chat_listbox.bind("<<ListboxSelect>>", join_selected_chat)
window.bind("<Return>", send_msg)

# Start receive thread
threading.Thread(target=receive, daemon=True).start()

window.mainloop()
