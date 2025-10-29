# biRun (TR)

Sunucular arası script yönetimi ve çalıştırma için gelişmiş iş akışı otomasyonu, gerçek zamanlı izleme ve modern koyu/açık tema arayüzüne sahip kapsamlı bir web uygulaması.

## 🚀 Özellikler

### Temel İşlevler
- **Kullanıcı Yönetimi**: JWT ile güvenli kimlik doğrulama ve rol tabanlı erişim kontrolü
- **Sunucu Yönetimi**: SSH anahtar doğrulamasıyla sunucu ekleme/düzenleme/yönetim
- **Script Yönetimi**: Vurgu renklendirme ile script oluşturma, düzenleme, organize etme
- **Çalıştırma Motoru**: Script'leri tekil sunucularda veya sunucu gruplarında çalıştırma
- **Zamanlama**: Cron ifadeleri ve saat dilimi desteği ile otomatik çalıştırma
- **Gerçek Zamanlı İzleme**: Anlık çıktı akışı ve çalıştırma geçmişi
- **Sunucu Grupları**: Toplu işlemler için mantıksal gruplama
- **Terminal Erişimi**: Etkileşimli SSH terminal oturumları

### İleri Seviye Özellikler
- **İş Akışı Otomasyonu**: Sürükle-bırak görsel iş akışı oluşturucu
- **Tetikleyiciler**: Kullanıcı, zamanlama (cron) ve webhook tetikleyicileri
- **Gerçek Zamanlı İş Akışı İzleme**: WebSocket ile canlı durum güncellemeleri
- **Tekrar Deneme Politikaları**: Yapılandırılabilir tekrar denemeler
- **Grup Hata Politikaları**: Grup çalıştırmalarında hata davranış kontrolü
- **Pazar Yeri**: Topluluk script’lerini keşfetme ve indirme
- **Sunucu Sağlık İzleme**: CPU, bellek, disk kullanımına yönelik otomatik kontroller
- **Denetim Kayıtları**: Tüm işlemler için kapsamlı kayıt

### Arayüz
- **Koyu/Açık Tema**: Anında tema değiştirme
- **Duyarlı Tasarım**: Masaüstü ve mobilde sorunsuz kullanım
- **Panel**: Grafikler ve istatistiklerle genel bakış
- **Canlı Güncellemeler**: Anlık durum ve bildirimler

## 🛠 Teknoloji Yığını
- **Backend**: FastAPI, SQLite, SQLAlchemy, Paramiko (SSH)
- **Frontend**: React 18, Bootstrap 5, Monaco Editor, Recharts
- **Kimlik Doğrulama**: JWT, bcrypt
- **Gerçek Zamanlı**: WebSockets
- **Zamanlama**: croniter
- **SSH**: paramiko
- **Saat Dilimi**: zoneinfo

## 🚀 Hızlı Başlangıç

### Önkoşullar
- Python 3.8+
- Node.js 16+
- npm veya yarn

### Kurulum
1. **Depoyu klonlayın**
   `ash
   git clone <repository-url>
   cd script-manager/
   `
2. **Backend’i başlatın**
   `ash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   `
3. **Frontend’i başlatın**
   `ash
   cd frontend
   npm install
   npm start
   `
4. **Yönetici kullanıcı oluşturun**
   `ash
   cd backend
   python create_admin.py
   `
5. **Uygulamaya erişim**
   - Arayüz: http://localhost:3000
   - API: http://localhost:8000
   - API Dokümanları: http://localhost:8000/docs

## 📁 Proje Yapısı
`
script-manager/
├── backend/
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── routers/
│   ├── database.py
│   ├── scheduler.py
│   └── health_commands.py
├── frontend/
│   └── src/
└── README.tr.md
`

## 🎯 Kullanım
### Başlarken
1. **Giriş yapın** (admin hesabıyla)
2. **Sunucu ekleyin** (SSH parolalı ve anahtar tabanlı erişim)
3. **Script oluşturun** (Python, Bash, PowerShell)
4. **Çalıştırın** (tekil sunucu veya gruplar)
5. **Zamanlayın** (otomatik çalıştırmalar)
6. **İzleyin** (gerçek zamanlı çıktı)

### İş Akışları
1. Görsel oluşturucuda iş akışı oluşturun
2. Script düğümleri ekleyin ve bağlayın
3. Tetikleyicileri ayarlayın (kullanıcı/zamanlama/webhook)
4. Tekrar deneme ve hata politikalarını yapılandırın
5. Çalıştırmayı canlı izleyin
6. Geçmişi ve log’ları inceleyin

### Pazar Yeri
1. Script’leri kategori ve etiketlerle keşfedin
2. Arayın ve filtreleyin
3. Script’leri indirin ve kullanın

### Sunucu Sağlığı
1. Sağlık kontrollerini yapılandırın
2. CPU, bellek ve disk kullanımını takip edin
3. Otomatik sağlık izlemeyi etkinleştirin

## 🔒 Güvenlik
- JWT ile oturum yönetimi
- bcrypt ile parola saklama
- Şifreli SSH anahtar yönetimi
- Rol tabanlı erişim kontrolü
- Denetim (audit) kayıtları
- CORS ve güvenlik başlıkları

## 🎨 Temalar
- **Koyu/Açık Tema** desteği
- **Tema geçişi** tek tıkla
- **Tutarlı stil** tüm bileşenlerde

## 📊 İzleme & Analitik
- Gerçek zamanlı panel ve grafikler
- Çalıştırma geçmişi ve denetim izi
- Sağlık izleme metrikleri

## 🔧 Yapılandırma
- SECRET_KEY, DATABASE_URL, CORS_ORIGINS
- SSH yapılandırmaları (parola/anahtar, port, gruplama, etiketleme)

## 🚀 Dağıtım
- Ortam değişkenlerini ayarlayın
- Ters proxy (nginx/Apache) ve SSL
- İzleme ve loglama

## 🤝 Katkı
1. Depoyu çatallayın (fork)
2. Branch oluşturun (eature/ozellik)
3. Değişiklikleri uygulayın ve test edin
4. PR açın

## 🆘 Destek
- Issue açın
- Dokümantasyonu kontrol edin
- /docs uç noktasını inceleyin

## 🎉 Güncel Yenilikler
- ✅ Görsel İş Akışı Oluşturucu
- ✅ Gerçek Zamanlı İzleme (WebSocket)
- ✅ Pazar Yeri (Marketplace)
- ✅ Sunucu Sağlık İzleme
- ✅ Koyu/Açık Tema
- ✅ Denetim Kayıtları
- ✅ Tekrar Deneme Politikaları

