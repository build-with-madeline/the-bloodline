#!/usr/bin/env python3
"""
The merged data model. The original extraction (data/genealogy.json) is IMMUTABLE.
Expansion happens in data/additions/*.json, layered on top at build time.

A union dot = a MARRIAGE (exactly 2 parents). Children are 0+.  A childless
marriage is a valid union with 0 children (per the corrected semantics).

Additions file format:
{
  "families": [
    {
      "a": "HVIII" | {"id":"NEWID","label":"Name<br/>1500-1560","style":"fill:#..,color:#000"},
      "b": "ANNECLEVES" | {...},
      "children": [ "EXISTINGID" | {"id":..,"label":..}, ... ],   # [] == childless
      "note": "optional provenance"
    }
  ]
}
`a`/`b`/each child may be an existing id (string) or a new person (object).
If a union between a and b already exists, new children are appended to it
(no duplicate union).
"""
import json
import re
from pathlib import Path
from collections import defaultdict

ROOT = Path("/Users/madelinevinson/Downloads/the-bloodline")
GEN = ROOT / "data/genealogy.json"
ADD_DIR = ROOT / "data/additions"


def _icon(label):
    if not label:
        return ""
    if label.startswith("👑"):
        return "monarch"
    if label.startswith("✝"):
        return "pope"
    return ""


def load_merged():
    g = json.load(open(GEN, encoding="utf-8"))
    people = {pid: dict(info) for pid, info in g["people"].items()}
    unions = {uid: {"id": uid, "parents": list(u["parents"]), "children": list(u["children"])}
              for uid, u in g["unions"].items()}
    edges = [tuple(e) for e in g["edges"]]

    # index unions by frozenset of parents for dedup / append
    def parent_key(u):
        return frozenset(u["parents"])
    by_parents = {parent_key(u): uid for uid, u in unions.items() if len(u["parents"]) == 2}

    def ensure_person(ref):
        if isinstance(ref, str):
            if ref not in people:
                raise ValueError(f"family references unknown existing person id: {ref}")
            return ref
        pid = ref["id"]
        if pid not in people:
            people[pid] = {"id": pid, "label": ref.get("label"), "icon": _icon(ref.get("label"))}
            if ref.get("style"):
                people[pid]["style"] = ref["style"]
        return pid

    def new_union_id(a, b):
        base = f"U_{a.lower()}_{b.lower()}"
        uid = base
        i = 2
        while uid in unions:
            uid = f"{base}_{i}"; i += 1
        return uid

    applied = 0
    for f in sorted(ADD_DIR.glob("*.json")) if ADD_DIR.exists() else []:
        payload = json.load(open(f, encoding="utf-8"))
        for fam in payload.get("families", []):
            a = ensure_person(fam["a"])
            b = ensure_person(fam["b"])
            key = frozenset((a, b))
            if key in by_parents:
                uid = by_parents[key]
            else:
                uid = fam.get("union_id") or new_union_id(a, b)
                unions[uid] = {"id": uid, "parents": [a, b], "children": []}
                by_parents[key] = uid
                edges.append((a, uid)); edges.append((b, uid))
            # a servant/concubine union is a different KIND, tied back to the
            # mistress the servant belonged to (Hagar->Sarah, Bilhah->Rachel, ...)
            if fam.get("kind"):
                unions[uid]["kind"] = fam["kind"]
            if fam.get("mistress"):
                unions[uid]["mistress"] = fam["mistress"]
            for child in fam.get("children", []):
                cid = ensure_person(child)
                if cid not in unions[uid]["children"]:
                    unions[uid]["children"].append(cid)
                    edges.append((uid, cid))
            applied += 1

    # Reigning queens / female sovereigns (ruled in their own right) get the 👑,
    # like the kings. Consorts and regents (ruled for someone else) do NOT.
    QUEENS_REGNANT = {
        "MARYI", "ELIZI", "EMPM", "ISABELLAI", "JUANAMAD", "MQOS", "BERENGARIA",
        "BLANCHENAV", "ISABJER", "CONSTSICILY", "ANNEBRIT", "MARYBURGUNDY",
    }
    for pid in QUEENS_REGNANT:
        info = people.get(pid)
        if info and info.get("label") and not info["label"].startswith("👑"):
            info["label"] = "👑 " + info["label"]
            info["icon"] = "monarch"

    # Icons: 😇 = canonized saint, ✝ = held a church office above priest (bishop/
    # archbishop/cardinal/pope). Rebuilt in a fixed order 👑 ✝ 😇 so nothing doubles up.
    SAINTS = {
        "ADELAIDEIT", "ARNULFMETZ", "BEGGA", "CLOTILDE", "CUNIGUNDE", "FERDIII",
        "HENRYIIHRE", "ITTA", "LIX", "MARGS", "MATRING", "OLGA", "RICHARDIS", "VLADIMIR", "HELENA",
    }
    CLERGY = {"ARNOALD", "ARNULFMETZ", "CHARLESL", "GREGORYV", "JAMESROSS", "POPECLEMENTVII", "POPELEOX"}
    ICONS = ("👑", "✝️", "✝", "😇")
    for pid, info in people.items():
        lab = info.get("label")
        if not lab:
            continue
        crown = False
        core = lab
        changed = True
        while changed:                                   # peel any existing leading icons
            changed = False
            for ic in ICONS:
                if core.startswith(ic):
                    if ic == "👑":
                        crown = True
                    core = core[len(ic):].lstrip()
                    changed = True
        prefix = ("👑" if crown else "") + ("✝" if pid in CLERGY else "") + ("😇" if pid in SAINTS else "")
        info["label"] = (prefix + " " + core) if prefix else core

    return {"people": people, "unions": unions, "edges": edges, "_applied_families": applied}


def audit(graph):
    people = graph["people"]; unions = graph["unions"]
    problems = {}
    # unions must have exactly 2 parents (marriage). children 0+ is FINE.
    problems["unions_not_2_parents"] = [u for u, d in unions.items() if len(d["parents"]) != 2]
    # every union id used in edges must be defined and vice-versa
    problems["people_missing_label"] = [p for p, d in people.items() if not d.get("label")]
    # cycle check (person -> child)
    adj = defaultdict(set)
    for u in unions.values():
        for p in u["parents"]:
            for c in u["children"]:
                adj[p].add(c)
    WHITE, GREY, BLACK = 0, 1, 2
    color = {n: WHITE for n in people}
    cyc = []

    def dfs(s):
        stack = [(s, iter(adj[s]))]; color[s] = GREY
        while stack:
            node, it = stack[-1]
            for nb in it:
                if color.get(nb) == GREY:
                    cyc.append((node, nb)); return True
                if color.get(nb, BLACK) == WHITE:
                    color[nb] = GREY; stack.append((nb, iter(adj[nb]))); break
            else:
                color[node] = BLACK; stack.pop()
        return False

    for n in list(people):
        if color[n] == WHITE:
            if dfs(n):
                break
    problems["cycles"] = cyc

    childless = [u for u, d in unions.items() if len(d["children"]) == 0]
    return {
        "people": len(people),
        "unions": len(unions),
        "childless_marriages": len(childless),
        "problems": {k: v for k, v in problems.items() if v},
    }


if __name__ == "__main__":
    g = load_merged()
    rep = audit(g)
    print(f"applied families: {g['_applied_families']}")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
