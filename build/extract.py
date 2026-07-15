#!/usr/bin/env python3
"""
Losslessly extract the genealogy from the existing single-file Mermaid diagram
into structured JSON. This is the data-layer foundation: everything downstream
(the dynasty-partitioned website, the mass expansion) is generated FROM this
data, never by hand-editing Mermaid again.

Model of the source graph:
  - Person nodes:  ID["label with &lt;br/&gt; breaks"]   (uppercase-ish IDs)
  - Union nodes:   U_a_b(("&bull;"))  gold-dot marriage nodes, IDs start with U_
  - Edges:         X --> Y            (HTML-encoded as --&gt; in the file)
  - Union semantics: (parent1 --> U), (parent2 --> U), (U --> child), (U --> child)...
  - Styling:       `class <list> union` registers dot nodes; `style ID fill:..` colors people
"""
import json
import re
import sys
import html
from pathlib import Path

SRC = Path("/Users/madelinevinson/Downloads/the-bloodline-node-diagram.html")
OUT = Path("/Users/madelinevinson/Downloads/the-bloodline/data/genealogy.json")


def extract_mermaid_block(text: str) -> str:
    m = re.search(r'<pre class="mermaid">(.*?)</pre>', text, re.DOTALL)
    if not m:
        sys.exit("ERROR: could not find <pre class=\"mermaid\"> block")
    return m.group(1)


def main():
    raw = SRC.read_text(encoding="utf-8")
    block = extract_mermaid_block(raw)
    lines = block.split("\n")

    people = {}      # id -> {label, icon, is_monarch, is_pope}
    unions = {}      # union_id -> {parents: [], children: []}
    edges = []       # (src, dst) decoded
    styles = {}      # id -> raw style string (fill/color)
    union_registered = set()

    # --- node definition regexes (operate on HTML-decoded lines) ---
    # Person def:  ID["...label..."]   label may contain <br/> (decoded)
    person_def_re = re.compile(r'^\s*([A-Za-z][A-Za-z0-9_]*)\["(.*?)"\]\s*$')
    # Union def:   U_x(("&bull;"))  -> after decode: U_x(("•"))
    union_def_re = re.compile(r'^\s*(U_[A-Za-z0-9_]*)\(\("(.*?)"\)\)\s*$')
    # Edge (optionally with inline node def on either side):
    edge_re = re.compile(r'^\s*(.+?)\s*-->\s*(.+?)\s*$')
    # inline node forms on an edge endpoint:
    inline_person_re = re.compile(r'^([A-Za-z][A-Za-z0-9_]*)\["(.*?)"\]$')
    inline_union_re = re.compile(r'^(U_[A-Za-z0-9_]*)(?:\(\("(.*?)"\)\))?$')
    style_re = re.compile(r'^\s*style\s+([A-Za-z0-9_]+)\s+(.*?)\s*$')
    class_union_re = re.compile(r'^\s*class\s+(.+?)\s+union\s*$')

    def register_person(pid, label):
        # A later real definition should win over an earlier bare reference.
        if pid in people and people[pid].get("label"):
            return
        icon = ""
        if label:
            if label.startswith("👑"):
                icon = "monarch"
            elif label.startswith("✝"):
                icon = "pope"
        people[pid] = {"id": pid, "label": label, "icon": icon}

    def note_endpoint(token):
        """Return canonical id for an edge endpoint, registering inline defs."""
        token = token.strip()
        mu = inline_union_re.match(token)
        mp = inline_person_re.match(token)
        if token.startswith("U_"):
            uid = mu.group(1) if mu else token
            unions.setdefault(uid, {"id": uid, "parents": [], "children": []})
            return uid
        if mp:
            register_person(mp.group(1), mp.group(2))
            return mp.group(1)
        # bare person id referenced before/without a bracket def
        register_person(token, None if token not in people else people[token]["label"])
        return token

    for line in lines:
        # decode HTML entities so we work with real <, >, &, •
        dline = html.unescape(line)
        s = dline.strip()
        if not s or s.startswith("%%"):
            continue

        m = class_union_re.match(dline)
        if m:
            for uid in m.group(1).split(","):
                uid = uid.strip()
                if uid:
                    union_registered.add(uid)
                    unions.setdefault(uid, {"id": uid, "parents": [], "children": []})
            continue

        m = style_re.match(dline)
        if m:
            styles[m.group(1)] = m.group(2)
            continue

        if s.startswith("classDef") or s.startswith("flowchart") or s.startswith("graph"):
            continue

        m = union_def_re.match(dline)
        if m:
            unions.setdefault(m.group(1), {"id": m.group(1), "parents": [], "children": []})
            continue

        m = person_def_re.match(dline)
        if m:
            register_person(m.group(1), m.group(2))
            continue

        m = edge_re.match(dline)
        if m:
            src = note_endpoint(m.group(1))
            dst = note_endpoint(m.group(2))
            edges.append((src, dst))
            continue

        # anything else we ignore but report
        # (helps catch parser gaps)
        # print("UNPARSED:", repr(s), file=sys.stderr)

    # --- derive union parent/child structure from edges ---
    for src, dst in edges:
        if dst.startswith("U_"):
            unions[dst]["parents"].append(src)
        elif src.startswith("U_"):
            unions[src]["children"].append(dst)

    # attach styles
    for pid, st in styles.items():
        if pid in people:
            people[pid]["style"] = st

    data = {
        "people": people,
        "unions": unions,
        "edges": edges,
        "union_registered": sorted(union_registered),
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- audit / report ---
    n_people = len(people)
    n_unions = len(unions)
    n_edges = len(edges)
    unions_wrong_parents = [u for u, d in unions.items() if len(d["parents"]) != 2]
    unions_no_children = [u for u, d in unions.items() if len(d["children"]) == 0]
    unregistered = [u for u in unions if u not in union_registered]
    registered_but_missing = [u for u in union_registered if u not in unions]

    print(f"people:            {n_people}")
    print(f"unions:            {n_unions}")
    print(f"edges:             {n_edges}")
    print(f"union_registered:  {len(union_registered)}")
    print(f"unions !=2 parents: {len(unions_wrong_parents)} {unions_wrong_parents[:8]}")
    print(f"unions 0 children:  {len(unions_no_children)} {unions_no_children[:8]}")
    print(f"unions unregistered:{len(unregistered)} {unregistered[:8]}")
    print(f"registered-not-defined:{len(registered_but_missing)} {registered_but_missing[:8]}")
    # people with no label captured (bare refs)
    no_label = [p for p, d in people.items() if not d.get("label")]
    print(f"people w/o label:   {len(no_label)} {no_label[:12]}")


if __name__ == "__main__":
    main()
