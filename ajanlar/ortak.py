"""Ortak yardimcilar."""
import json
import os
import re
import time

import requests

GEMINI_MODELLERI = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash"]
GROQ_MODELI = "llama-3.3-70b-versatile"


def _gemini(sistem, kullanici):
    anahtar = os.environ.get("GEMINI_API_KEY", "").strip()
    if not anahtar:
        return None
    for model in GEMINI_MODELLERI:
        for deneme in range(3):
            try:
                cevap = requests.post(
                    "https://generativelanguage.googleapis.com/v1beta/models/"
                    + model
                    + ":generateContent",
                    params={"key": anahtar},
                    json={
                        "systemInstruction": {"parts": [{"text": sistem}]},
                        "contents": [{"parts": [{"text": kullanici}]}],
                        "generationConfig": {
                            "temperature": 0.9,
                            "responseMimeType": "application/json",
                        },
                    },
                    timeout=120,
                )
            except requests.RequestException as hata:
                print("gemini ag hatasi:", hata)
                time.sleep(5)
                continue
            if cevap.status_code == 200:
                try:
                    return cevap.json()["candidates"][0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError):
                    continue
            if cevap.status_code in (429, 500, 503):
                print("gemini", model, cevap.status_code, "bekleniyor")
                time.sleep(10 * (deneme + 1))
                continue
            print("gemini", model, cevap.status_code, cevap.text[:200])
            break
    return None


def _groq(sistem, kullanici):
    anahtar = os.environ.get("GROQ_API_KEY", "").strip()
    if not anahtar:
        return None
    try:
        cevap = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + anahtar},
            json={
                "model": GROQ_MODELI,
                "temperature": 0.9,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": sistem},
                    {"role": "user", "content": kullanici},
                ],
            },
            timeout=120,
        )
        if cevap.status_code == 200:
            return cevap.json()["choices"][0]["message"]["content"]
        print("groq", cevap.status_code, cevap.text[:200])
    except requests.RequestException as hata:
        print("groq ag hatasi:", hata)
    return None


def llm(sistem, kullanici):
    for saglayici in (_gemini, _groq):
        metin = saglayici(sistem, kullanici)
        if metin:
            return metin
    raise SystemExit("HATA: hicbir model cevap vermedi. Anahtarlari kontrol et.")


def json_ayikla(metin):
    metin = re.sub(r"^```(?:json)?|```$", "", metin.strip(), flags=re.M).strip()
    for bas, son in (("[", "]"), ("{", "}")):
        if bas in metin and son in metin:
            parca = metin[metin.index(bas): metin.rindex(son) + 1]
            try:
                return json.loads(parca)
            except json.JSONDecodeError:
                continue
    raise ValueError("JSON cozulemedi: " + metin[:300])


def gecmis_oku():
    try:
        with open("gecmis.json", encoding="utf-8") as dosya:
            return json.load(dosya)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"konular": []}


def gecmis_yaz(kayit):
    kayit["konular"] = kayit.get("konular", [])[-200:]
    with open("gecmis.json", "w", encoding="utf-8") as dosya:
        json.dump(kayit, dosya, ensure_ascii=False, indent=2)


def ozet_yaz(markdown):
    yol = os.environ.get("GITHUB_STEP_SUMMARY")
    if yol:
        with open(yol, "a", encoding="utf-8") as dosya:
            dosya.write(markdown + "\n")
    print(markdown)
