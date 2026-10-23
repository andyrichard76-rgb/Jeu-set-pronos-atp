# Étape 1 : récupère le tableau des scores ATP et en garde un échantillon pour vérifier sa structure.
import json, urllib.request
URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard"
req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
d = json.loads(raw)
json.dump(d, open("tools/espn-sample.json", "w"), ensure_ascii=False, indent=1)
print("ok", len(raw))
