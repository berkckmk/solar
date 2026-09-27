PROJE TESLİM GÖREVİ
===================

Bu görevin sonunda bana açıklama veya yalnızca kod parçaları verme.

ÇALIŞAN, PAKETLENMİŞ, VS CODE'DA DOĞRUDAN AÇILABİLEN BİR ZIP PROJESİ TESLİM ET.

Proje adı:

solar_system_time_journey

Ben ZIP'i açtıktan sonra coder modele mümkün olduğunca yalnızca:

"Final videoyu üret ve render al."

demek istiyorum.

Dolayısıyla:

- astronomik araştırma
- matematik
- orbital hesaplama
- gezegen verileri
- sahne tasarımı
- materyaller
- planet görünüşleri
- Sun shader
- trail sistemi
- kamera
- UI
- storyboard
- timeline
- presetler
- render pipeline
- verification

bu görev sırasında hazırlanmış olmalı.

==================================================
1. ANA KONSEPT
==================================================

16:9 yatay, minimum 8 dakika 30 saniyelik premium bilimsel görselleştirme videosu üretilecek.

Hedef süre:

9:00–9:30

Video şu soruyu cevaplayacak:

"1, 30 ve 365 Dünya günü geçtiğinde Güneş Sistemi'ndeki gezegenler ne kadar hareket etmiş olur?"

Üç zaman ölçeği:

1 EARTH DAY
30 EARTH DAYS
365 EARTH DAYS

Her bölümde:

Mercury
Venus
Earth
Mars
Jupiter
Saturn
Uranus
Neptune

gezegenlerinin HER BİRİNE ayrı kamera focus girişi yapılacak.

Kamera o gezegenle birlikte hareket edecek.

Focus sırasında:

- gezegen büyük ve detaylı görünür
- Güneş Sistemi bağlamı tamamen kaybolmaz
- gezegenin hareket ettiği gerçek orbital path görünür
- gezegen kendi renginde arkasında ince bir motion trail bırakır
- bilgi paneli açılır
- 1 / 30 / 365 Earth-day zaman aralığında ne kadar yol aldığı gösterilir

Video yarış, challenge veya "kim daha hızlı" içeriği değildir.

Ton:

CURIOUS
SCIENTIFIC
CALM
CINEMATIC
HYPNOTIC
EDUCATIONAL

==================================================
2. REFERANS GÖRSEL
==================================================

Bu göreve eklediğim visual catalog görseli ANA ART-DIRECTION REFERANSIDIR.

Exact geometry olarak kopyalama.

Şu görsel kombinasyonu referans alınsın:

BACKGROUND:
BG-02 Sparse Stars
+
BG-07 çok hafif Volumetric Haze

LIGHTING:
LIGHT-03 Solar Backlight
+
LIGHT-02 kontrollü Cinematic Rim

PLANETS:
PLANET-01 Realistic
+
PLANET-02 Stylized Realistic

TRAIL:
TRAIL-04 Long Exposure temel alınsın.

Ancak referanstaki kadar aşırı emissive olmasın.

CAMERA:
CAM-02 Cinematic Wide
CAM-04 Planet Follow
CAM-07 Close Flyby
CAM-10 Documentary

UI:
UI-03 Documentary
+
UI-07 Data Strip yaklaşımı

POST:
POST-01 Clean
+
POST-02 Subtle Bloom
+
POST-06 Filmic

FULL LOOK:
LOOK-A Scientific Noir
+
LOOK-C Dark Cinematic Space

ana görsel dil olsun.

LOOK-B'deki aşırı neon yoğunluğunu kullanma.

==================================================
3. GÖRSEL HEDEF
==================================================

Video sıradan bir:

"Blender'da renkli kürelerden oluşan Solar System"

gibi görünmemeli.

Hedef:

premium astronomy documentary
+
cinematic scientific visualization.

Ana görsel özellikler:

- deep black space
- kontrollü yıldız alanı
- detaylı gerçekçi/stilize gezegenler
- fiziksel olarak tutarlı Güneş ışığı
- çok ince atmosfer rimleri
- long-exposure orbital trails
- temiz kamera hareketi
- minimal bilimsel typography
- kontrollü bloom
- yüksek görüntü kalitesi

==================================================
4. ASTRONOMİK VERİ
==================================================

Gerekli gerçek astronomik verileri güvenilir resmi kaynaklardan araştır.

Öncelik:

NASA
JPL
JPL Horizons
NASA Planetary Fact Sheets

Veri kaynağını proje içinde belgele.

Her gezegen için en az:

name
mass
mean radius
semi-major axis
eccentricity
inclination
longitude of ascending node
argument of periapsis
mean anomaly / epoch state
orbital period
rotation period
mean orbital speed

saklanmalı.

Sabit ve deterministic bir epoch seç.

Örneğin J2000 veya belgelenmiş başka bir sabit epoch.

Renderlar her çalıştırmada aynı başlangıç konumlarını vermeli.

==================================================
5. ORBITAL MATEMATİK
==================================================

Basit:

theta = angular_speed * time

çember modeli kullanma.

Gezegenlerin gerçek eliptik yörüngelerini modelle.

Keplerian orbit solver oluştur.

Mean anomaly:

M(t) = M0 + n*t

n = 2π/P

Kepler equation:

M = E - e*sin(E)

E değerini Newton-Raphson veya stabil bir solver ile hesapla.

Sonra true anomaly ve 3D heliocentric position hesaplanmalı.

Inclination dahil edilsin.

Physics coordinate system ile Blender visual coordinate system AYRI olsun.

==================================================
6. 1 / 30 / 365 DAY HESAPLARI
==================================================

Her zaman aralığı için bütün gezegenlerde hesapla:

T = 1 Earth day
T = 30 Earth days
T = 365 Earth days

Her gezegen için:

START POSITION

END POSITION

ORBITAL ARC TRAVELLED

TRAVEL DISTANCE KM

AVERAGE ORBITAL SPEED

END INSTANTANEOUS SPEED

ORBIT FRACTION

ORBIT COUNT

ANGLE / ANOMALY PROGRESS

SUN DISTANCE

hesaplansın.

Özellikle "ne kadar yol kat etti?" değeri basit:

speed × time

yaklaşımıyla hesaplanmasın.

Gerçek Keplerian trajectory boyunca N adet yeterince yoğun sample al.

Örneğin:

N >= 1000
veya süreye göre adaptive sampling.

Ardışık 3D heliocentric noktaların mesafelerini toplayarak:

arc_length_km

hesapla.

==================================================
7. MULTIPLE ORBIT HANDLING
==================================================

365 Earth days içinde Mercury gibi gezegenler birden fazla tur tamamlar.

Aynı elips üzerine 4 ayrı kalın neon çizgi bindirip görüntüyü bozma.

Örneğin Mercury için sistem:

4.15 ORBITS

gösterebilir.

Visual:

full orbit guide:
çok düşük opacity

current travelled path:
parlak

önceki tamamlanmış lap'ler:
çok düşük ghost trail

veya lap counter.

Ana amaç:
bilgi anlaşılır olsun.

==================================================
8. STATIC ORBIT RING POLİTİKASI
==================================================

Wide Solar System görüntülerinde sürekli sekiz tane parlak orbit circle gösterme.

Bu görüntüyü şemaya çeviriyor.

Normal durumda:

STATIC ORBIT RINGS = OFF

Ancak bir gezegene focus girildiğinde:

o gezegenin tam orbital ellipse'i

çok ince,
çok düşük opacity,
scientific guide

olarak görünür olabilir.

Örneğin:

opacity %5–10.

Gezegenin gerçekten kat ettiği yol:

kendi rengiyle daha parlak trail olarak görünür.

Focus bittiğinde guide tekrar fade-out olur.

==================================================
9. PLANET TRAIL COLORS
==================================================

Her gezegen kendine ait ama kontrollü bir trail rengine sahip olsun.

Önerilen palet:

Mercury:
silver / cool white

Venus:
warm pale gold

Earth:
azure / cyan-blue

Mars:
rust orange / red-orange

Jupiter:
cream / amber

Saturn:
pale gold

Uranus:
aqua / pale cyan

Neptune:
cobalt / deep electric blue

Renkler birbirinden seçilebilir olsun.

Ancak:

RAINBOW NEON

görünümü oluşturma.

TRAIL STYLE:

thin bright core
+
soft outer glow
+
long exposure feeling

TRAIL tamamen neon tube gibi görünmemeli.

==================================================
10. GEZEGENLER İSİMSİZ DE TANINMALI
==================================================

Planet name UI'da bulunabilir.

Ancak gezegen ekrana geldiğinde isim görünmeden de ne olduğu anlaşılabilecek kadar karakteristik olmalı.

MERCURY:
gray rocky
subtle crater variation

VENUS:
cream/gold dense cloud atmosphere

EARTH:
blue ocean
continents
white cloud layer
thin atmosphere

MARS:
rust-red
dark surface variation

JUPITER:
clear cloud bands
Great Red Spot benzeri karakteristik feature

SATURN:
high-quality multi-band rings
ring transparency
ring shadows

URANUS:
pale cyan
subtle atmosphere

NEPTUNE:
deep blue
subtle cloud detail

==================================================
11. TEXTURES / ASSETS
==================================================

Görsel kaliteyi yükseltmek için uygun olduğunda resmi NASA/JPL kaynaklı kullanılabilir/public-domain planet textures araştır ve kullan.

Kullanılan her harici asset için:

SOURCE
LICENSE / USAGE STATUS
FILE

bilgisini:

THIRD_PARTY_ASSETS.md

içinde yaz.

NASA logosu veya marka öğeleri kullanma.

Uygun texture bulunamazsa procedural Blender material oluştur.

Proje internetsiz render edilebilmeli.

Gerekli assetleri ZIP içine koy.

==================================================
12. SUN REDESIGN
==================================================

Güneş düz sarı emissive ball OLMAYACAK.

Sun shader en az:

CORE
SURFACE
LIMB
CORONA

katmanlarından oluşsun.

Surface:

procedural granulation
subtle turbulent/cellular structure
warm yellow-orange variation

Center:
warm white-yellow

Limb:
bright but detailed

Corona:
controlled soft glow

Bloom yüzey detayını öldürmemeli.

No:
flat yellow sphere
fantasy fireball
overexposed white blob.

Güneş aynı zamanda gezegenlerin ana fiziksel ışık yönünü belirlemeli.

==================================================
13. VIDEO STRUCTURE
==================================================

VIDEO:

16:9
target ~9:10
minimum 8:30

3 ACT kullanılacak.

--------------------------------------------------
OPENING
0:00 – ~0:25
--------------------------------------------------

Wide cinematic Solar System.

Camera yavaşça sisteme yaklaşır.

Title:

THE SOLAR SYSTEM THROUGH EARTH TIME

Subtitle:

1 DAY • 30 DAYS • 365 DAYS

Question:

How far does each world travel while Earth’s clock keeps ticking?

--------------------------------------------------
ACT 1
1 EARTH DAY
~0:25 – 2:55
--------------------------------------------------

Chapter opener:

1 EARTH DAY
24 HOURS

Soru:

How much does the Solar System change in one day?

Sonra sırasıyla:

Mercury
Venus
Earth
Mars
Jupiter
Saturn
Uranus
Neptune

Her biri yaklaşık:

15–17 seconds.

--------------------------------------------------
ACT 2
30 EARTH DAYS
~2:55 – 5:45
--------------------------------------------------

Chapter:

30 EARTH DAYS

Soru:

Now how much orbital motion becomes visible?

Tekrar sekiz gezegene focus.

Her biri:
16–18 sec.

--------------------------------------------------
ACT 3
365 EARTH DAYS
~5:45 – 8:50
--------------------------------------------------

Chapter:

365 EARTH DAYS
1 EARTH YEAR

Soru:

How different does the Solar System look after one full Earth year?

Her gezegene:
18–20 sec.

Bu bölüm final payoff bölümü.

--------------------------------------------------
OUTRO
~8:50 – 9:15
--------------------------------------------------

Wide Solar System.

Bütün gezegenlerin current positions görünür.

Trails kontrollü şekilde mevcut.

Final text:

ONE EARTH YEAR LATER

altında:

Every planet has moved on a different clock.

==================================================
14. HER PLANET FOCUS SHOT
==================================================

Her gezegen focus segmenti aynı şekilde monoton olmamalı ama ortak dil taşımalı.

Her focus yaklaşık şu akışı kullansın:

A:
WIDE → gezegene doğru yaklaş

B:
planet follow

C:
bilgi paneli açılır

D:
gezegenle birlikte hareket

E:
traveled orbital segment belirginleşir

F:
kısa result hold

G:
camera pull-away / transition

==================================================
15. PLANET FOLLOW CAMERA
==================================================

Bu projenin en önemli görsel fonksiyonlarından biri.

Kamera gezegeni sadece merkezden takip etmesin.

Composition:

planet yaklaşık rule-of-thirds bölgesinde.

Frame'in başka kısmında mümkün olduğunda:

Sun
trail
orbit context

bulunsun.

Camera:

smooth spline motion.

No:
shake
random rotation
fast zoom
aggressive cuts.

Camera hareketleri:

slow dolly
gentle orbit
planet tracking
subtle parallax.

Planet takip edilirken arkasındaki orbital trail çok net okunmalı.

==================================================
16. CAMERA PRESETS
==================================================

Hazır reusable presetler oluştur:

CAM_SOLAR_WIDE

CAM_PLANET_APPROACH

CAM_PLANET_FOLLOW

CAM_PLANET_SIDE_FOLLOW

CAM_PLANET_3Q_FOLLOW

CAM_PLANET_TRAIL_REVEAL

CAM_PLANET_PULLBACK

CAM_DOCUMENTARY_CLOSE

==================================================
17. DATA PANEL
==================================================

Focus sırasında minimal bilgi paneli göster.

Yerleşim:

planet hangi taraftaysa
UI karşı tarafta.

Planet ile çakışmasın.

Örnek:

EARTH

ELAPSED
365 EARTH DAYS

ORBITAL SPEED
29.8 km/s

DISTANCE TRAVELLED
xxx million km

ORBIT COMPLETED
~100%

ORBIT COUNT
1.00×

DISTANCE FROM SUN
x.xx AU

Çok fazla veri aynı anda gösterme.

Maximum 4 ana metric aynı anda.

Bilgiler staggered fade ile gelebilir.

==================================================
18. TIME-SPECIFIC METRIC PRIORITY
==================================================

1 EARTH DAY:

öncelik:
distance travelled
orbital speed
orbit percentage

30 EARTH DAYS:

öncelik:
distance travelled
orbit percentage
orbital speed

365 EARTH DAYS:

öncelik:
orbits completed
distance travelled
final orbital position
average orbital speed

==================================================
19. COMPARISON PAYOFF
==================================================

Her ACT sonunda kısa comparison shot yap.

Örneğin:

AFTER 1 EARTH DAY

ve sekiz gezegenin:
orbital progress'i

çok sade data bars veya orbit fraction indicator ile gösterilebilir.

30 days sonunda:

inner planets belirgin ilerledi
outer planets az ilerledi

görsel olarak netleşsin.

365 days sonunda:

Mercury > multiple orbits
Venus > more than one
Earth = nearly one
Mars ~ partial
Jupiter/Saturn/Uranus/Neptune = small fraction

farkı tek karede anlaşılmalı.

==================================================
20. UI STYLE
==================================================

Attached visual catalog:

UI-03 Documentary
+
UI-07 Data Strip

referans.

Style:

clean
white
thin
minimal
scientific

accent:
planet-specific color.

NO:
large HUD panels
thick sci-fi borders
gaming bars
cyberpunk UI.

==================================================
21. AUDIO
==================================================

Copyrighted music kullanma.

Video sessiz de render edilebilir ancak audio system hazır olsun.

İdeal olarak:

çok düşük seviyede:
deep-space tonal ambience

Transition:
subtle soft whoosh

Planet focus:
çok hafif tonal signature

No:
arcade sounds
dramatic trailer booms
constant loud music.

Audio finalden ayrı kapatılabilir config ile kontrol edilsin:

ENABLE_AUDIO = true/false

==================================================
22. RENDER QUALITY
==================================================

Uzun video olduğu için performans/kalite dengesi kur.

Recommended production default:

2560x1440
30 FPS
16:9

Optional:
3840x2160 30 FPS

Preview:
960x540 veya 1280x720

Blender:
EEVEE Next high-quality production default.

Cycles:
yalnız lookdev hero still / optional.

Color:
AgX.

Subtle motion blur.

Controlled bloom/glare.

Render doğrudan tek MP4'e yapılmasın.

Önce:

PNG image sequence
veya uygun güvenli frame sequence

render.

Sonra FFmpeg ile encode.

Böylece render yarıda kesilirse tekrar sıfırdan başlamasın.

==================================================
23. FINAL ENCODE
==================================================

FFmpeg script oluştur.

Final:

H.264 high quality
AAC audio

ve ayrıca optional:

H.265 master.

Output:

output/final/
solar_system_1_30_365_days_1440p.mp4

==================================================
24. PROJECT STRUCTURE
==================================================

Teslim ZIP yaklaşık şu yapıya sahip olsun:

solar_system_time_journey/

README_FIRST.md

PROJECT_STATUS.md
STORYBOARD.md
VISUAL_STYLE.md
SCIENCE_NOTES.md
THIRD_PARTY_ASSETS.md

requirements.txt

config.py
generate.py

solar/
    constants.py
    planet_data.py
    kepler.py
    orbital_state.py
    metrics.py
    validation.py

scene/
    solar_scene.py
    sun.py
    planets.py
    trails.py
    stars.py
    lighting.py

camera/
    director.py
    presets.py

ui/
    overlays.py
    data_panel.py
    chapter_titles.py

timeline/
    longform.py
    chapters.py
    transitions.py

render/
    preview.py
    final.py
    encode.py

assets/
    textures/
    fonts/
    audio/

data/
    planets.json
    metrics_1_30_365.csv

output/

render_preview_macos.command
render_final_macos.command

render_preview_windows.bat
render_final_windows.bat

==================================================
25. COMMANDS
==================================================

Mac:

./render_preview_macos.command

ve:

./render_final_macos.command

çalışmalı.

Coder modele mümkün olduğunca yalnız:

"Run final render."

demek yeterli olsun.

==================================================
26. PRECOMPUTE
==================================================

Blender render sırasında astronomik matematiği tekrar tekrar çözme.

Önceden:

1
30
365

day için bütün orbital state/metrics precompute et.

Cache:

data/cache/

altında tutulabilir.

==================================================
27. AUTOMATIC VALIDATION
==================================================

Math validation script yaz.

Kontrol:

- no NaN
- orbit positions finite
- Earth ~1 orbit / year
- Mercury multiple orbit result plausible
- Venus >1 orbit / year
- outer planets partial orbit
- calculated arc length positive
- visual coordinates valid

Hardcoded metric yazma.

Hepsi dataset + solver üzerinden hesaplanmalı.

==================================================
28. LOOKDEV BEFORE FULL PROJECT DELIVERY
==================================================

Full video render etmek zorunda değilsin.

Ama proje tesliminden önce minimum şu stills/preview'ları üret ve kontrol et:

01_solar_wide.png
02_mercury_follow.png
03_earth_follow.png
04_jupiter_follow.png
05_saturn_follow.png
06_year_comparison.png

Ayrıca yaklaşık 20–30 sn düşük çözünürlüklü proof video oluştur:

preview_visual_proof.mp4

Bu preview:

wide solar shot
→ Earth focus
→ Jupiter focus
→ 365-day comparison

göstermeli.

==================================================
29. QUALITY GATE
==================================================

ZIP'i teslim etmeden önce kontrol et:

[ ] Sun artık düz sarı top değil

[ ] Mercury, Venus, Earth, Mars, Jupiter, Saturn, Uranus, Neptune isim olmadan tanınabilecek kadar farklı

[ ] trails ince ve kontrollü

[ ] her planet trail kendi renginde

[ ] focus planet path rahat okunuyor

[ ] static bright orbit rings yok

[ ] focus sırasında subtle orbit guide kullanılabiliyor

[ ] kamera gerçekten gezegenle hareket ediyor

[ ] camera motion smooth

[ ] bilgi paneli gezegeni kapatmıyor

[ ] 1-day data doğru

[ ] 30-day data doğru

[ ] 365-day data doğru

[ ] travelled distance gerçek trajectory üzerinden hesaplandı

[ ] multiple orbits doğru ele alındı

[ ] 16:9 composition doğru

[ ] final video timeline >= 8:30

[ ] render scripts çalışıyor

[ ] proje VS Code'da doğrudan açılabilir

[ ] external dependencies README'de açık

==================================================
30. ÇOK ÖNEMLİ: WORK'ÜN ROLÜ
==================================================

Bu görev sonunda bana:

"Coder şunları yapmalı..."

şeklinde plan VERME.

BUNLARI SEN YAP.

Ben coder modele mimari kurdurmak istemiyorum.

WORK ŞUNLARI BİTİRMELİ:

- araştırma
- planetary dataset
- mathematics
- calculations
- camera system
- materials
- shaders
- planet appearance
- Sun shader
- trail system
- UI
- timeline
- storyboard
- render scripts
- project structure
- validation
- documentation

Coder'ın görevi mümkün olduğunca sadece:

FINAL VIDEO RENDER

olmalı.

==================================================
31. TESLİM
==================================================

Son teslim:

solar_system_time_journey.zip

ZIP'i oluştur.

Ayrıca bana şu kısa raporu ver:

- ZIP path
- tested commands
- calculated video duration
- chosen epoch
- astronomical sources
- render engine
- final default resolution
- any remaining limitation

ZIP gerçekten oluşturulmadan görevi tamamlandı sayma.