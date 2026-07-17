# 🚀 Loyihani ishga tushirish bo'yicha qo'llanma

Ushbu loyihani mahalliy muhitda ishga tushirish uchun quyidagi qadamlarni bajaring.

> ⚠️ Loyiha faqat **PostgreSQL** bilan ishlaydi. SQLite'ga zaxira varianti yo'q: sozlama
> noto'g'ri bo'lsa, loyiha ataylab ishga tushmaydi va xatolikni ko'rsatadi.

### 1. Loyihani tayyorlash

Terminalda loyiha papkasiga o'ting va kerakli kutubxonalarni o'rnating:

```bash
# Virtual muhit yaratish
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Loyiha papkasiga o'tish
cd src

# Kerakli kutubxonalarni o'rnatish
pip install -r requirements/dev.txt
```

### 2. Muhit sozlamalari (`.env`)

`.env` fayli repozitoriyda yo'q (u `.gitignore` ichida), shuning uchun uni shablondan yaratish
kerak:

```bash
cp .env.example .env
```

So'ng `.env` faylini oching va ikkita qiymatni to'ldiring:

```bash
# 1. SECRET_KEY yarating va uni .env ga qo'ying:
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"

# 2. O'zingizning PostgreSQL'ingiz uchun DB_NAME va DB_USER ni ko'rsating.
```

⚠️ **Bu qadamsiz loyiha ishga tushmaydi** — `env("SECRET_KEY")` `ImproperlyConfigured`
xatoligini beradi.

`DB_HOST` ni **bo'sh qoldiring**: shunda mahalliy Unix-socket ishlatiladi (parol talab
qilinmaydi). Agar host ko'rsatsangiz, `DB_PASSWORD` ham kerak bo'ladi.

### 3. Ma'lumotlar bazasi

Bazani yarating va migratsiya qiling:

```bash
createdb tz_app
python manage.py migrate
```

### 4. Test ma'lumotlari

```bash
python manage.py seed_data
```

Bu buyruq rollar (Admin, Manager, Employee, Guest), huquqlar va administrator yaratadi:

```
Email:  admin@gmail.com
Parol:  admin123
```

Buyruq **idempotent** — uni istagancha ko'p marta ishga tushirish mumkin, nusxalar
yaratilmaydi.

### 5. Serverni ishga tushirish

```bash
python manage.py runserver
```

| Manzil | Nima |
| --- | --- |
| `http://127.0.0.1:8000/api/v1/` | API |
| `http://127.0.0.1:8000/api/v1/docs/` | Swagger UI — interaktiv hujjatlar |
| `http://127.0.0.1:8000/admin/` | Django admin paneli |

---

### 🛠 Postman konfiguratsiyasi

API so'rovlarini test qilish uchun Postman sozlamalarini quyidagicha bajaring:

1. **Postman** ilovasini oching.
2. **Import** → `postman-variables.json` faylini tanlang. Bu — **muhit (environment)**, uni
   o'ng yuqoridagi ro'yxatdan tanlab qo'ying.
3. **Import** → `postman-workflows.json` faylini tanlang. Bu — **kollektsiya**.
4. **1. Auth → Login (admin)** so'rovini bajaring.

Boshqa hech narsani qo'lda kiritish shart emas: bu so'rovning skripti tokenlarni o'zi saqlaydi,
qolgan barcha so'rovlar ularni avtomatik ishlatadi. Papkalar yuqoridan pastga ketma-ket
bajarilishga mo'ljallangan — har biri keyingisiga kerak bo'ladigan id larni saqlab boradi.

Butun kollektsiyani terminaldan ishga tushirish (50 ta so'rov, 107 ta tekshiruv):

```bash
npx newman run postman-workflows.json -e postman-variables.json
```

> 💡 **Eslatma:** to'liq hujjatlar `src/README.md` faylida (rus tilida) hamda Swagger UI da:
> `http://127.0.0.1:8000/api/v1/docs/`.
