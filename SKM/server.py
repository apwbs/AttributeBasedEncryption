import socket
import ssl
import threading
import abenc_adapt_hybrid
import abenc_adapt_hybrid_reading
from datetime import datetime
import random
import sqlite3
from hashlib import sha512

HEADER = 64
PORT = 5050
server_cert = 'Keys/server.crt'
server_key = 'Keys/server.key'
client_certs = 'Keys/client.crt'
SERVER = socket.gethostbyname(socket.gethostname())
ADDR = (SERVER, PORT)
FORMAT = 'utf-8'
DISCONNECT_MESSAGE = "!DISCONNECT"

"""
creation and connection of the secure channel using SSL protocol
"""

context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
context.verify_mode = ssl.CERT_REQUIRED
context.load_cert_chain(certfile=server_cert, keyfile=server_key)
context.load_verify_locations(cafile=client_certs)
bindsocket = socket.socket()
bindsocket.bind(ADDR)
bindsocket.listen(5)


def generate(message):
    return abenc_adapt_hybrid.main(message)


def read(message):
    return abenc_adapt_hybrid_reading.main(message)


"""
function that handles the requests from the clients. There are two possible requests, namely the 
creation of a key and the deciphering of a ciphertext.
"""


def handle_client(conn, addr):
    print(f"[NEW CONNECTION] {addr} connected.")

    connected = True
    while connected:
        msg_length = conn.recv(HEADER).decode(FORMAT)
        if msg_length:
            msg_length = int(msg_length)
            msg = conn.recv(msg_length).decode(FORMAT)
            if msg == DISCONNECT_MESSAGE:
                connected = False

            # print(f"[{addr}] {msg}")
            conn.send("Msg received!".encode(FORMAT))
            message = msg.split('||')
            if message[0] == "Please certify signature":
                now = datetime.now()
                now = int(now.strftime("%Y%m%d%H%M%S%f"))
                random.seed(now)
                number_to_sign = random.randint(1, 2 ** 64)
                connection = sqlite3.connect('Database_SKM/signatures.db')
                x = connection.cursor()
                x.execute("INSERT OR IGNORE INTO signatures VALUES (?,?)",
                          (message[1], str(number_to_sign)))
                connection.commit()
                conn.send(b'Here is the number: ' + str(number_to_sign).encode())
            if message[0] == "Please generate my key":
                connection = sqlite3.connect('Database_SKM/signatures.db')
                x = connection.cursor()
                x.execute("SELECT * FROM signatures WHERE address = ?", (message[2],))
                user_signature = x.fetchall()
                user_signature = user_signature[0][1]
                connection1 = sqlite3.connect('Database_Reader/public_key.db')
                y = connection1.cursor()
                y.execute("SELECT * FROM publicKeys WHERE address = ?", (message[2],))
                user_public_key = y.fetchall()
                hash = int.from_bytes(sha512(str(user_signature).encode()).digest(), byteorder='big')
                hashFromSignature = pow(int(message[3]), int(user_public_key[0][2]), int(user_public_key[0][1]))
                if hash == hashFromSignature:
                    response = generate(message)
                    response_0 = bytes(str(response[0]), FORMAT)
                    response_1 = bytes(str(response[1]), FORMAT)
                    conn.send(b'Here is IPFS link and key: ' + response_0 + b'\n\n' + response_1)
            if message[0] == "Please read my data":
                connection = sqlite3.connect('Database_SKM/signatures.db')
                x = connection.cursor()
                x.execute("SELECT * FROM signatures WHERE address = ?", (message[4],))
                user_signature = x.fetchall()
                user_signature = user_signature[0][1]
                connection1 = sqlite3.connect('Database_Reader/public_key.db')
                y = connection1.cursor()
                y.execute("SELECT * FROM publicKeys WHERE address = ?", (message[4],))
                user_public_key = y.fetchall()
                hash = int.from_bytes(sha512(str(user_signature).encode()).digest(), byteorder='big')
                hashFromSignature = pow(int(message[5]), int(user_public_key[0][2]), int(user_public_key[0][1]))
                if hash == hashFromSignature:
                    response = read(message)
                    conn.send(b'Here is plaintext and salt:\n\n' + response[0] + b'\n\n' + response[1])

    conn.close()


"""
main function starting the server. It listens on a port and waits for a request from a client
"""


def start():
    bindsocket.listen()
    print(f"[LISTENING] Server is listening on {SERVER}")
    while True:
        newsocket, fromaddr = bindsocket.accept()
        conn = context.wrap_socket(newsocket, server_side=True)
        thread = threading.Thread(target=handle_client, args=(conn, fromaddr))
        thread.start()
        print(f"[ACTIVE CONNECTIONS] {threading.activeCount() - 1}")


print("[STARTING] server is starting...")
start()
