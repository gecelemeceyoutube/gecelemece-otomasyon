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

Her fikir su kurallara UYMAK ZORUNDA:
1. TEK bir somut cekirdek sec: bir olay, bir nesne, bir yapi, bir gelenek veya bir kisi.
   Genis konu yasak. "Osmanli tarihi" degil, "Ramazan topu".
2. Cekirdek DOGRULANABILIR olmali. Uydurma mekan + olay birlesimi yapma.
   Kotu ornek: "Cukurcuma Gece Pazari" - boyle bir pazar bilinmiyorsa yazma.
   Emin degilsen daha bilinen bir cekirdek sec.
3. Baslik en fazla 60 karakter. Birincil anahtar kelime basta. En fazla bir iki nokta.
4. anahtar_kelime: insanlarin YouTube'a gercekten yazdigi arama ifadesi olsun.
5. neden_simdi somut olsun. "ilgi cekiyor", "populer" gibi bos ifade yasak.
   Ya sinyal listesinde geciyorsa onu goster, ya mevsim bagi kur, ya guncel bir olaya bagla.
6. skor 1-10 ve dagilim gercekci olsun: en az bir fikir 4-5, en az bir fikir 9-10 almali.
7. Yasak listesindeki konulari ve ayni cekirdegi tekrar etme.

Cikti SADECE JSON dizisi. Alanlar: baslik, anahtar_kelime, niyet, aci, skor, neden_simdi, cekirdek
niyet: bilgi | merak | tartisma
cekirdek: tek cumlelik dogrulanabilir iddia
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


def temizle(fikirler, adet, yasak):
    secilen, gorulen = [], {b.lower() for b in yasak}
    for fikir in fikirler:
        baslik = str(fikir.get("baslik", "")).strip()
        if not baslik or len(baslik) > 62:
            print("atildi, baslik:", baslik)
            continue
        if baslik.lower() in gorulen:
            print("atildi, tekrar:", baslik)
            continue
        gorulen.add(baslik.lower())
        secilen.append(fikir)
    return secilen[:adet]


def main():
    adet = int(os.environ.get("ADET", "10"))
    gecmis = gecmis_oku()
    yasak = [kayit["baslik"] for kayit in gecmis["konular"]]
    bugun = datetime.date.today()

    kullanici = (
        "Bugun: " + bugun.isoformat() + "\n\n"
        "YouTube arama onerileri:\n- "
        + "\n- ".join(onerileri_topla())
        + "\n\nGoogle Trends TR basliklari:\n- "
        + "\n- ".join(trendleri_topla())
        + "\n\nYasak listesi, tekrarlama:\n- "
        + "\n- ".join(yasak[-60:] or ["(bos)"])
        + "\n\nBana tam "
        + str(adet)
        + " fikir ver."
    )

    fikirler = json_ayikla(llm(SISTEM, kullanici))
    if isinstance(fikirler, dict):
        fikirler = fikirler.get("fikirler", [])
    fikirler = temizle(fikirler, adet, yasak)

    os.makedirs("cikti", exist_ok=True)
    with open(
        "cikti/fikirler-" + bugun.isoformat() + ".json", "w", encoding="utf-8"
    ) as dosya:
        json.dump(fikirler, dosya, ensure_ascii=False, indent=2)

    satirlar = [
        "# Fikir listesi - " + bugun.isoformat(),
        "",
        "| # | Skor | Baslik | Cekirdek | Neden simdi |",
        "|---|---|---|---|---|",
    ]
    for sira, fikir in enumerate(fikirler, 1):
        satirlar.append(
            "| {0} | {1} | {2} | {3} | {4} |".format(
                sira,
                fikir.get("skor", "-"),
                fikir.get("baslik", "-"),
                fikir.get("cekirdek", "-"),
                fikir.get("neden_simdi", "-"),
            )
        )
        gecmis["konular"].append(
            {"baslik": fikir.get("baslik", ""), "tarih": bugun.isoformat(), "durum": "onerildi"}
        )

    ozet_yaz("\n".join(satirlar))
    gecmis_yaz(gecmis)


if __name__ == "__main__":
    main()
