#!/usr/bin/env python3
"""One-command rebuild: audit -> classify -> generate. Run after any data change."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import model
import classify

def main():
    g = model.load_merged()
    rep = model.audit(g)
    print("=== AUDIT ===")
    print(f"people: {rep['people']}  unions: {rep['unions']}  "
          f"childless marriages: {rep['childless_marriages']}  "
          f"applied families: {g['_applied_families']}")
    if rep["problems"]:
        print("PROBLEMS:", rep["problems"])
        sys.exit("Aborting build: fix data problems first.")
    print("no structural problems\n")
    print("=== CLASSIFY ===")
    classify.main()
    # Import generate only AFTER classify has written the fresh dynasty.json,
    # so generate reads current classifications (it loads dynasty.json at import).
    print("\n=== GENERATE ===")
    import generate
    generate.main()

if __name__ == "__main__":
    main()
