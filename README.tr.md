# biRun (Türkçe)

Sunucular arasında script yönetimi ve çalıştırmayı kolaylaştıran; gelişmiş iş akışı otomasyonu, gerçek zamanlı izleme ve modern koyu/açık tema arayüzüne sahip kapsamlı bir web uygulaması.

## 🚀 Özellikler

### Temel İşlevler
- **Kullanıcı Yönetimi**: JWT tabanlı güvenli kimlik doğrulama ve rol tabanlı erişim kontrolü
- **Sunucu Yönetimi**: SSH anahtar doğrulamasıyla sunucu ekleme, düzenleme ve yönetim
- **Script Yönetimi**: Sözdizimi vurgulama ile script oluşturma, düzenleme ve organize etme
- **Çalıştırma Motoru**: Script’leri tekil sunucularda veya sunucu gruplarında çalıştırma
- **Zamanlanmış Çalıştırma**: Cron ifadeleri ve saat dilimi desteği ile otomasyon
- **Gerçek Zamanlı İzleme**: Anlık çıktı akışı ve çalıştırma geçmişi
- **Sunucu Grupları**: Toplu işlemler için mantıksal gruplama
- **Terminal Erişimi**: Etkileşimli SSH terminal oturumları

### İleri Seviye Özellikler
- **İş Akışı Otomasyonu**: Sürükle-bırak görsel iş akışı oluşturucu
- **İş Akışı Tetikleyicileri**: Kullanıcı, zamanlama (cron) ve webhook tetikleyicileri
- **Gerçek Zamanlı İş Akışı İzleme**: Çalıştırma sırasında WebSocket ile canlı güncellemeler
- **Tekrar Deneme Politikaları**: Yapılandırılabilir tekrar deneme mantığı
- **Grup Hata Politikaları**: Sunucu gruplarında hata davranış kontrolü
- **Pazar Yeri**: Topluluktan script keşfetme ve paylaşma
- **Sunucu Sağlık İzleme**: CPU, bellek ve disk kullanımı için otomatik kontroller
- **Denetim Kayıtları**: Tüm işlemler için kapsamlı audit izi

### Kullanıcı Arayüzü
- **Koyu/Açık Tema**: Modern karanlık tema (varsayılan) ve aydınlık tema
- **Duyarlı Tasarım**: Masaüstü ve mobil cihazlarda sorunsuz kullanım
- **Panel & Gösterge**: Grafikler ve istatistiklerle genel bakış
- **Gerçek Zamanlı Güncellemeler**: Canlı durum ve bildirimler

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
   ```bash
   git clone <repository-url>
   cd script-manager/
   ```

2. **Backend’i başlatın**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Frontend’i başlatın**
   ```bash
   cd frontend
   npm install
   npm start
   ```

4. **Yönetici kullanıcı oluşturun**
   ```bash
   cd backend
   python create_admin.py
   ```

5. **Uygulamaya erişim**
   - Arayüz: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Dokümanları: http://localhost:8000/docs

## 📁 Proje Yapısı

```
script-manager/
├── backend/                    # FastAPI backend
│   ├── main.py                # Ana uygulama
│   ├── models.py              # Veritabanı modelleri
│   ├── schemas.py             # Pydantic şemaları
│   ├── routers/               # API uç noktaları
│   │   ├── auth.py            # Kimlik doğrulama
│   │   ├── users.py           # Kullanıcı yönetimi
│   │   ├── servers.py         # Sunucu yönetimi
│   │   ├── scripts.py         # Script yönetimi
│   │   ├── workflows.py       # İş akışı otomasyonu
│   │   ├── health.py          # Sağlık izleme
│   │   ├── marketplace.py     # Pazar yeri
│   │   └── ...
│   ├── database.py            # Veritabanı yapılandırması
│   ├── auth.py                # Kimlik doğrulama mantığı
│   ├── scheduler.py           # Arka plan zamanlayıcı
│   └── health_commands.py     # Sağlık kontrol komutları
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── components/        # React bileşenleri
│   │   │   ├── Dashboard.js   # Ana panel
│   │   │   ├── Workflows.js   # İş akışı yönetimi
│   │   │   ├── WorkflowBuilder.js # Görsel iş akışı oluşturucu
│   │   │   ├── WorkflowMonitor.js # Gerçek zamanlı izleme
│   │   │   ├── Marketplace.js # Script pazar yeri
│   │   │   └── ...
│   │   ├── contexts/          # React context’leri
│   │   │   └── ThemeContext.js # Tema yönetimi
│   │   ├── styles/            # CSS stilleri
│   │   │   └── themes.css     # Tema değişkenleri
│   │   └── App.js             # Ana uygulama bileşeni
│   └── public/                # Statik varlıklar
└── README.md                  # İngilizce doküman
```

## 🎯 Kullanım

### Başlarken
1. **Giriş yapın** (admin hesabı ile)
2. **Sunucu ekleyin** (SSH erişimi: parola veya anahtar)
3. **Script oluşturun** (Python, Bash, PowerShell)
4. **Script çalıştırın** (tek sunucu veya grup)
5. **Zamanlayın** (otomatik çalıştırmalar)
6. **Sonuçları izleyin** (gerçek zamanlı)

### İş Akışı Otomasyonu
1. **Görsel oluşturucu** ile iş akışı oluşturun
2. **Düğüm ekleyin** ve bağlantıları tanımlayın
3. **Tetikleyici seçin** (kullanıcı, zamanlama veya webhook)
4. **Tekrar deneme** ve **hata** politikalarını ayarlayın
5. **Gerçek zamanda izleyin**
6. **Geçmişi ve log’ları** inceleyin

### Pazar Yeri
1. **Script keşfedin** (kategori ve etiketler)
2. **Arayın ve filtreleyin**
3. **İndirin ve koleksiyonunuza ekleyin**
4. **Toplulukla paylaşın**

### Sunucu Sağlık İzleme
1. **Sağlık kontrollerini yapılandırın**
2. **CPU, bellek ve disk** kullanımını izleyin
3. **Otomatik izleme** ayarlarını yapın

## 🔒 Güvenlik Özellikleri

- **JWT tabanlı kimlik doğrulama** ve güvenli token yönetimi
- **bcrypt** ile parola saklama
- **Şifreli SSH anahtar yönetimi**
- **Rol tabanlı erişim kontrolü** (admin/kullanıcı)
- **Denetim kayıtları** (audit)
- **CORS** ve güvenlik başlıkları

## 🎨 Temalar

Uygulama koyu ve açık temaları destekler:
- **Koyu Tema**: Modern, göz yormayan arayüz (varsayılan)
- **Açık Tema**: Sade ve profesyonel
- **Tema Geçişi**: Anında geçiş
- **Tutarlı Stil**: Tüm bileşenler temaya uyum sağlar

## 📊 İzleme ve Analitik

- **Gerçek Zamanlı Panel**: Canlı istatistikler ve grafikler
- **Çalıştırma Geçmişi**: Tam denetim izi
- **Performans Metrikleri**: Sunucu ve script performansı
- **Sağlık İzleme**: Otomatik kontroller
- **İş Akışı Analitiği**: Başarı oranları ve süreler

## 🔧 Yapılandırma

### Ortam Değişkenleri
- `SECRET_KEY`: JWT gizli anahtarı
- `DATABASE_URL`: Veritabanı bağlantı dizesi
- `CORS_ORIGINS`: İzin verilen CORS kaynakları

### Sunucu Yapılandırması
- SSH anahtar/parola doğrulama
- Özel SSH portları
- Sunucu gruplama ve etiketleme

## 🚀 Dağıtım

### Üretim Kurulumu
1. **Ortam değişkenlerini** ayarlayın
2. **Ters proxy** (nginx/Apache) yapılandırın
3. **SSL sertifikaları** ekleyin
4. **Yedekleme** ve geri yükleme stratejisi oluşturun
5. **İzleme ve loglama** yapılandırın

### Docker Desteği
```bash
# Docker Compose ile derleyip çalıştırın
docker-compose up -d
```

## 🤝 Katkı

1. Depoyu forklayın
2. Özellik dalı açın (`git checkout -b feature/harika-ozellik`)
3. Değişiklikleri yapın
4. İyice test edin
5. Commit atın (`git commit -m 'Harika özellik eklendi'`)
6. Dalı itin (`git push origin feature/harika-ozellik`)
7. Pull Request açın

## 📝 Lisans



## 🆘 Destek

Destek ve sorular için:
- Depoda issue açın
- Dokümantasyonu inceleyin
- `/docs` altındaki API dokümanlarına göz atın

## 🎉 Güncel Yenilikler

- ✅ **İş Akışı Otomasyonu**: Görsel oluşturucu tamamlandı
- ✅ **Gerçek Zamanlı İzleme**: WebSocket tabanlı canlı güncellemeler
- ✅ **Pazar Yeri**: Script paylaşımı ve keşif
- ✅ **Sağlık İzleme**: Otomatik sunucu kontrolleri
- ✅ **Tema Sistemi**: Koyu/açık tema geçişi
- ✅ **Denetim Kayıtları**: Kapsamlı işlem takibi
- ✅ **Tekrar Deneme Politikaları**: Gelişmiş hata yönetimi
- ✅ **Veritabanı İyileştirmeleri**: Performans ve güvenilirlik artışı

---

**biRun** - Güçlü iş akışları ve gerçek zamanlı izleme ile sunucu otomasyonunu hızlandırın! 🚀


