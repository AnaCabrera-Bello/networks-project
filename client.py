import socket
import os
import json
import hashlib
import time
import getpass
from analysis import logMetrics

# chunk size set to 4 KB to prevent memory overflow when streaming large files
BUFFER_SIZE = 4096
    
def main():
    clientSocket = None
    connected = False
    
    while True:
        if not connected:
            # wait for user input in main shell
            userInput = input("> ").strip().split()
            if not userInput:
                continue
            
            command = userInput[0].lower()
            if command == "exit" or command == "quit":
                break
            elif command == "connect":
                #prompt user for server IP and port
                serverIP = input("Sever IP: ").strip()
                serverPort = int(input("Server Port: ").strip())
                
                try:
                    # establish TCP connection using IPv4 and Stream Sockets
                    clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    clientSocket.connect((serverIP, serverPort))
                    print("[OK] Connected to server.")
                    
                    # secure authentication: hash password with SHA-256
                    username = input("Username: ").strip()
                    password = getpass.getpass("Password: ")
                    hashedPW = hashlib.sha256(password.encode()).hexdigest()
                    
                    # send authentication packet
                    authData = f"AUTH@{username}@{hashedPW}"
                    clientSocket.sendall(authData.encode('utf-8'))
                    
                    # receive and evaluate server authentication response
                    response = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    parts = response.split("@", 1)
                    status = parts[0]
                    msg = parts[1] if len(parts) > 1 else ""
                    
                    if status == "OK" or status == "SUCCESS":
                        print(f"[OK] {msg}")
                        connected = True
                    else:
                        print(f"[ERROR] {msg or 'Authentication failed.'}")
                        clientSocket.close()
                        clientSocket = None
                except Exception as e:
                    print(f"[ERROR] Connection failed: {e}")
            else:
                print("[ERROR] Type 'connect' to initiate a server connection.")
        
        else:
            # interactive command menu
            print("\n========== COMMAND MENU ==========")
            print("1. Upload")
            print("2. Download")
            print("3. Delete")
            print("4. Dir")
            print("5. Subfolder Create")
            print("6. Subfolder Delete")
            print("7. Disconnect")
            print("==================================")
            
            cmdInput = input("\n> ").strip().split()
            if not cmdInput:
                continue
            
            action = cmdInput[0].lower()
            
            try:
                # 1. upload operation: checks local file existence and streams file in chunks
                if action == "1" or action == "upload":
                    filePath = input("Enter local file path to upload: ").strip()
                    if not os.path.exists(filePath):
                        print("[ERROR] File not found.")
                        continue
                    
                    fileName = os.path.basename(filePath)
                    fileSize = os.path.getsize(filePath)
                    fileSizeMB = round(fileSize / (1024 * 1024), 2)
                    
                    # send upload request header containing metadata
                    req = f"UPLOAD@{fileName}@{fileSize}"
                    clientSocket.sendall(req.encode('utf-8'))
                    
                    # handle file overwrite confirmation
                    srvRes = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    if "@" in srvRes:
                        status, msg = srvRes.split("@", 1)
                        if status == "PROMPT_OVERWRITE":
                            choice = input(f"[?] {msg} (Y/N): ").strip().upper()
                            clientSocket.sendall(choice.encode('utf-8'))
                            if choice != 'Y':
                                print("[*] Upload cancelled.")
                                continue
                    
                    print(f"Uploading {fileName}...")
                    startTime = time.time()
                    
                    # read and send file binary contents in small chunks
                    with open(filePath, "rb") as f:
                        while True:
                            chunk = f.read(BUFFER_SIZE)
                            if not chunk:
                                break
                            clientSocket.sendall(chunk)
                            
                    # receive completion confirmation and calculate performance metrics
                    confirmation = json.loads(clientSocket.recv(BUFFER_SIZE).decode('utf-8'))
                    duration = time.time() - startTime
                    dataRate = fileSizeMB / duration if duration > 0 else 0
                    
                    if "OK" in confirmation or "SUCCESS" in confirmation:
                        print("Progress: 100%")
                        print(f"Size: {fileSizeMB} MB")
                        print(f"Transfer Time: {duration:.2f} seconds")
                        print(f"Average Speed: {dataRate:.2f} MB/s")
                        print("[OK] Upload completed.")
                        logMetrics("UPLOAD", fileName, fileSize, duration)
                    else:
                        print(f"[ERROR] Upload failed.")
                        
                # 2. download operation: requests file and streams incoming binary data into local storage
                elif action == "2" or action == "download":
                    fileName = input("Enter server file name to download: ").strip()
                    req = f"DOWNLOAD@{fileName}"
                    clientSocket.sendall(req.encode('utf-8'))
                    
                    response = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    parts = response.split("@")
                    
                    if parts[0] == "ERROR":
                        print(f"[ERROR] {parts[1] if len(parts) > 1 else 'File not found.'}")
                        continue
                    
                    # assuming server responds with "SUCCESS@filesize"
                    fileSize = int(parts[1]) if len(parts) > 1 else 0
                    fileSizeMB = round(fileSize / (1024 * 1024), 2)
                    
                    clientSocket.sendall(b"Y") # proceed download confirmation
                    
                    print(f"Downloading {fileName}...")
                    startTime = time.time()
                    
                    # receive file chunks sequentially until full file size is reached
                    bytesReceived = 0
                    with open(fileName, "wb") as f:
                        while bytesReceived < fileSize:
                            remaining = fileSize - bytesReceived
                            chunkSize = BUFFER_SIZE if remaining > BUFFER_SIZE else remaining
                            chunk = clientSocket.recv(chunkSize)
                            if not chunk:
                                break
                            f.write(chunk)
                            bytesReceived += len(chunk)
                            
                    duration = time.time() - startTime
                    dataRate = fileSizeMB / duration if duration > 0 else 0
                    
                    print("Progress: 100%")
                    print(f"Transfer Time: {duration:.2f} seconds")
                    print(f"Average Speed: {dataRate:.2f} MB/s")
                    print("[OK] Download completed.")
                    logMetrics("DOWNLOAD", fileName, fileSize, duration)
                    
                # 3. delete operation: requests deletion of a specified file from server storage
                elif action == "3" or action == "delete":
                    fileName = input("Enter filename to delete from server: ").strip()
                    req = f"DELETE@{fileName}"
                    clientSocket.sendall(req.encode('utf-8'))
                    res = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    parts = res.split("@", 1)
                    if parts[0] == "OK" or parts[0] == "SUCCESS":
                        print(f"[OK] {parts[1] if len(parts) > 1 else 'File deleted.'}")
                    else:
                        print(f"[ERROR] {parts[1] if len(parts) > 1 else 'Delete failed.'}")
                        
                # 4. dir operation: requests and displays server directory inventory list
                elif action == "4" or action == "dir":
                    req = "DIR@"
                    clientSocket.sendall(req.encode('utf-8'))
                    
                    res = clientSocket.recv(BUFFER_SIZE * 4).decode('utf-8')
                    print(f"[OK] Server directory response:\n{res}")
                    
                # 5. subfolder create operation: requests creation of a new subfolder path
                elif action == "5" or action == "subfolder create":
                    path = input("Enter folder name to create: ").strip()
                    req = f"SUBFOLDER@create@{path}"
                    clientSocket.sendall(req.encode('utf-8'))
                    
                    res = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    parts = res.split("@", 1)
                    if parts[0] == "OK" or parts[0] == "SUCCESS":
                        print(f"[OK] {parts[1] if len(parts) > 1 else 'Folder created.'}")
                    else:
                        print(f"[ERROR] {parts[1] if len(parts) > 1 else 'Action failed.'}")
                        
                # 6. subfolder delete operation: requests deletion of an empty subfolder path
                elif action == "6" or action == "subfolder delete":
                    path = input("Enter folder name to delete: ").strip()
                    req = f"SUBFOLDER@delete@{path}"
                    clientSocket.sendall(req.encode('utf-8'))
                    
                    res = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    parts = res.split("@", 1)
                    if parts[0] == "OK" or parts[0] == "SUCCESS":
                        print(f"[OK] {parts[1] if len(parts) > 1 else 'Folder deleted.'}")
                    else:
                        print(f"[ERROR] {parts[1] if len(parts) > 1 else 'Action failed.'}")
                        
                # 7. disconnect operation: safely terminates socket session with server
                elif action == "7" or action == "disconnect":
                    req = "DISCONNECT@"
                    clientSocket.sendall(req.encode('utf-8'))
                    clientSocket.close()
                    connected = False
                    print("[OK] Disconnected from server.")

                else:
                    print("[ERROR] Invalid choice. Please choose a valid menu option (1-7).")

            except Exception as e:
                print(f"[ERROR] Communication error: {e}")
                if clientSocket:
                    clientSocket.close()
                connected = False

if __name__ == "__main__":
    main()