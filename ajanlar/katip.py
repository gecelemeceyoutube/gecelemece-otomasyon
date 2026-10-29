"""Katip ajani: arastirma + senaryo."""
import datetime
import json
import os
import re

import requests

from ortak import json_ayikla, llm, ozet_yaz

KONU = os.environ.get("KONU", "").strip()
BASLIKLAR = {"User-Agent": "GecelemeceAjan/1.0 (egitim amacli otomasyon)"}
VIKI = "https://tr.wikipedia.org/w/api.php"

SISTEM = """Sen Gecelemece kanalinin arastirmaci senaristisin.
Kanal Turkce; tarih, Istanbul, Osmanli, unutulmus gelenekler ve gece temasi.
Ton: sakin hikaye anlaticisi, gece atmosferi, kisa cumleler. Yapay zeka klichleri yasak
("bir yolculuga cikalim", "unutmayin", "sizleri bekliyor" gibi).

Gorev: verilen konu ve arastirma metniyle 3-5 dakikalik senaryo yaz.

KURALLAR:
1. Sadece verilen arastirma metnindeki bilgileri kullan. Metinde olmayan tarih, sayi, isim uydurma.
2. Metinde olmayan ama gerekli bir detay varsa sonuna "(dogrulanmali)" yaz.
3. Terimleri metindeki yazimla kullan. Yazim farkliysa metne uy.
4. Yapi: ilk 15 saniye merak kancasi, sonra baglam, orta bolumde somut olay ve detay,
   son 20 saniyede bugune baglayan kapanis ve sonraki video cagrisi.
5. Uzunluk 500-700 kelime.
6. Abartma, "inanilmaz", "sok edici" gibi tiklamaya oynayan ifadeler kullanma.

Cikti SADECE JSON:
{
  "baslik_final": "en fazla 60 karakter, birincil anahtar kelime basta, iki nokta kullanma",
  "senaryo": "tam metin, paragraflara bolunmus",
  "bolumler": [{"baslangic_sn": 0, "baslik": "..."}],
  "kaynaklar": ["kullanilan kaynak adi"],
  "gorsel_notlari": ["sahne icin gorsel tarifi"],
  "guven_notu": "dogrulanmasi gereken noktalar"
}
"""


def viki_ara(sorgu, adet=3):
    try:
        cevap = requests.get(
            VIKI,
            params={
                "action": "query",
                "list": "search",
                "srsearch": sorgu,
                "format": "json",
                "srlimit": adet,
            },
            headers=BASLIKLAR,
            timeout=30,
        )
        return [k["title"] for k in cevap.json()["query"]["search"]]
    except Exception as hata:
        print("viki arama hatasi:", hata)
        return []


def viki_metin(baslik):
    try:
        cevap = requests.get(
            VIKI,
            params={
                "action": "query",
                "prop": "extracts",
                "explaintext": "1",
                "titles": baslik,
                "format": "json",
                "redirects": "1",
            },
            headers=BASLIKLAR,
            timeout=30,
        )
        sayfalar = cevap.json()["query"]["pages"]
        for sayfa in sayfalar.values():
            metin = sayfa.get("extract", "")
            if metin:
                return sayfa.get("title", baslik), metin
    except Exception as hata:
        print("viki metin hatasi:", baslik, hata)
    return None, ""


def arastir(konu):
    parcalar, kaynaklar = [], []
    for baslik in viki_ara(konu):
        gercek, metin = viki_metin(baslik)
        if metin:
            parcalar.append("### " + gercek + "\n" + metin[:2500])
            kaynaklar.append("tr.wikipedia.org - " + gercek)
    return "\n\n".join(parcalar)[:9000], kaynaklar


def main():
    if not KONU:
        raise SystemExit("HATA: KONU bos.")

    arastirma, kaynaklar = arastir(KONU)
    if not arastirma:
        arastirma = "(Wikipedia'da dogrudan kaynak bulunamadi, dikkatli yaz ve belirsizleri isaretle.)"
    print("arastirma uzunlugu:", len(arastirma))

    kullanici = (
        "Konu: " + KONU + "\n\nArastirma metni:\n" + arastirma
    )
    veri = json_ayikla(llm(SISTEM, kullanici))
    if isinstance(veri, dict) and "fikirler" in veri:
        veri = veri["fikirler"]

    senaryo = veri.get("senaryo", "")
    kelime = len(senaryo.split())
    print("kelime sayisi:", kelime)
    if kelime < 350:
        print("UYARI: senaryo kisa, " + str(kelime) + " kelime")

    veri.setdefault("kaynaklar", [])
    for kaynak in kaynaklar:
        if kaynak not in veri["kaynaklar"]:
            veri["kaynaklar"].append(kaynak)
    veri["konu"] = KONU
    veri["tarih"] = datetime.date.today().isoformat()

    slug = re.sub(r"[^a-z0-9]+", "-", KONU.lower()).strip("-")[:50]
    os.makedirs("cikti", exist_ok=True)
    with open("cikti/senaryo-" + slug + ".json", "w", encoding="utf-8") as dosya:
        json.dump(veri, dosya, ensure_ascii=False, indent=2)

    ozet_yaz(
        "# Senaryo\n\n**Baslik:** " + veri.get("baslik_final", "-")
        + "\n\n**Kelime:** " + str(kelime)
        + "\n\n---\n\n" + senaryo
        + "\n\n---\n\n**Bolumler:**\n"
        + "\n".join(
            "- " + str(b.get("baslangic_sn")) + " sn: " + b.get("baslik", "")
            for b in veri.get("bolumler", [])
        )
        + "\n\n**Guven notu:** " + str(veri.get("guven_notu", "-"))
    )


if __name__ == "__main__":
    main()
