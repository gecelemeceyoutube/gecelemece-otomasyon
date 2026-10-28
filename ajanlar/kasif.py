"""Kasif ajani."""
import datetime
import json
import os
import re
import urllib.parse

import requests

from ortak import gecmis_oku, gecmis_yaz, json_ayikla, llm, ozet_yaz

TOHUMLAR = [
    "osmanlı tarihi",
    "istanbul tarihi",
    "tarihte gece",
    "osmanlı gelenekleri",
    "eski istanbul",
    "tarihi hikaye",
]

SISTEM = """Sen Gecelemece kanalinin fikir ajanisin.
Kanal Turkce; tarih, Istanbul, Osmanli, unutulmus gelenekler ve gece temasi uzerine.
Format 3-5 dakikalik, arastirmaya dayali, sakin anlatimli belgesel.
Gorev: verilen sinyallere bakarak yeni video fikirleri uretmek.

Kurallar:
- Cok genis konu secme. "Osmanli tarihi" kotu, "Ramazan topu" iyi.
- Her fikir tek bir somut olay, nesne, mekan veya gelenek uzerine olsun.
- Yasak listesindeki konulari tekrarlama.
- Baslik 60 karakteri gecmesin ve birincil anahtar kelime basta olsun.
- Cikti SADECE JSON dizisi olsun, aciklama yazma.

Her elemanin alanlari: baslik, anahtar_kelime, niyet, aci, skor, neden_simdi
niyet degeri: bilgi | merak | tartisma
skor: 1-10 arasi tamsayi
"""


def onerileri_topla():
    bulunan = []
    for tohum in TOHUMLAR:
        adres = (
            "https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q="
            + urllib.parse.quote(tohum)
        )
        try:
            cevap = requests.get(adres, timeout=15)
            for oneri in cevap.json()[1]:
                if oneri not in bulunan:
                    bulunan.append(oneri)
        except Exception as hata:
            print("oneri alinamadi:", tohum, hata)
    return bulunan[:40]


def trendleri_topla():
    try:
        cevap = requests.get(
            "https://trends.google.com/trending/rss?geo=TR", timeout=20
        )
        return re.findall(r"<title>(.*?)</title>", cevap.text)[:20]
    except Exception as hata:
        print("trend alinamadi:", hata)
        return []


def main():
    adet = int(os.environ.get("ADET", "10"))
    gecmis = gecmis_oku()
    yasak = [kayit["baslik"] for kayit in gecmis["konular"]]

    oneriler = onerileri_topla()
    trendler = trendleri_topla()

    kullanici = (
        "YouTube arama onerileri:\n- "
        + "\n- ".join(oneriler)
        + "\n\nGoogle Trends TR basliklari:\n- "
        + "\n- ".join(trendler)
        + "\n\nYasak listesi, tekrarlama:\n- "
        + "\n- ".join(yasak[-60:] or ["(bos)"])
        + "\n\nBana "
        + str(adet)
        + " fikir ver."
    )

    fikirler = json_ayikla(llm(SISTEM, kullanici))
    if isinstance(fikirler, dict):
        fikirler = fikirler.get("fikirler", [])
    fikirler = fikirler[:adet]

    bugun = datetime.date.today().isoformat()
    os.makedirs("cikti", exist_ok=True)
    with open("cikti/fikirler-" + bugun + ".json", "w", encoding="utf-8") as dosya:
        json.dump(fikirler, dosya, ensure_ascii=False, indent=2)

    satirlar = [
        "# Fikir listesi - " + bugun,
        "",
        "| # | Skor | Baslik | Anahtar kelime | Neden simdi |",
        "|---|---|---|---|---|",
    ]
    for sira, fikir in enumerate(fikirler, 1):
        satirlar.append(
            "| {0} | {1} | {2} | {3} | {4} |".format(
                sira,
                fikir.get("skor", "-"),
                fikir.get("baslik", "-"),
                fikir.get("anahtar_kelime", "-"),
                fikir.get("neden_simdi", "-"),
            )
        )
        gecmis["konular"].append(
            {"baslik": fikir.get("baslik", ""), "tarih": bugun, "durum": "onerildi"}
        )

    ozet_yaz("\n".join(satirlar))
    gecmis_yaz(gecmis)


if __name__ == "__main__":
    main()
