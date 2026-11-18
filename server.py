import os
import socket
import threading
import mimetypes
import time
import csv
import json
import hmac
import hashlib

IP = "100.82.117.26"
PORT = 4450
ADDR = (IP,PORT)
SIZE = 1024
FORMAT = "utf-8"
SERVER_PATH = "server"
SERVER_LOG = "serverPerformanceLog.csv"

users = {
    "tam": hashlib.sha256("tampassword".encode()).hexdigest(),
    "alex": hashlib.sha256("alexpassword".encode()).hexdigest()
}

commands = [
    "UPLOAD",
    "DOWNLOAD",
    "DELETE",
    "DIRECTORY",
    "SUBFOLDER CREATE",
    "SUBFOLDER DELETE",
    "DISCONNECT"
]

menu = """
========== COMMAND MENU ==========
1. Upload
2. Download
3. Delete
4. Dir
5. Subfolder Create
6. Subfolder Delete
7. Disconnect
==================================
"""

active_clients = 0
client_lock = threading.Lock()

active_files = set()
active_folders = set()

def logServerMetrics(operation, fileName, sizeBytes, duration):
    fileSizeMB = round(sizeBytes / (1024 * 1024), 4)
    dataRate = round(fileSizeMB / duration, 2) if duration > 0 else 0
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    fileExists = os.path.exists(SERVER_LOG)
    with open(SERVER_LOG, mode="a", newline="") as f:
        writer = csv.writer(f)
        if not fileExists:
            writer.writerow(["Timestamp", "Operation", "FileName", "FileSizeMB", "Duration_s", "DataRateMBs"])
        writer.writerow([timestamp, operation, fileName, fileSizeMB, round(duration, 4), dataRate])

def authenticate(conn):
    global active_clients
    try:
        # recieve authentication request
        data = conn.recv(SIZE).decode(FORMAT).strip()
        parts = data.split("@")

        if len(parts) != 3 or parts[0] != "AUTH":
            raise ValueError("Invalid authentication request.")

        username = parts[1]
        password_hash = parts[2]

        # verify username and password
        stored_hash = users.get(username)

        if stored_hash and hmac.compare_digest(stored_hash, password_hash):
            conn.sendall("[OK] Authentication successful.".encode(FORMAT))
            print(f"[AUTH] {username} authenticated.")
            print(f"[SERVER] Active clients: {active_clients}")
            return True

        raise PermissionError("Invalid username or password.")

    except (OSError, ValueError, PermissionError) as e:
        conn.sendall(f"[ERROR] {e}".encode(FORMAT))
        print(f"[AUTH] Authentication failed")
        active_clients -= 1
        return False

### to handle individual commands
def upload(conn, cmd_parts):
    try:
        tracking = False

        temp_path = None
        filename = cmd_parts[1].strip()
        size = int(cmd_parts[2].strip())

        if not filename:
            raise ValueError("No filename provided.")

        file_path = os.path.realpath(os.path.join(SERVER_PATH, filename))
        server_path = os.path.realpath(SERVER_PATH)

        if os.path.commonpath([server_path, file_path]) != server_path:
            raise ValueError("Invalid file path.")

        if not os.path.isdir(os.path.dirname(file_path)):
            raise FileNotFoundError("Destination folder does not exist.")
        
        temp_path = file_path + ".tmp"

        # check if file is being used elsewhere
        if filename in active_files:
            raise PermissionError("File is currently being processed.")
        active_files.add(filename)
        tracking = True

        # check if the file already exists
        if os.path.exists(file_path):
            conn.sendall("File already exists. Overwrite? (Y/N)".encode(FORMAT))

            while True:
                response = conn.recv(SIZE).decode(FORMAT).strip().upper()

                if response == "Y":
                    break
                elif response == "N":
                    conn.sendall("Upload cancelled.".encode(FORMAT))
                    return
                else:
                    conn.sendall("Invalid response. Enter Y or N.".encode(FORMAT))

        # tells client to start sending files
        conn.sendall("READY".encode(FORMAT))

        print(f"[{threading.current_thread().name.split()[0].upper()}] Receiving file...")

        start_time = time.time()
        with open(temp_path, "wb") as file:
            remaining = size

            while remaining > 0:
                chunk = conn.recv(min(SIZE, remaining))
                file.write(chunk)
                remaining -= len(chunk)

                if not chunk:
                    raise ConnectionError("Client disconnected during upload.")

        duration = time.time() - start_time
        logServerMetrics("UPLOAD", filename, size, duration)  # log metrics

        size_mb = size / (1024 * 1024)
        rate = size_mb / duration if duration > 0 else 0

        print(f"[ANALYSIS] Upload: {size_mb:.2f} MB / {duration:.2f} s")
        print(f"[ANALYSIS] Rate: {rate:.2f} MB/s")

        os.replace(temp_path, file_path)
        conn.sendall("[OK] Upload completed.".encode(FORMAT))
        print(f"[{threading.current_thread().name.split()[0].upper()}] Upload completed.")
        print()
        
    except (OSError, ValueError, IndexError, ConnectionError, PermissionError) as e:
        if tracking and temp_path and os.path.isfile(temp_path):
            os.remove(temp_path)

        print(f"[ERROR] {threading.current_thread().name.split()[0].upper()}: {e}")
        conn.sendall(f"[ERROR] {e}".encode(FORMAT))

    finally:
        if tracking:
            active_files.discard(filename)


def download(conn, cmd_parts):
    try:
        tracking = False

        # verify a filename was sent
        filename = cmd_parts[1].strip()
        start_offset = int(cmd_parts[2].strip()) if len(cmd_parts) > 2 else 0#BLAH

        if not filename:
            raise ValueError("No filename provided.")

        # verify the file exists
        file_path = os.path.join(SERVER_PATH, filename)
        if not os.path.isfile(file_path):
            raise FileNotFoundError("File does not exist.")

        # check if file is being used elsewhere
        if filename in active_files:
            raise PermissionError("File is currently being processed.")
        active_files.add(filename)
        tracking = True

        # get file size and send to client
        total_size = os.path.getsize(file_path)#BLAH

        if start_offset > total_size:#BLAH
            start_offset = total_size#BLAH

        conn.sendall(f"SIZE@{total_size}@{start_offset}".encode(FORMAT))#BLAH

        # wait for "READY" response from client to send file (if not ready, stop)
        response = conn.recv(SIZE).decode(FORMAT).strip().upper()
        print(f"[DEBUG] Download received: {repr(response)}")

        if response != "READY":
            print("[ERROR] Client did not send READY.")
            return

        start_time = time.time()
        # send file
        with open(file_path, "rb") as file:
            file.seek(start_offset)#BLAH
            while True:
                chunk = file.read(SIZE)

                if not chunk:
                    break

                conn.sendall(chunk)

        print(f"[{threading.current_thread().name.split()[0].upper()}] Download completed.")
        duration = time.time() - start_time
        transferred_bytes = total_size - start_offset #BLAH
        logServerMetrics("DOWNLOAD", filename, transferred_bytes, duration)  # log metrics#BLAH

        size_mb = transferred_bytes / (1024 * 1024)#BLAH
        rate = size_mb / duration if duration > 0 else 0

        print(f"[ANALYSIS] Download: {size_mb:.2f} MB / {duration:.2f} s")
        print(f"[ANALYSIS] Rate: {rate:.2f} MB/s")
        print("[ANALYSIS] Statistics saved.")

    except (OSError, IndexError, FileNotFoundError, ValueError, PermissionError) as e:
        conn.sendall(f"[ERROR] {e}".encode(FORMAT))

    finally:
        if tracking:
            active_files.discard(filename)


def delete(conn, cmd_parts):
    try:
        tracking = False

        # verify a filename was sent
        filename = cmd_parts[1].strip()
        if not filename:
            raise ValueError("No filename provided.")

        # verify the file exists
        file_path = os.path.join(SERVER_PATH, filename)
        if not os.path.isfile(file_path):
            raise FileNotFoundError("File does not exist.")

        # check if file is being used elsewhere
        if filename in active_files:
            raise PermissionError("File is currently being processed.")
        active_files.add(filename)
        tracking = True

        # delete the file
        os.remove(file_path)
        conn.sendall("[OK] File deleted.".encode(FORMAT))

    except (OSError, IndexError, FileNotFoundError, ValueError, PermissionError) as e:
        conn.sendall(f"[ERROR] {e}".encode(FORMAT))

    finally:
        if tracking:
            active_files.discard(filename)


def directory(conn):
    try:
        # check if directory is empty
        contents = os.listdir(SERVER_PATH)
        if not contents:
            conn.sendall("EMPTY".encode(FORMAT))
            return

        files = []

        # get the info for every file
        for name in contents:
            file_path = os.path.join(SERVER_PATH, name)
            if os.path.isdir(file_path):
                file_type = "Folder"
                file_size = 0
            else:
                file_type, _ = mimetypes.guess_type(name)
                file_type = file_type.split("/")[0].capitalize() if file_type else "Other"
                file_size = os.path.getsize(file_path)

            files.append(f"{name}@{file_size}@{file_type}")

        conn.sendall("[OK] Server directory:".encode(FORMAT))
        conn.sendall("\n".join(files).encode(FORMAT))


    except OSError as e:
        conn.sendall(f"[ERROR] {e}".encode(FORMAT))  


def subfolder_create(conn, cmd_parts):
    try:
        # verify a folder name was sent
        foldername = cmd_parts[1].strip()
        if not foldername:
            raise ValueError("No folder name provided.")

        # make sure the path is not outside the server folder
        folder_path = os.path.realpath(os.path.join(SERVER_PATH, foldername))
        server_path = os.path.realpath(SERVER_PATH)
        if os.path.commonpath([server_path, folder_path]) != server_path:
            raise ValueError("Invalid folder path.")

        # check if folder already exists
        if os.path.exists(folder_path):
            raise FileExistsError("Folder already exists.")

        # create the folder
        os.makedirs(folder_path)

        conn.sendall(f"[OK] Folder '{foldername}' created.".encode(FORMAT))

    except (OSError, IndexError, ValueError, FileExistsError) as e:
        conn.sendall(f"[ERROR] {e}".encode(FORMAT))


def subfolder_delete(conn, cmd_parts):
    try:
        # verify a folder name was sent
        foldername = cmd_parts[1].strip()
        if not foldername:
            raise ValueError("No folder name provided.")

        # make sure the path is not outside the server folder
        folder_path = os.path.realpath(os.path.join(SERVER_PATH, foldername))
        server_path = os.path.realpath(SERVER_PATH)
        if os.path.commonpath([server_path, folder_path]) != server_path or folder_path == server_path:
            raise ValueError("Invalid folder path.")

        # verify the folder exists
        if not os.path.isdir(folder_path):
            raise FileNotFoundError("Folder does not exist.")

        # delete folder (only works if empty)
        os.rmdir(folder_path)

        conn.sendall(f"[OK] Folder '{foldername}' deleted.".encode(FORMAT))

    except (OSError, IndexError, ValueError, FileNotFoundError) as e:
        conn.sendall(f"[ERROR] {e}".encode(FORMAT))

### to handle client input

def handle_command(conn, cmd_parts):
    cmd = cmd_parts[0]
    thread = threading.current_thread().name.split()[0].upper()
    print()

    if cmd == commands[0]:
        print(f"[{thread}] UPLOAD {cmd_parts[1] if len(cmd_parts) > 1 else ''}")
        upload(conn, cmd_parts)

    elif cmd == commands[1]:
        print(f"[{thread}] DOWNLOAD {cmd_parts[1] if len(cmd_parts) > 1 else ''}")
        download(conn, cmd_parts)

    elif cmd == commands[2]:
        print(f"[{thread}] DELETE {cmd_parts[1] if len(cmd_parts) > 1 else ''}")
        delete(conn, cmd_parts)

    elif cmd == commands[3] or cmd == "DIR":
        print(f"[{thread}] DIR requested.")
        directory(conn)
        print(f"[{thread}] Directory list sent.")

    elif cmd == commands[4]:
        print(f"[{thread}] CREATE FOLDER {cmd_parts[1] if len(cmd_parts) > 1 else ''}")
        subfolder_create(conn, cmd_parts)

    elif cmd == commands[5]:
        print(f"[{thread}] DELETE FOLDER {cmd_parts[1] if len(cmd_parts) > 1 else ''}")
        subfolder_delete(conn, cmd_parts)

    else:
        print(f"[{thread}] Invalid command: {cmd}")
        conn.sendall("[ERROR] Invalid command.".encode(FORMAT))


### to handle the clients
def handle_client(conn, addr):
    global active_clients
    
    print()
    print(f"[CONNECT] {addr[0]}:{addr[1]}")
    active_clients += 1
    client_num = active_clients
    print(f"[{threading.current_thread().name.split()[0].upper()}] Started for Client {client_num}")

    conn.sendall("[OK] Connected to server.".encode(FORMAT))

    # authenticate user
    if not authenticate(conn):
        conn.close()
        return

    while True:
        try:
            data = conn.recv(SIZE).decode(FORMAT)
        except ConnectionResetError:
            active_clients -= 1
            break

        if not data:
            break

        cmd_parts = data.split("@")
        cmd = cmd_parts[0].strip().upper()
        cmd_parts[0] = cmd

        if cmd == "DISCONNECT":
            conn.sendall("[OK] Disconnected from server.".encode(FORMAT))
            break
        else:
            handle_command(conn, cmd_parts)

    print(f"[DISCONNECT] Client {client_num} disconnected")
    conn.close()


def main():

    print("\033[92mFILE SHARING SERVER v1.0\033[0m")
    print("[SERVER] Starting...")

    server = socket.socket(socket.AF_INET,socket.SOCK_STREAM) ## used IPV4 and TCP connection
    server.bind(ADDR) # bind the address
    server.listen() ## start listening

    print("[SERVER] IP: ", IP)
    print("[SERVER] Port: ", PORT)

    os.makedirs(SERVER_PATH, exist_ok=True)
    print("[SERVER] Storage initialized.")

    print("[ANALYSIS] Monitoring started.")

    print("[SERVER] Listening for connections...")

    while True:
        conn, addr = server.accept() ### accept a connection from a client
        thread = threading.Thread(target = handle_client, args = (conn, addr)) ## assigning a thread for each client
        thread.start()


if __name__ == "__main__":
    main()
