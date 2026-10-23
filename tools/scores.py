"""Mise à jour automatique des scores (lancée par GitHub toutes les 10 minutes).
Source : tableau des scores ATP public d'ESPN. Ne touche qu'aux matchs déjà présents dans data.json."""
import json, re, unicodedata, urllib.request
from datetime import datetime, timezone, timedelta

URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/atp/scoreboard"

def paris_now():
    # heure de Paris (heure d'été jusqu'au dernier dimanche d'octobre, simplifié par l'offset système de la date)
    now = datetime.now(timezone.utc)
    y = now.year
    def last_sunday(month):
        d = datetime(y, month, 31 if month in (3, 10) else 30, 1, tzinfo=timezone.utc)
        while d.weekday() != 6: d -= timedelta(days=1)
        return d
    off = 2 if last_sunday(3) <= now < last_sunday(10) else 1
    return now.astimezone(timezone(timedelta(hours=off))), off

def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z\s.-]", "", s)

def pkey(n):
    w = [x for x in re.split(r"[\s.]+", norm(n).replace("-", " ")) if x]
    return (w[0][0] + " " + w[-1]) if w else ""

def lastkey(n):
    w = [x for x in re.split(r"[\s.]+", norm(n).replace("-", " ")) if x]
    return w[-1] if w else ""

def same(a, b):
    return pkey(a) == pkey(b) or (lastkey(a) == lastkey(b) and norm(a)[:1] == norm(b)[:1])


CITY = {"brussels": "bruxelles", "basel": "bale", "vienna": "vienne", "turin": "turin", "munich": "munich",
        "geneva": "geneve", "antwerp": "anvers", "stockholm": "stockholm", "tokyo": "tokyo", "beijing": "pekin",
        "shanghai": "shanghai", "london": "londres", "rome": "rome", "madrid": "madrid", "barcelona": "barcelone",
        "hamburg": "hambourg", "marseille": "marseille", "montpellier": "montpellier", "metz": "metz", "lyon": "lyon",
        "almaty": "almaty", "paris": "paris", "rotterdam": "rotterdam", "dubai": "dubai", "doha": "doha"}
ROUND_BACK = {"Final": 1, "Semifinal": 2, "Quarterfinal": 3, "Round 4": 4, "Round 3": None, "Round 2": None, "Round 1": None}

def add_new(data, comps, now, tz):
    """Ajoute les matchs du jour et du lendemain qui ne sont pas encore dans data.json (sans analyse)."""
    days = {now.strftime("%Y-%m-%d"), (now + timedelta(days=1)).strftime("%Y-%m-%d")}
    added = []
    for c in comps:
        rnd = (c.get("round") or {}).get("displayName", "")
        if "Qualif" in rnd: continue
        st = ((c.get("status") or {}).get("type") or {}).get("state")
        if st == "post": continue
        try:
            t0 = datetime.strptime(c["date"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).astimezone(tz)
        except Exception: continue
        day = t0.strftime("%Y-%m-%d")
        if day not in days: continue
        city = norm(((c.get("venue") or {}).get("fullName") or "").split(",")[0]).strip()
        city = CITY.get(city, city)
        t = next((t for t in data.get("tournois", []) if norm(t.get("nom")).replace("a", "a") == city or t.get("id", "").endswith("-" + city)), None)
        if not t: continue
        a, b = sorted(c["competitors"], key=lambda x: x.get("order", 0))
        na, nb = a["athlete"]["displayName"], b["athlete"]["displayName"]
        if any(m.get("date") == day and ((same(m["j1"], na) and same(m["j2"], nb)) or (same(m["j1"], nb) and same(m["j2"], na))) for m in data["matchs"]):
            continue
        tours = ((t.get("tableau") or {}).get("tours")) or ["1er tour", "8e de finale", "Quart de finale", "Demi-finale", "Finale"]
        back = ROUND_BACK.get(rnd)
        tour = tours[-back] if back and back <= len(tours) else rnd
        def info(n):
            for r in ((t.get("tableau") or {}).get("matchs")) or []:
                for bm in r:
                    for s in ("j1", "j2"):
                        p = bm.get(s) or {}
                        if p.get("nom") and same(p["nom"], n): return p.get("pays", ""), p.get("tds", "")
            return "", ""
        def flag(x):
            h = ((x.get("athlete") or {}).get("flag") or {}).get("href", "")
            mm = re.search(r"/([a-z]{3})\.png", h)
            return mm.group(1).upper() if mm else ""
        p1, s1 = info(na); p2, s2 = info(nb)
        slug = lambda n: re.sub(r"[^a-z]", "", lastkey(n))
        mid = f"{day}-{t['id'].split('-', 1)[1]}-{slug(na)}-{slug(nb)}"
        m = {"tournoiId": t["id"], "tournoi": t.get("nom"), "categorie": t.get("categorie", ""), "surface": t.get("surface", ""),
             "tour": tour, "date": day, "heure": t0.strftime("%H:%M") if c.get("timeValid") else "",
             "ordre": len([x for x in data["matchs"] if x.get("date") == day and x.get("tournoiId") == t["id"]]) + 1,
             "j1": na, "j1Pays": p1 or flag(a), "j1Tds": s1, "j2": nb, "j2Pays": p2 or flag(b), "j2Tds": s2,
             "statut": "a_venir", "score": "", "vainqueur": None, "id": mid}
        if m["j1Pays"] in ("RUS", "BLR"): m["j1Pays"] = ""
        if m["j2Pays"] in ("RUS", "BLR"): m["j2Pays"] = ""
        data["matchs"].append(m); added.append(m)
    return added

def main():
    now, off = paris_now()
    tz = timezone(timedelta(hours=off))
    data = json.load(open("data.json", encoding="utf-8"))
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    sb = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    comps = []
    for e in sb.get("events", []):
        for g in e.get("groupings", []):
            if (g.get("grouping") or {}).get("slug") != "mens-singles": continue
            for c in g.get("competitions", []):
                cs = c.get("competitors") or []
                if len(cs) == 2 and all((x.get("athlete") or {}).get("displayName", "TBD") != "TBD" for x in cs):
                    comps.append(c)
    changed = []
    today = now.strftime("%Y-%m-%d"); yest = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    for m in data.get("matchs", []):
        if m.get("date") not in (today, yest): continue
        L = m.get("live") or {}
        if m.get("statut") == "termine" and L.get("fini"): continue
        found = None
        for c in comps:
            a, b = c["competitors"]
            na, nb = a["athlete"]["displayName"], b["athlete"]["displayName"]
            if same(na, m["j1"]) and same(nb, m["j2"]): found = (c, a, b); break
            if same(nb, m["j1"]) and same(na, m["j2"]): found = (c, b, a); break
        if not found: continue
        c, c1, c2 = found
        st = (c.get("status") or {}).get("type") or {}
        state, detail = st.get("state"), (st.get("detail") or "")
        l1 = [int(round(float(x.get("value", 0)))) for x in c1.get("linescores") or []]
        l2 = [int(round(float(x.get("value", 0)))) for x in c2.get("linescores") or []]
        sets = [[x, y] for x, y in zip(l1, l2)]
        before = json.dumps(m, sort_keys=True)
        if state == "pre":
            if c.get("timeValid") and c.get("date"):
                try:
                    t = datetime.strptime(c["date"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc).astimezone(tz)
                    if t.strftime("%Y-%m-%d") == m["date"]: m["heure"] = t.strftime("%H:%M")
                except Exception: pass
        elif state in ("in", "post"):
            score = " ".join(f"{x}-{y}" for x, y in sets)
            if state == "post":
                w = 1 if c1.get("winner") else 2 if c2.get("winner") else None
                low = detail.lower()
                if "walkover" in low or "w/o" in low: score = "forfait"
                elif "ret" in low and score: score += " ab."
                if w:
                    m["statut"], m["vainqueur"], m["score"] = "termine", w, score
                    L.update({"sets": sets, "fini": True}); L.pop("jeu", None); L.pop("service", None)
            else:
                m["statut"], m["score"] = "en_cours", score or "0-0"
                L.update({"sets": sets or [[0, 0]]}); L.pop("jeu", None)
                srv = 1 if c1.get("possession") else 2 if c2.get("possession") else None
                if srv: L["service"] = srv
            L["maj"] = now.isoformat(timespec="seconds")
            m["live"] = L
        if json.dumps(m, sort_keys=True) != before:
            changed.append(m)
    # tableaux des tournois
    for m in changed:
        if m.get("statut") != "termine" or not m.get("vainqueur"): continue
        t = next((t for t in data.get("tournois", []) if t.get("id") == m.get("tournoiId")), None)
        if not t or not t.get("tableau"): continue
        rounds = t["tableau"].get("matchs") or []
        for r, ms in enumerate(rounds):
            for i, bm in enumerate(ms):
                p1, p2 = bm.get("j1") or {}, bm.get("j2") or {}
                if not p1.get("nom") or not p2.get("nom"): continue
                if same(p1["nom"], m["j1"]) and same(p2["nom"], m["j2"]): flip = False
                elif same(p1["nom"], m["j2"]) and same(p2["nom"], m["j1"]): flip = True
                else: continue
                w = m["vainqueur"] if not flip else 3 - m["vainqueur"]
                sc = m["score"]
                if flip and sc != "forfait":
                    sc = " ".join("-".join(reversed(s.split("-"))) if "-" in s else s for s in sc.split(" "))
                bm["vainqueur"], bm["score"] = w, sc
                if r + 1 < len(rounds) and i // 2 < len(rounds[r + 1]):
                    nxt = rounds[r + 1][i // 2]
                    nxt["j1" if i % 2 == 0 else "j2"] = p1 if w == 1 else p2
    changed += add_new(data, comps, now, tz)
    if changed:
        data.setdefault("meta", {})["misAJour"] = now.isoformat(timespec="seconds")
        json.dump(data, open("data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("matchs mis à jour :", ", ".join(m["id"] for m in changed) or "aucun")

main()
