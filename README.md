# Binance Futures RSI kapanış bildirimleri

Tüm aktif **USDT, PERPETUAL, kripto** sözleşmeleri için **15 dakika, Wilder RSI(14), kapanış fiyatı**. Tam olarak `RSI > 90` veya `RSI < 15` ise her uygun mum için sinyal üretir. Art arda uygun kapanışların tümü bildirilir; 90 ve 15 dahil değildir. İşlem açmaz, Binance API anahtarı istemez.

## Kurulum

1. GitHub'da herkese açık, yeni bir depo oluştur. Bu klasörün içeriğini deponun köküne aktar. Gizli `.github/workflows/rsi.yml` dosyasının da yüklendiğini kontrol et. Klasörün kendisini bir alt klasör olarak yükleme; ZIP'i açmadan depoya yükleme.
2. Telegram'da doğrulanmış **@BotFather** hesabına `/newbot` gönderip bir bot oluştur. Aldığın token'ı kodlara veya sohbete yapıştırma. Yeni botunun sohbetini açıp `/start` gönder.
3. Bilgisayarında `python3 telegram_chat_id.py` çalıştır. Token'ı gizli giriş alanına gir; program sohbet kimliğini gösterecek. Bu yardımcı sadece bilgiyi okur, token'ı dosyaya yazmaz.
4. Depoda **Settings → Secrets and variables → Actions → New repository secret** yolundan iki secret ekle:
   - `TELEGRAM_BOT_TOKEN`: BotFather'ın verdiği token.
   - `TELEGRAM_CHAT_ID`: Programın gösterdiği kendi sohbet kimliğin.
5. **Actions → Binance RSI alerts → Run workflow** ile ilk çalıştırmayı başlat. Workflow dosyası varsayılan dalda bulunmalı. Gerekirse depo/kurum politikalarında Actions'ın depoya yazmasına izin ver; ilerleme kaydı için `contents: write` gerekir.
6. İlk koşunun yeşil tamamlandığını, `data/state.json` dosyasının oluştuğunu ve Telegram'da kurulum mesajının geldiğini doğrula. Sonraki koşular otomatik tetiklenir. İlk koşu Binance erişiminin GitHub çalıştırıcısında çalışıp çalışmadığının da gerçek testidir.

## Davranış

- Planlanan tetikleme saat başından itibaren 02, 17, 32, 47. dakikalarda. UTC cron; Türkiye'de de aynı dakika noktalarına denk gelir. Bildirimlerde Türkiye saati gösterilir.
- Açık mum hesaplamaya alınmaz. Kontrol ufku, Binance sunucu saatindeki en son kapanıştır.
- İlk çalıştırmada her çift için en fazla 499 kapanmış mumla RSI başlatılır; yalnızca en son kapanış için bildirim üretilir. Kurulum öncesindeki bütün tarih için alarm gönderilmez.
- Sonraki koşularda her çiftin kaldığı yerden tüm eksik mumlar sayfalı çekilir. RSI ortalama kazanç/kayıp değerleri korunur; her seferinde kısa geçmişten yeniden başlatılmaz.
- İlk 15 kapanışı henüz oluşmamış yeni çiftlerde RSI hesaplanana kadar beklenir. Yeni listeler her koşuda yeniden alınır. Kapsam o sırada aktif çiftlerdir; kesinti sırasında işlemden kaldırılmış çiftler için geçmiş telafisi garanti edilmez.
- Normal koşuda aynı mum tekrarlanmaz. Bildirimler en fazla 8 sinyallik mesajlar halinde gönderilir; her sinyalin çifti, RSI'ı ve kapanış saati ayrı yazılır.
- Gönderilemeyen mesajlar `data/state.json` içindeki kuyrukta bekler. Hatalı koşularda da yerel ilerleme GitHub'a kaydedilir. Bu dosyada sadece piyasa verisi/RSI durumu ve bekleyen sinyaller bulunur, token veya sohbet kimliği bulunmaz.
- Telegram mesajı kabul ettikten hemen sonra ağ/runner kesilirse veya GitHub'a kayıt başarısız olursa sonraki koşuda tekrar mesaj gelebilir. GitHub ve Telegram arasında tek bir ortak işlem olmadığından kesin “yalnızca bir kez teslim” garantisi yoktur. Mesajdaki sinyal kimliği aynı mumu ayırt eder.
- Bozuk/eksik mum dizisinde o çiftin ilerlemesi atlatılmaz, koşu hata gösterir. Binance erişim veya hız sınırı hatalarında tarama durdurulur.
- RSI'nın başlangıç geçmişi veya grafiğin kullandığı fiyat türü farklıysa grafikte küçük farklar olabilir. Karşılaştırma RSI(14), Wilder/RMA ve normal sözleşme kapanış fiyatıyla yapılmalıdır; mark fiyatı değildir. Eşik kontrolü yuvarlanmamış değerle yapılır.

## Ücretsiz kullanım ve sınırlar

Açık depoda standart `ubuntu-latest` çalıştırıcı kullanılır; ek ücretli servis veya paket gerektirmez. Kod ve piyasa verisi kaydı herkese açık olur; Secrets gizlidir. Gizli depo kullanımında ücretsiz kota sınırı farklıdır.

GitHub zamanlaması kesin saat garantisi vermez; yoğunlukta gecikebilir veya bir koşu atlanabilir. Sonraki başarılı koşu geçmişi tarar; bildirim geç ulaşabilir. Çok büyük bir bildirim birikimi birden fazla koşuda boşaltılabilir. Repo etkinliği uzun süre olmazsa (GitHub'ın belgesine göre 60 gün) zamanlama devre dışı kalabilir; otomatik kayıtlar etkinlik oluştursa da Actions durumunu kontrol et.

Binance, GitHub çalıştırıcısının IP'sine/bölgesine erişimi kısıtlayabilir (örn. HTTP 451/403). Bu durumda bu ortamda çözüm devreye alınmış sayılmaz. Ücretsiz plan tek başına erişimi garanti etmez; erişime izin verilen başka bir çalışma ortamı gerekir. Kod böyle bir kısıtlamayı aşmaya çalışmaz.

GitHub Actions başarısız koşu bildirimlerini açık tut. Telegram sessizliği, her zaman sinyal olmadığı anlamına gelmez; son başarılı koşu Actions ekranından kontrol edilebilir. `data/state.json` dosyasını silmek takibi sıfırlar. Durum commit'i için depoda varsayılan dala botun yazmasını engelleyen koruma kuralı bulunmamalıdır.

## Testler

`python3 -m unittest test_monitor -v`

Dokuz çevrimdışı test: bilinen Wilder hesap sonucu, her uygun kapanışta sinyal, açık mumun dışlanması, eşik eşitlikleri, düşüş/sabit fiyat, yetersiz geçmiş, mum boşluğu, 1.100 mumluk sayfalı telafi ve işlenmiş mumun tekrarlanmaması.

Hazırlık sırasında bu testler geçti. GitHub üzerinde canlı Binance erişimi ve gerçek Telegram teslimi henüz test edilmedi.

## Kaynaklar

- [Binance Futures piyasa verileri](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)
- [GitHub Actions zamanlama](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GitHub Actions ücretlendirme](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Telegram Bot API](https://core.telegram.org/bots/api#sendmessage)
