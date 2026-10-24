"""Fusionne un export de la base (dossier avec matchs/, tournois/, classements/, meta/ en JSON) dans data.json.
Usage : python3 tools/export.py <dossier_export> data.json
Les scores déjà plus récents dans data.json (mis à jour par tools/scores.py) sont conservés."""
import json,os,sys,glob
from datetime import datetime
src,dst=sys.argv[1],sys.argv[2]
def load(c):return {os.path.basename(f)[:-5]:json.load(open(f)) for f in sorted(glob.glob(f"{src}/{c}/*.json"))}
M,T,C,Me=load('matchs'),load('tournois'),load('classements'),load('meta')
old={}
try: old=json.load(open(dst))
except Exception: pass
import unicodedata,re
def ln(n):
  w=re.sub(r"[^a-z ]"," ",unicodedata.normalize("NFD",str(n or "")).encode("ascii","ignore").decode().lower()).split()
  return w[-1] if w else ""
pk=lambda m:(m.get('date'),frozenset((ln(m.get('j1')),ln(m.get('j2')))))
OM={m['id']:m for m in old.get('matchs',[])}
OP={pk(m):m for m in old.get('matchs',[])}; OT={t['id']:t for t in old.get('tournois',[])}
def ts(m):
  s=(m.get('live') or {}).get('maj') or ''
  try: return datetime.fromisoformat(s).timestamp()
  except Exception: return 0
rank={'a_venir':0,'en_cours':1,'termine':2}
for k,m in M.items():
  o=OM.get(k) or OP.get(pk(m))
  if not o: continue
  if o.get('heure') and not m.get('heure'): m['heure']=o['heure']
  if o.get('j1') and ln(o.get('j1'))!=ln(m.get('j1')):
    continue  # ordre des joueurs différent : on garde la base
  # le fichier public (mis à jour toutes les 10 min par GitHub) est gardé s'il est plus récent ou plus avancé
  if ts(o)>ts(m) or rank.get(o.get('statut'),0)>rank.get(m.get('statut'),0):
    stats=(m.get('live') or {}).get('stats')
    for f in ('statut','score','vainqueur','heure'):
      if f in o: m[f]=o[f]
    L=dict(o.get('live') or {})
    if stats and not L.get('stats'): L['stats']=stats
    elif stats and L.get('fini') is not True: L['stats']=stats
    if (m.get('live') or {}).get('srId') and not L.get('srId'): L['srId']=m['live']['srId']
    m['live']=L
# matchs ajoutés automatiquement dans le fichier public (pas encore dans la base) : on les garde
from datetime import date,timedelta
pairs={pk(m) for m in M.values()}
lim=(date.today()-timedelta(days=1)).isoformat()
for k,o in OM.items():
  if k in M or o.get('date','')<lim: continue
  if pk(o) in pairs: continue
  M[k]={x:v for x,v in o.items() if x!='id'}
for k,t in T.items():
  o=OT.get(k)
  if not o or not o.get('tableau') or not t.get('tableau'): continue
  try:
    for r,(ra,rb) in enumerate(zip(t['tableau']['matchs'],o['tableau']['matchs'])):
      for i,(a,b) in enumerate(zip(ra,rb)):
        if b.get('vainqueur') and not a.get('vainqueur'): a['vainqueur'],a['score']=b['vainqueur'],b.get('score','')
        for s in ('j1','j2'):
          if b.get(s) and not a.get(s): a[s]=b[s]
  except Exception: pass
meta=Me.get('maj',{})
om=(old.get('meta') or {}).get('misAJour')
if om and meta.get('misAJour') and om>meta['misAJour']: meta['misAJour']=om
d={"matchs":[{"id":k,**v} for k,v in M.items()],"tournois":[{"id":k,**v} for k,v in T.items()],
   "meta":meta,"fond":"fond.jpg","classements":{"atp":C.get('atp',{}),"race":C.get('race',{})}}
json.dump(d,open(dst,'w'),ensure_ascii=False,indent=1)
print(len(d['matchs']),'matchs',len(d['tournois']),'tournois',d['meta'])
