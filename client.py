import requests

URL = "http://127.0.0.1:5000/api/masuratori"
URL_EXT = "http://127.0.0.1:5000/api/extern"

def test_api():
    print("=" * 50)
    print("   TEST API — SISTEM ILUMINAT PUBLIC IAȘI")
    print("=" * 50)

   
    print("\n[A] GET — API Extern 1: Sunrise-Sunset")
    r = requests.get(f"{URL_EXT}/soare")
    print("Status:", r.status_code)
    print("Raspuns:", r.json())

    print("\n[B] GET — API Extern 2: Open-Meteo (Vreme)")
    r = requests.get(f"{URL_EXT}/vreme")
    print("Status:", r.status_code)
    print("Raspuns:", r.json())

   
    print("\n[1] POST — Adaugare masuratore")
    r = requests.post(URL, json={
        "senzor": "Stalp_Test_01",
        "valoare": 80,
        "status": "Activ"
    })
    print("Status:", r.status_code)
    print("Raspuns:", r.json())
    if r.status_code != 201:
        print("Eroare la POST!")
        return
    id_nou = r.json()['id']

    print("\n[2] GET ALL — Toate masuratorile")
    r = requests.get(URL)
    print("Status:", r.status_code)
    print(f"Numar inregistrari: {len(r.json())}")

    print("\n[3] GET ONE — Masurarea cu id", id_nou)
    r = requests.get(f"{URL}/{id_nou}")
    print("Status:", r.status_code)
    print("Date:", r.json())

    print("\n[4] PUT — Actualizare")
    r = requests.put(f"{URL}/{id_nou}", json={
        "valoare": 120,
        "status": "Mentenanta"
    })
    print("Status:", r.status_code)
    print("Raspuns:", r.json())

    print("\n[5] DELETE — Stergere")
    r = requests.delete(f"{URL}/{id_nou}")
    print("Status:", r.status_code)
    print("Raspuns:", r.json())

    print("\n[6] GET dupa stergere — trebuie 404")
    r = requests.get(f"{URL}/{id_nou}")
    print("Status:", r.status_code, "✅" if r.status_code == 404 else "❌")

    print("\n" + "=" * 50)
    print("   TEST FINALIZAT")
    print("=" * 50)

if __name__ == "__main__":
    test_api()
