# TRRCMS - Map & GIS System
## نظام الخرائط والبيانات الجغرافية - دليل البناء والربط

---

## 1. من أين تأتي الخرائط؟

التطبيق يحتاج نوعين من البيانات الجغرافية:

### 1.1 خريطة الخلفية (Base Map) — الشوارع والأحياء

هذه الخريطة التي تظهر كخلفية (شوارع، أحياء، معالم) تحت طبقة المباني.

**مصدرها:** ملف MBTiles — وهو ملف SQLite يحتوي صور خريطة مقسمة حسب مستويات التكبير (zoom levels).

**كيفية الحصول عليه:**

| الطريقة | الشرح |
|---------|-------|
| نوفره نحن | نجهز ملف MBTiles للمنطقة المستهدفة ونسلمه للعميل |
| تحميل من OpenStreetMap | عبر أدوات مثل openmaptiles.org (مجاني للمناطق الصغيرة) |
| تصدير من QGIS | **Processing** > **Toolbox** > **Generate XYZ tiles (MBTiles)** |
| سكريبت مضمن مع التطبيق | `python utils/download_aleppo_tiles.py --bbox MIN_LNG,MIN_LAT,MAX_LNG,MAX_LAT --zoom 10-18` |

الملف الحالي يغطي منطقة صغيرة من حلب (عدة أحياء للتطوير والاختبار).
التطبيق مبني ليتعامل مع خرائط أكبر بكثير (محافظة كاملة أو أكثر) — التجميع الذكي (Clustering) وتحميل البيانات حسب نطاق العرض (viewport loading) يضمنان أداء سلس حتى مع آلاف المباني.
لتغطية منطقة أكبر، يكفي تجهيز ملف MBTiles يغطي تلك المنطقة وتعديل الإحداثيات في `.env`.

### 1.2 بيانات المباني والمطالبات — من قاعدة البيانات

بيانات المباني والأشخاص والمطالبات مخزنة في قاعدة PostgreSQL + PostGIS.
هذه البيانات تُدخل عبر التطبيق نفسه أو تُستورد من ملفات.
التطبيق يعرضها كطبقة فوق خريطة الخلفية.

---

## 2. بناء سيرفر الخرائط (TileServer GL) — مطلوب

TileServer GL هو سيرفر مفتوح المصدر يقرأ ملف MBTiles ويقدم صور الخريطة عبر HTTP.
تطبيق الديسكتوب يطلب منه صور الخلفية (tiles) ويعرضها على الخريطة.

### 2.1 تجهيز ملف الخريطة

```bash
# إنشاء مجلد على السيرفر
mkdir -p /opt/trrcms/tiles

# نسخ ملف MBTiles إلى المجلد
cp aleppo_tiles.mbtiles /opt/trrcms/tiles/
```

### 2.2 تشغيل TileServer كحاوية Docker

```bash
docker run -d \
  --name trrcms-tileserver \
  -p 5000:8080 \
  -v /opt/trrcms/tiles:/data \
  --restart always \
  maptiler/tileserv-gl
```

هذا الأمر:
- يحمّل صورة TileServer GL من Docker Hub
- يربط مجلد `/opt/trrcms/tiles` (الذي فيه ملف MBTiles) بالحاوية
- يكشف السيرفر على بورت 5000

### 2.3 التحقق من عمل السيرفر

افتح في المتصفح:
```
http://<SERVER_IP>:5000
```
يجب أن تظهر واجهة تفاعلية تعرض الخريطة المتوفرة.

### 2.4 تغيير البورت (إذا لزم)

إذا كان بورت 5000 مشغول، غيّر الرقم الأول فقط:
```bash
docker run -d \
  --name trrcms-tileserver \
  -p 9000:8080 \
  -v /opt/trrcms/tiles:/data \
  --restart always \
  maptiler/tileserv-gl
```
ثم عدّل البورت في ملف `.env` على أجهزة الديسكتوب (موضح في القسم 5).

### 2.5 أين يرتبط بالتطبيق؟

**من جهتنا جاهز.** تطبيق الديسكتوب يقرأ عنوان سيرفر الخرائط من سطر واحد في ملف `.env`:

```env
TILE_SERVER_URL=http://<SERVER_IP>:5000
```

لا يحتاج أي تعديل على الكود. فقط تعبئة عنوان السيرفر.

---

## 3. بناء GeoServer — اختياري (لربط QGIS)

GeoServer مطلوب فقط إذا كانت الإدارة تريد:
- فتح بيانات المباني والمطالبات في QGIS كطبقات جغرافية
- تحليل مكاني متقدم عبر QGIS
- عرض طبقات بيانات حية (WMS) فوق الخريطة في تطبيق الديسكتوب

GeoServer يقرأ من نفس قاعدة البيانات (PostGIS) ويكشف البيانات عبر بروتوكولات WMS/WFS.

### 3.1 تشغيل GeoServer كحاوية Docker

```bash
docker run -d \
  --name trrcms-geoserver \
  -p 8085:8080 \
  -e GEOSERVER_ADMIN_USER=admin \
  -e GEOSERVER_ADMIN_PASSWORD=<GEOSERVER_PASSWORD> \
  -v geoserver_data:/opt/geoserver/data_dir \
  --restart always \
  kartoza/geoserver:2.24.1
```

### 3.2 التحقق من عمل GeoServer

افتح في المتصفح:
```
http://<SERVER_IP>:8085/geoserver/web
```
سجل الدخول بـ admin / `<GEOSERVER_PASSWORD>`.

### 3.3 ربط GeoServer بقاعدة البيانات

بعد التشغيل، يجب ربط GeoServer بقاعدة PostGIS يدوياً من واجهة الإدارة:

**إنشاء Workspace:**
1. **Workspaces** > **Add new workspace**
2. Name: `trrcms`
3. Namespace URI: `http://trrcms.unhabitat.org`
4. تفعيل: **Default Workspace** > حفظ

**إنشاء PostGIS Store:**
1. **Stores** > **Add new Store** > **PostGIS**
2. Workspace: `trrcms`
3. Data Source Name: `trrcms_postgis`
4. Connection Parameters:
   - host: `<SERVER_IP>` (أو اسم حاوية Docker إذا على نفس الشبكة)
   - port: `5432`
   - database: `trrcms`
   - schema: `public`
   - user: `trrcms_user`
   - passwd: `<DB_PASSWORD>`
5. حفظ

**نشر الطبقات:**
1. **Layers** > **Add a new layer**
2. اختيار store: `trrcms:trrcms_postgis`
3. نشر الجداول: `buildings`, `persons`, `claims`
4. لكل طبقة: اضغط **Compute from data** ثم **Compute from native bounds** > حفظ

**التحقق:**
```
WMS: http://<SERVER_IP>:8085/geoserver/trrcms/wms?service=WMS&request=GetCapabilities
WFS: http://<SERVER_IP>:8085/geoserver/trrcms/wfs?service=WFS&request=GetCapabilities
```

### 3.4 أين يرتبط بالتطبيق؟

**من جهتنا جاهز.** تطبيق الديسكتوب يحتوي على كود جاهز لعرض طبقات WMS من GeoServer.
التفعيل يتم بثلاثة أسطر في ملف `.env`:

```env
GEOSERVER_URL=http://<SERVER_IP>:8085/geoserver
GEOSERVER_WORKSPACE=trrcms
GEOSERVER_ENABLED=true
```

عند التفعيل، تظهر طبقة إضافية على الخريطة يمكن للمستخدم تشغيلها/إيقافها.
عند عدم التفعيل (الوضع الافتراضي)، لا يتغير شيء في التطبيق.

---

## 4. ربط QGIS بالنظام (مسؤولية العميل)

إذا تم بناء GeoServer (القسم 3)، يمكن للإدارة ربط QGIS بثلاث طرق:

### 4.1 عبر WFS (قراءة وكتابة)

1. QGIS > **Layer** > **Add Layer** > **Add WFS Layer**
2. **New**:
   - Name: `TRRCMS GeoServer`
   - URL: `http://<SERVER_IP>:8085/geoserver/trrcms/wfs`
   - Version: `2.0.0`
   - Username/Password: بيانات دخول GeoServer
3. **Connect** > اختر الطبقات > **Add**

WFS يسمح بالعرض والاستعلام والتعديل والحفظ في قاعدة البيانات.

### 4.2 عبر WMS (عرض فقط)

1. QGIS > **Layer** > **Add Layer** > **Add WMS/WMTS Layer**
2. **New**:
   - Name: `TRRCMS Map`
   - URL: `http://<SERVER_IP>:8085/geoserver/trrcms/wms`
3. اتصل واختر الطبقات

WMS يعرض صور خرائط مرسومة (أسرع لعرض بيانات كبيرة).

### 4.3 اتصال مباشر بـ PostGIS (متقدم)

1. QGIS > **Layer** > **Add Layer** > **Add PostGIS Layers**
2. **New**:
   - Host: `<SERVER_IP>`
   - Port: `5432`
   - Database: `trrcms`
   - Username: `trrcms_user`
   - Password: `<DB_PASSWORD>`
3. اتصل واختر الجداول ذات الإحداثيات

الاتصال المباشر يتيح استعلامات مكانية كاملة وتحليل متقدم بدون GeoServer.

---

## 5. إعداد تطبيق الديسكتوب (على كل جهاز موظف)

ملف `.env` في مجلد التطبيق هو المكان الوحيد الذي يُعدّل فيه كل الاتصالات:

```env
# ===== اتصال Backend API =====
API_BASE_URL=http://<SERVER_IP>:8080/api
API_USERNAME=admin
API_PASSWORD=<API_PASSWORD>

# ===== سيرفر الخرائط =====
TILE_SERVER_URL=http://<SERVER_IP>:5000
USE_DOCKER_TILES=true

# ===== المنطقة الجغرافية =====
MAP_CENTER_LAT=36.2021
MAP_CENTER_LNG=37.1343
MAP_DEFAULT_ZOOM=14
MAP_MIN_ZOOM=10
MAP_MAX_ZOOM=18
MAP_BOUNDS_MIN_LAT=35.5
MAP_BOUNDS_MAX_LAT=37.0
MAP_BOUNDS_MIN_LNG=36.5
MAP_BOUNDS_MAX_LNG=38.0

# ===== GeoServer (اختياري) =====
GEOSERVER_URL=http://<SERVER_IP>:8085/geoserver
GEOSERVER_WORKSPACE=trrcms
GEOSERVER_ENABLED=false
```

استبدل `<SERVER_IP>` بعنوان IP الفعلي للسيرفر.

**لتغيير المنطقة الجغرافية:** عدّل قيم `MAP_*` لتطابق المنطقة الجديدة، مع التأكد أن ملف MBTiles يغطي نفس المنطقة.

---

## 6. ملخص ما هو جاهز وما هو مطلوب

### من جهتنا (جاهز):

| الميزة | الحالة | التفاصيل |
|--------|--------|----------|
| خريطة تفاعلية في التطبيق | جاهز | Leaflet.js مع تجميع ذكي وأداء محسّن |
| ربط سيرفر خرائط خارجي | جاهز | يقرأ العنوان من `.env` — سطر واحد |
| قاعدة بيانات جغرافية (PostGIS) | جاهز | 20+ دالة مكانية، فهارس، GeoJSON |
| إحداثيات قابلة للتعديل | جاهز | كل الإحداثيات تُقرأ من `.env` |
| دعم GeoServer (WMS) | جاهز | يُفعّل بثلاثة أسطر في `.env` |
| طبقة WMS على الخريطة | جاهز | تظهر كطبقة اختيارية عند التفعيل |

### من جهة العميل (مطلوب):

| المتطلب | التفاصيل |
|---------|----------|
| سيرفر | جهاز واحد يدعم Docker — Linux أو Windows Server |
| المواصفات | 4 أنوية، 8 GB RAM، 50 GB+ تخزين |
| شبكة داخلية | تربط أجهزة الموظفين بالسيرفر |
| Docker | Docker Engine + Docker Compose منصّب |
| فتح بورتات | 8080 (API)، 5000 (خرائط)، 5432 (قاعدة بيانات)، 8085 (GeoServer اختياري) |
| QGIS | تنصيب على أجهزة المحللين (إذا مطلوب) |

---

## 7. Docker Compose — تشغيل كل الخدمات معاً

إذا أراد العميل تشغيل كل شيء بأمر واحد، هذا ملف `docker-compose.yml`:

```yaml
version: '3.8'

services:
  postgis:
    image: postgis/postgis:15-3.3
    container_name: trrcms-db
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: trrcms
      POSTGRES_USER: trrcms_user
      POSTGRES_PASSWORD: <SECURE_PASSWORD>
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: always

  backend:
    image: trrcms-backend:latest
    container_name: trrcms-api
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: postgresql://trrcms_user:<SECURE_PASSWORD>@postgis:5432/trrcms
    depends_on:
      - postgis
    restart: always

  tileserver:
    image: maptiler/tileserv-gl
    container_name: trrcms-tileserver
    ports:
      - "5000:8080"
    volumes:
      - ./tiles:/data
    restart: always

  # اختياري — فقط إذا مطلوب ربط QGIS
  geoserver:
    image: kartoza/geoserver:2.24.1
    container_name: trrcms-geoserver
    ports:
      - "8085:8080"
    environment:
      GEOSERVER_ADMIN_USER: admin
      GEOSERVER_ADMIN_PASSWORD: <GEOSERVER_PASSWORD>
    volumes:
      - geoserver_data:/opt/geoserver/data_dir
    depends_on:
      - postgis
    restart: always

volumes:
  pgdata:
  geoserver_data:
```

```bash
docker-compose up -d
docker ps
```

---

## 8. استكشاف الأخطاء

| المشكلة | التحقق |
|---------|--------|
| الخريطة فارغة | هل TileServer يعمل؟ افتح `http://<SERVER_IP>:5000` |
| | هل `TILE_SERVER_URL` صحيح في `.env`؟ |
| | هل MBTiles يغطي المنطقة المحددة في `MAP_BOUNDS`؟ |
| لا يتصل بالـ API | هل Backend يعمل؟ `http://<SERVER_IP>:8080/api/health` |
| | هل الجدار الناري يسمح ببورت 8080؟ |
| QGIS لا يتصل | هل GeoServer يعمل؟ `http://<SERVER_IP>:8085/geoserver/web` |
| | هل الطبقات منشورة؟ (القسم 3.3) |
| منطقة خاطئة على الخريطة | `MAP_CENTER_LAT/LNG` لا يتطابق مع تغطية MBTiles |
