# रील सेवर (Reel Saver)

Instagram लिंक पेस्ट करो → वीडियो (MP4), ऑडियो (MP3) या फोटो डाउनलोड करो।
Flask + yt-dlp बैकएंड, सादा HTML/CSS/JS फ्रंटएंड।

## कंप्यूटर पर चलाना
```bash
pip install -r requirements.txt
# ऑडियो (MP3) के लिए ffmpeg इंस्टॉल होना चाहिए
python server.py
# खोलो: http://localhost:8000
```

## ऑनलाइन होस्ट करना (Docker वाली कोई भी सर्विस)
1. इस फ़ोल्डर को GitHub पर डालो।
2. Render.com / Railway.app / Fly.io पर "New Web Service" बनाओ और रेपो जोड़ो।
   Docker अपने-आप `Dockerfile` से चलेगा (ffmpeg साथ में इंस्टॉल होता है)।
3. डिप्लॉय होने पर आपको लिंक मिल जाएगा। अपना डोमेन चाहिए तो सर्विस की सेटिंग में जोड़ो।

## टेस्ट चलाना
```bash
python tests/test_server.py   # बैकएंड (नकली yt-dlp से, बिना इंटरनेट)
node tests/test_frontend.js   # फ्रंटएंड लॉजिक
```

## सेटिंग्स (एनवायरनमेंट वेरिएबल)
| नाम | डिफ़ॉल्ट | मतलब |
|---|---|---|
| `RATE_LIMIT_PER_MIN` | 20 | हर IP की रिक्वेस्ट प्रति मिनट |
| `MAX_CONCURRENT_DOWNLOADS` | 3 | एक साथ कितने डाउनलोड |
| `MAX_FILE_MB` | 200 | फ़ाइल का अधिकतम साइज़ |
| `COOKIES_FILE` | cookies.txt | वैकल्पिक Instagram कुकीज़ |

हेल्थ-चेक का पाथ `/healthz` है। Render पर `render.yaml` से एक क्लिक में डिप्लॉय हो जाता है।

## ज़रूरी बातें
- Instagram अक्सर सर्वर/क्लाउड IP को रोकता है। लिंक न खुले तो अपने Instagram अकाउंट की
  `cookies.txt` (Netscape फॉर्मेट) इस फ़ोल्डर में रखो, या `COOKIES_FILE` एनवायरनमेंट वेरिएबल से पाथ दो।
  cookies.txt किसी को शेयर मत करो और GitHub पर मत डालो (`.gitignore` में पहले से है)।
- yt-dlp को समय-समय पर अपडेट करो (`pip install -U yt-dlp` और रीडिप्लॉय), क्योंकि Instagram बदलता रहता है।
- कई फोटो वाली पोस्ट में फोटो डाउनलोड अक्सर थंबनेल-साइज़ मिलती है; पूरी क्वालिटी की गारंटी नहीं।
- `RATE_LIMIT_PER_MIN` (डिफ़ॉल्ट 20) से हर IP की रिक्वेस्ट सीमित होती है।
- सिर्फ़ अपना या इजाज़त वाला कंटेंट डाउनलोड करो। Instagram की शर्तें और कॉपीराइट का ध्यान रखो।
