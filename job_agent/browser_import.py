"""Score jobs collected in Chrome (compact feature rows) with the normal matcher.

Each row: id~title~company~location~worktype~easy~applied~desclen~years~salmax~degree~req~pref~resp
where req/pref are dot-separated indices into matcher.SKILL_VOCAB keys, and resp is one digit per
scoring profile (responsibility hits, in config order). The full description stays in the browser.
"""
from __future__ import annotations

from unittest import mock

from . import matcher


def parse_rows(text: str) -> list[dict]:
    keys = list(matcher.SKILL_VOCAB)
    out = []
    for line in text.strip().splitlines():
        p = line.split("~")
        if len(p) < 14:
            continue
        idx = lambda s: {keys[int(i)] for i in s.split(".") if i.strip().isdigit() and int(i) < len(keys)}
        out.append(dict(id=p[0], title=p[1].strip(), company=p[2].strip(), location=p[3].strip(), wt=p[4],
                        easy=p[5] == "1", applied=p[6] == "1", desc_len=int(p[7] or 0),
                        years=int(p[8]) if p[8] else None, sal=int(p[9]) if p[9] else None, degree=p[10] == "1",
                        req=idx(p[11]), pref=idx(p[12]), resp=[int(c) for c in p[13]]))
    return out


def score_row(r: dict, profile: dict, cfg: dict) -> dict:
    names = list(cfg["profiles"])
    resp = dict(zip(names, r["resp"]))
    desc = ("x " * 150 + (" computer science" if r["degree"] else "")) if r["desc_len"] >= 200 else "short"
    job = {"title": r["title"], "description": desc, "location": r["location"],
           "remote": r["wt"] == "R", "salary_max": r["sal"], "salary_min": None}
    by_spec = {id(cfg["profiles"][n]): resp.get(n, 0) for n in names}
    with mock.patch.object(matcher, "extract_skills", lambda d: (set(r["req"]), set(r["pref"]))), \
         mock.patch.object(matcher, "required_years", lambda d: r["years"]), \
         mock.patch.object(matcher, "responsibilities_hit", lambda d, spec: ["x"] * by_spec.get(id(spec), 0)):
        return matcher.score_job(job, profile, cfg)
