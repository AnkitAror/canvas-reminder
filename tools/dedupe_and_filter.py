"""Group duplicate assignments (cross-listed / "(COPY)" course shells) and drop completed ones.

Rule: if ANY item in a duplicate group is completed (Canvas submission status, or a manual
"[Canvas Done]" email), the whole group is treated as done and removed.

Two items are duplicates when ALL of these hold:
  - they are due at the same minute
  - their titles match after normalizing case/punctuation (or are >= 90% similar)
  - their courses are related: same course name, or the same course code (e.g. 01:640:350,
    so "01:640:350:03 LINEAR ALGEBRA" ~ "01:640:350:03 (COPY)"); when a course has no code,
    names must match once "(COPY)" is removed
"""
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "exclude_rules.json"

CODE_RE = re.compile(r"\b(\d{2}:\d{3}:\d{3})")  # Rutgers style school:subject:course
TITLE_SIMILARITY = 0.9


def norm_title(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def _course_code(c):
    m = CODE_RE.search(c or "")
    return m.group(1) if m else None


def _is_copy(c):
    return "copy" in (c or "").lower()


def _strip_copy(c):
    return norm_title(re.sub(r"\(?\bcopy\b\)?", " ", c or "", flags=re.IGNORECASE))


def courses_related(c1, c2):
    if c1 == c2:
        return True
    k1, k2 = _course_code(c1), _course_code(c2)
    if k1 and k2:  # both have a course code -> they must match
        return k1 == k2
    # No codes: same name once "(COPY)" is removed, or one name contains the other
    s1, s2 = _strip_copy(c1), _strip_copy(c2)
    return bool(s1 and s2) and (s1 == s2 or s1 in s2 or s2 in s1)


def is_duplicate(a, b):
    if a["due_at"][:16] != b["due_at"][:16]:
        return False
    if not courses_related(a["course"], b["course"]):
        return False
    ta, tb = norm_title(a["title"]), norm_title(b["title"])
    return ta == tb or SequenceMatcher(None, ta, tb).ratio() >= TITLE_SIMILARITY


def group_duplicates(items):
    """Union-find over pairwise duplicate checks. Returns a list of groups (lists of items)."""
    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if is_duplicate(items[i], items[j]):
                parent[find(j)] = find(i)

    groups = {}
    for i, it in enumerate(items):
        groups.setdefault(find(i), []).append(it)
    return list(groups.values())


def _merge(group, done_ids):
    # Primary = the "real" course (not a COPY shell), else the first one
    primary = next((g for g in group if not _is_copy(g["course"])), group[0])
    ids = [g["id"] for g in group if g.get("id")]
    merged = dict(primary)
    merged["ids"] = ids
    merged["also_in"] = [g["course"] for g in group if g is not primary and g["course"] != primary["course"]]
    merged["is_exam"] = any(g["is_exam"] for g in group)
    merged["completed"] = any(g.get("completed") for g in group) or any(i in done_ids for i in ids)
    return merged


def load_exclude_rules(path=RULES_PATH):
    if not path.exists():
        return []
    rules = json.loads(path.read_text()).get("rules", [])
    return [{k: re.compile(r[k], re.IGNORECASE) for k in ("course", "title") if r.get(k)}
            for r in rules if r.get("course") or r.get("title")]


def is_excluded(item, rules):
    return any(all(rx.search(item.get(field) or "") for field, rx in rule.items()) for rule in rules)


def process(data, done_ids=frozenset(), rules=None):
    """Mutates and returns data: drop excluded items, then merge duplicates and drop
    completed groups."""
    rules = load_exclude_rules() if rules is None else rules
    kept = [i for i in data["items"] if not is_excluded(i, rules)]
    data["excluded"] = len(data["items"]) - len(kept)
    groups = group_duplicates(kept)
    merged = [_merge(g, set(done_ids)) for g in groups]
    data["duplicates_merged"] = sum(len(g) - 1 for g in groups)
    data["hidden_done"] = sum(1 for m in merged if m["completed"])
    data["items"] = sorted((m for m in merged if not m["completed"]), key=lambda i: i["due_at"])
    return data
