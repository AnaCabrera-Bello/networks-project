import os
import socket
import threading

IP = "172.20.10.12"
PORT = 4450
ADDR = (IP,PORT)
SIZE = 1024
FORMAT = "utf-8"
SERVER_PATH = "server"

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


### to handle individual commands
def upload(conn, cmd_parts):
    try:
        temp_path = None
        filename = cmd_parts[1].strip()
        size = int(cmd_parts[2].strip())

        if not filename:
            raise ValueError("No filename provided.")

        file_path = os.path.join(SERVER_PATH, filename)
        temp_path = file_path + ".tmp"
        
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

        with open(temp_path, "wb") as file:
            remaining = size

            while remaining > 0:
                chunk = conn.recv(min(SIZE, remaining))
                file.write(chunk)
                remaining -= len(chunk)

                if not chunk:
                    raise ConnectionError("Client disconnected during upload.")

        os.replace(temp_path, file_path)
        conn.sendall("[OK] Upload successful.".encode(FORMAT))
        
    except (OSError, ValueError, IndexError, ConnectionError) as e:
        if temp_path and os.path.isfile(temp_path):
            os.remove(temp_path)

        conn.sendall(f"[ERROR] {e}".encode(FORMAT))


def download(conn, cmd_parts):
    try:
        # verify a filename was sent
        filename = cmd_parts[1].strip()
        if not filename:
            raise ValueError("No filename provided.")

        # verify the file exists
        file_path = os.path.join(SERVER_PATH, filename)
        if not os.path.isfile(file_path):
            raise FileNotFoundError("File does not exist.")

        # get file size and send to client
        size = os.path.getsize(file_path)
        conn.sendall(f"SIZE@{size}".encode(FORMAT))

        # wait for "READY" response from client to send file (if not ready, stop)
        response = conn.recv(SIZE).decode(FORMAT).strip().upper()
        if response != "READY":
            return

        # send file
        with open(file_path, "rb") as file:
            while True:
                chunk = file.read(SIZE)

                if not chunk:
                    break

                conn.sendall(chunk)

        


        

    except (OSError, IndexError, FileNotFoundError, ValueError) as e:
        conn.sendall(f"[ERROR] {e}".encode(FORMAT))


### to handle client input
def handle_command(conn, cmd_parts):

    if cmd_parts[0] == commands[0]:
        conn.sendall("Starting upload...".encode(FORMAT))
        upload(conn, cmd_parts)
        
    elif cmd_parts[0] == commands[1]:
        conn.sendall("Starting download...".encode(FORMAT))

    elif cmd_parts[0] == commands[2]:
        conn.sendall("Deleting file...".encode(FORMAT))

    elif cmd_parts[0] == commands[3] or cmd == "DIR":
        conn.sendall("Displaying directory...".encode(FORMAT))

    elif cmd_parts[0] == commands[4]:
        conn.sendall("Creating subfolder...".encode(FORMAT))

    elif cmd_parts[0] == commands[5]:
        conn.sendall("Deleting subfolder...".encode(FORMAT))

    else:
        conn.sendall("Invalid command.".encode(FORMAT))


### to handle the clients
def handle_client (conn,addr):

    print(f"[NEW CONNECTION] {addr} connected.")
    conn.send("OK@Welcome to the server".encode(FORMAT))

    while True:
        data = conn.recv(SIZE).decode(FORMAT)

        if not data:
            break

        data = data.split("@")
        cmd = data[0].strip().upper()
        cmd_info = data[1].strip() if len(data) > 1 else ""
       
        send_data = "OK@"

        if cmd == "LOGOUT":
            break

        elif cmd == "TASK": 
            send_data += "LOGOUT from the server.\n"

            conn.send(send_data.encode(FORMAT))



    print(f"{addr} disconnected")
    conn.close()


def main():

    print("\033[92mFILE SHARING SERVER v1.0\033[0m")
    print("[SERVER] Starting...")

    server = socket.socket(socket.AF_INET,socket.SOCK_STREAM) ## used IPV4 and TCP connection
    server.bind(ADDR) # bind the address
    server.listen() ## start listening

    print("[SERVER] IP: ", IP)
    print("[SERVER] Port: ", PORT)
    print("[SERVER] Listening for connections...")

    while True:
        conn, addr = server.accept() ### accept a connection from a client
        thread = threading.Thread(target = handle_client, args = (conn, addr)) ## assigning a thread for each client
        thread.start()


if __name__ == "__main__":
    main()
