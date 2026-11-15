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
                    welcome_msg = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    print(f"[OK] Connected to server: {welcome_msg}")
                    
                    # secure authentication: hash password with SHA-256
                    # username = input("Username: ").strip()
                    # password = getpass.getpass("Password: ")
                    # hashedPW = hashlib.sha256(password.encode()).hexdigest()
                    
                    # send authentication packet
                    # authData = f"AUTH@{username}@{hashedPW}"
                    # clientSocket.sendall(authData.encode('utf-8'))
                    
                    # receive and evaluate server authentication response
                    # response = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    # if "OK" in response or "SUCCESS" in response:
                    #     print("[OK] Authentication successful.")
                    #     connected = True
                    # else:
                    #     print("[ERROR] Authentication failed.")
                    #     clientSocket.close()
                    #     clientSocket = None
                        
                    connected = True # remove once authentication is live
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
                    if "Overwrite?" in srvRes:
                        choice = input(f"[?] {srvRes} ").strip().upper()
                        clientSocket.sendall(choice.encode('utf-8'))
                        if choice != 'Y':
                            cancel_msg = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                            print(f"[*] {cancel_msg}")
                            continue
                        clientSocket.recv(BUFFER_SIZE).decode('utf-8') # wait for READY
                        
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
                    confirmation = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    duration = time.time() - startTime
                    dataRate = fileSizeMB / duration if duration > 0 else 0
                    
                    print("Progress: 100%")
                    print(f"Size: {fileSizeMB} MB")
                    print(f"Transfer Time: {duration:.2f} seconds")
                    print(f"Average Speed: {dataRate:.2f} MB/s")
                    print(f"{confirmation}")
                    logMetrics("UPLOAD", fileName, fileSize, duration)
                    
                # 2. download operation: requests file and streams incoming binary data into local storage
                elif action == "2" or action == "download":
                    fileName = input("Enter server file name to download: ").strip()
                    req = f"DOWNLOAD@{fileName}"
                    clientSocket.sendall(req.encode('utf-8'))
                    
                    response = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    if "[ERROR]" in response:
                        print(f"{response}")
                        continue
                    
                    if "SIZE@" in response:
                        fileSize = int(response.split("@")[1])
                        fileSizeMB = round(fileSize / (1024 * 1024), 2)
                    else:
                        print(f"[ERROR] Unexpected response: {response}")
                        continue
                    
                    if os.path.exists(fileName):
                        choice = input(f"[?] Local file '{fileName}' exists. Overwrite? (Y/N): ").strip().upper()
                        if choice != 'Y':
                            clientSocket.sendall(b"CANCEL")
                            print("[*] Download cancelled.")
                            continue
                    
                    clientSocket.sendall(b"READY")
                    
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
                    print(f"{res}")
                        
                # 4. dir operation: requests and displays server directory inventory list
                elif action == "4" or action == "dir":
                    req = "DIRECTORY@"
                    clientSocket.sendall(req.encode('utf-8'))
                    res = clientSocket.recv(BUFFER_SIZE * 4).decode('utf-8')
                    print(f"{res}")
                    
                # 5. subfolder create operation: requests creation of a new subfolder path
                elif action == "5" or action == "subfolder create":
                    path = input("Enter folder name to create: ").strip()
                    req = f"SUBFOLDER CREATE@{path}"
                    clientSocket.sendall(req.encode('utf-8'))
                    res = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    print(f"{res}")
                        
                # 6. subfolder delete operation: requests deletion of an empty subfolder path
                elif action == "6" or action == "subfolder delete":
                    path = input("Enter folder name to delete: ").strip()
                    req = f"SUBFOLDER DELETE@{path}"
                    clientSocket.sendall(req.encode('utf-8'))
                    res = clientSocket.recv(BUFFER_SIZE).decode('utf-8')
                    print(f"{res}")
                    
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