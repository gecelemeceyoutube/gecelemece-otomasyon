# ortak.py - ajanlarin paylastigi araclar
# Model adlari sik degisiyor, bu yuzden liste her calismada API'den cekilir.
import json
import os
import re
import time

import requests

YEDEK_GEMINI = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-flash-latest"]
YEDEK_GROQ = ["openai/gpt-oss-120b", "llama-4-scout-17b-16e-instruct", "llama-3.1-8b-instant"]

_onbellek = {"gemini": None, "groq": None}


def _gemini_modelleri(anahtar):
    sabit = os.environ.get("GEMINI_MODEL", "").strip()
    if sabit:
        return [sabit]
    if _onbellek["gemini"]:
        return _onbellek["gemini"]
    secilen = []
    try:
        cevap = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": anahtar},
            timeout=30,
        )
        if cevap.status_code == 200:
            adlar = [
                model["name"].split("/")[-1]
                for model in cevap.json().get("models", [])
                if "generateContent" in model.get("supportedGenerationMethods", [])
            ]
            gruplar = (
                [a for a in adlar if "flash" in a and "lite" not in a and "image" not in a],
                [a for a in adlar if "flash" in a and "image" not in a],
                [a for a in adlar if "pro" not in a and "image" not in a],
                adlar,
            )
            for grup in gruplar:
                if grup:
                    secilen = grup[:3]
                    break
    except requests.RequestException as hata:
        print("model listesi alinamadi:", hata)
    if not secilen:
        secilen = YEDEK_GEMINI
    _onbellek["gemini"] = secilen
    print("kullanilacak gemini modelleri:", secilen)
    return secilen


def _groq_modelleri(anahtar):
    sabit = os.environ.get("GROQ_MODEL", "").strip()
    if sabit:
        return [sabit]
    if _onbellek["groq"]:
        return _onbellek["groq"]
    secilen = []
    try:
        cevap = requests.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": "Bearer " + anahtar},
            timeout=30,
        )
        if cevap.status_code == 200:
            adlar = [
                model["id"]
                for model in cevap.json().get("data", [])
                if not any(
                    kelime in model["id"].lower()
                    for kelime in ("whisper", "tts", "guard", "embed")
                )
            ]
            tercih = [a for a in adlar if "gpt-oss" in a or "llama" in a] or adlar
            secilen = tercih[:3]
    except requests.RequestException as hata:
        print("groq model listesi alinamadi:", hata)
    if not secilen:
        secilen = YEDEK_GROQ
    _onbellek["groq"] = secilen
    print("kullanilacak groq modelleri:", secilen)
    return secilen


def _gemini(sistem, kullanici):
    anahtar = os.environ.get("GEMINI_API_KEY", "").strip()
    if not anahtar:
        return None
    for model in _gemini_modelleri(anahtar):
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
            print("gemini", model, cevap.status_code, cevap.text[:180])
            break
    return None


def _groq(sistem, kullanici):
    anahtar = os.environ.get("GROQ_API_KEY", "").strip()
    if not anahtar:
        return None
    for model in _groq_modelleri(anahtar):
        try:
            cevap = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": "Bearer " + anahtar},
                json={
                    "model": model,
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
            print("groq", model, cevap.status_code, cevap.text[:180])
        except requests.RequestException as hata:
            print("groq ag hatasi:", hata)
    return None


def llm(sistem, kullanici):
    for saglayici in (_gemini, _groq):
        metin = saglayici(sistem, kullanici)
        if metin:
            return metin
    raise SystemExit(
        "HATA: hicbir model cevap vermedi. Anahtarlari ve model listesini kontrol et."
    )


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
