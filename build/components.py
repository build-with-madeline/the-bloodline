import json
from collections import defaultdict
G = json.load(open("data/genealogy.json"))
edges = G["edges"]
ug = defaultdict(set)
allids = set(G["people"]) | set(G["unions"])
for a, b in edges:
    ug[a].add(b); ug[b].add(a)
seen = set(); comps = []
for n in allids:
    if n in seen: continue
    stack = [n]; seen.add(n); comp = []
    while stack:
        x = stack.pop(); comp.append(x)
        for nb in ug[x]:
            if nb not in seen: seen.add(nb); stack.append(nb)
    comps.append(comp)
comps.sort(key=len, reverse=True)

def nm(x):
    return (G["people"][x]["label"] or x).split("<br/>")[0] if x in G["people"] else x

print(f"total components: {len(comps)}")
for c in comps:
    persons = [x for x in c if not x.startswith("U_")]
    reps = [nm(p) for p in persons[:6]]
    print(f"  size {len(c):3d} ({len(persons):3d} ppl): {reps}")
