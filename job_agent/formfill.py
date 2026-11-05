"""Generic Playwright form filler for standard ATS application pages (Greenhouse, Lever, Ashby, Workable).

It reads every visible field, answers it from your profile, fills it, validates, and walks through
multi-step forms. It never clicks the final submit button itself - `apply.py` decides that.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .answers import Answer, Answerer, choose_option

COLLECT_JS = r"""
() => {
  const out = []; window.__jaN = window.__jaN || 0; const groups = {};
  const txt = s => (s || '').replace(/\s+/g, ' ').trim();
  const visible = el => el.type === 'file' || !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const own = el => {
    if (el.id) { const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`); if (l) return l.innerText; }
    const anc = el.closest('label'); if (anc) return anc.innerText;
    return '';
  };
  const questionOf = el => {
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    const lb = el.getAttribute('aria-labelledby');
    if (lb) { const t = lb.split(' ').map(i => document.getElementById(i)).filter(Boolean).map(e => e.innerText).join(' '); if (txt(t)) return t; }
    const o = own(el); if (txt(o)) return o;
    const c = el.closest('.application-question, .field, .form-group, .application-field, [class*="question"], [class*="Field"], [class*="field"], fieldset, li');
    if (c) { const l = c.querySelector('legend, .application-label, label, [class*="label"], [class*="Label"]'); if (l) return l.innerText; }
    return el.getAttribute('placeholder') || el.name || '';
  };
  document.querySelectorAll('input, textarea, select').forEach(el => {
    const t = (el.type || el.tagName).toLowerCase();
    if (['hidden', 'submit', 'button', 'image', 'reset', 'search'].includes(t)) return;
    if (!visible(el) || el.disabled) return;
    let id = el.getAttribute('data-ja'); if (!id) { id = 'ja' + (window.__jaN++); el.setAttribute('data-ja', id); }
    if (t === 'radio') {
      const key = el.name || id;
      if (!groups[key]) {
        const fs = el.closest('fieldset, [role=radiogroup], .application-question, [class*="question"], .field, .form-group');
        let q = '';
        if (fs) { const l = fs.querySelector('legend, .application-label, [class*="label"]:not(label)') || fs.querySelector('label'); q = l ? l.innerText : ''; }
        groups[key] = {id: key, kind: 'radio', label: txt(q) || key, required: false, options: [], ids: [], value: ''};
        out.push(groups[key]);
      }
      groups[key].options.push(txt(own(el)) || el.value); groups[key].ids.push(id);
      if (el.required) groups[key].required = true;
      if (el.checked) groups[key].value = txt(own(el)) || el.value;
      return;
    }
    const label = txt(questionOf(el));
    const f = {id, kind: el.tagName === 'SELECT' ? 'select' : el.tagName === 'TEXTAREA' ? 'textarea' : t,
               label, required: el.required || el.getAttribute('aria-required') === 'true' || /\*\s*$/.test(label),
               value: t === 'checkbox' ? String(el.checked) : (t === 'file' ? String(el.files && el.files.length) : (el.value || ''))};
    if (el.tagName === 'SELECT') f.options = [...el.options].map(o => txt(o.text));
    out.push(f);
  });
  return out;
}
"""

ERRORS_JS = r"""
() => [...document.querySelectorAll('[role=alert], .error, .errors, .field-error, .error-message, [class*="error" i]:not(input):not(form), [aria-invalid=true]')]
  .filter(e => e.offsetParent !== null).map(e => (e.innerText || e.getAttribute('aria-label') || e.name || '').trim())
  .filter(Boolean).slice(0, 10)
"""

CAPTCHA_JS = r"""
() => {
  const frames = [...document.querySelectorAll('iframe')].filter(f => f.offsetHeight > 30);
  const bad = frames.some(f => /hcaptcha\.com|challenges\.cloudflare\.com|recaptcha\/api2\/(anchor|bframe)|arkoselabs|funcaptcha/i.test(f.src || '')
                               && !/size=invisible/i.test(f.src || ''));
  const widgets = [...document.querySelectorAll('.h-captcha, .cf-turnstile, .g-recaptcha:not([data-size=invisible])')].some(e => e.offsetHeight > 30);
  return bad || widgets;
}
"""

EEO = re.compile(r"(?i)\b(gender|sex|race|ethnic|veteran|disab|sexual orientation|pronoun|hispanic|latino|religion|caste)\b")
DECLINE = re.compile(r"(?i)decline|prefer not|don.?t wish|do not wish|not to (say|disclose|answer)|rather not")
RESUME_LBL = re.compile(r"(?i)resume|cv|curriculum")
COVER_LBL = re.compile(r"(?i)cover letter|motivation letter")
CONSENT_LBL = re.compile(r"(?i)privacy (policy|notice)|consent to (the )?(processing|collection)|process my (personal )?data|data protection")
OPTIONAL_CB = re.compile(r"(?i)newsletter|marketing|talent (pool|community)|future (roles|opportunities)|subscribe|text messages|sms")
SUBMIT_BTN = re.compile(r"(?i)^\s*(submit( your)?( application)?|apply( now)?|send( application)?|complete application)\s*$")
NEXT_BTN = re.compile(r"(?i)^\s*(next|continue|save (&|and) continue|proceed|review( application)?)\s*(→|>)?\s*$")
CONFIRM_TXT = re.compile(r"(?i)thank(s| you)( for (applying|your (application|interest)))?|application (has been |was )?(submitted|received|sent)|we('ve| have) received your application|successfully (applied|submitted)")


@dataclass
class FillResult:
    answers: dict = field(default_factory=dict)       # label -> {value, confidence, note}
    unresolved: list = field(default_factory=list)    # required fields with no safe answer
    review: list = field(default_factory=list)        # filled but flagged for a human look
    errors: list = field(default_factory=list)
    captcha: bool = False
    steps: int = 0
    submit_ready: bool = False


def _record(res: FillResult, label: str, ans: Answer, required: bool) -> None:
    res.answers[label] = {"value": ans.value, "confidence": ans.confidence, "note": ans.note}
    if ans.confidence == "unknown" and required:
        res.unresolved.append(label)
    elif ans.confidence == "review":
        res.review.append(f"{label} -> {ans.value} ({ans.note})")


def _fill_page(page, answerer: Answerer, docs: dict, res: FillResult, prev_applied: bool) -> None:
    fields = page.evaluate(COLLECT_JS)
    for f in fields:
        label, kind, req = f["label"] or "(unlabelled)", f["kind"], f["required"]
        loc = page.locator(f'[data-ja="{f["id"]}"]')

        if kind == "file":
            if RESUME_LBL.search(label) or (label == "(unlabelled)" and not res.answers.get("__resume")):
                loc.set_input_files(docs["resume_path"])
                res.answers[label] = {"value": f"[file] {docs['resume_version']}", "confidence": "exact", "note": ""}
                res.answers["__resume"] = True
            elif COVER_LBL.search(label):
                loc.set_input_files(docs["cover_path"])
                res.answers[label] = {"value": "[file] cover letter", "confidence": "exact", "note": ""}
            elif req:
                res.unresolved.append(f"{label} (file upload)")
            continue

        if kind == "textarea" and COVER_LBL.search(label):
            loc.fill(docs["cover_text"])
            res.answers[label] = {"value": "[cover letter text]", "confidence": "exact", "note": ""}
            continue

        if kind == "checkbox":
            if CONSENT_LBL.search(label) or re.search(r"(?i)(confirm|certify|declare).*(accurate|true|correct)", label):
                loc.check()
                res.answers[label] = {"value": "checked", "confidence": "derived",
                                      "note": "application consent / accuracy declaration"}
            elif OPTIONAL_CB.search(label) and not req:
                res.answers[label] = {"value": "left unchecked", "confidence": "exact", "note": "optional opt-in"}
            elif req:
                res.unresolved.append(f"{label} (checkbox)")
            continue

        # Voluntary diversity questions: you gave no answers, so decline where the form allows it.
        if EEO.search(label):
            opts = f.get("options") or []
            pick = next((o for o in opts if DECLINE.search(o)), None)
            if not pick:   # mandatory on many Indian portals: use your profile value if you gave one
                own = answerer.answer(label)
                if own.value and opts:
                    pick = choose_option(own.value, opts)
                elif own.value and kind not in ("select", "radio"):
                    loc.fill(own.value)
                    res.answers[label] = {"value": own.value, "confidence": "exact", "note": "from profile"}
                    continue
            if pick:
                _set_choice(page, f, pick)
                res.answers[label] = {"value": pick, "confidence": "exact",
                                      "note": "voluntary - declined" if DECLINE.search(pick) else "from profile"}
            elif req:
                res.unresolved.append(label)
            continue

        if f.get("value") and kind not in ("radio", "select"):
            res.answers[label] = {"value": f["value"], "confidence": "prefilled", "note": "already filled on page"}
            continue

        ans = answerer.answer(label, prev_applied)
        if ans.confidence == "unknown":
            if req:
                res.unresolved.append(label)
            continue
        if kind in ("select", "radio"):
            pick = choose_option(ans.value, f.get("options") or [])
            if not pick:
                res.answers[label] = {"value": ans.value, "confidence": "unknown",
                                      "note": "stored answer doesn't match any option"}
                if req:
                    res.unresolved.append(label)
                continue
            _set_choice(page, f, pick)
            _record(res, label, Answer(pick, ans.confidence, ans.key, ans.note), req)
        else:
            loc.fill(ans.value)
            _record(res, label, ans, req)
    res.answers.pop("__resume", None)


def _set_choice(page, f: dict, option: str) -> None:
    if f["kind"] == "select":
        page.locator(f'[data-ja="{f["id"]}"]').select_option(label=option)
    elif f["kind"] == "radio":
        idx = f["options"].index(option)
        page.locator(f'[data-ja="{f["ids"][idx]}"]').check()


def _button(page, pattern: re.Pattern):
    for b in page.locator("button, input[type=submit], [role=button], a.button").all():
        try:
            if not b.is_visible():
                continue
            text = (b.inner_text() if b.evaluate("e => e.tagName") != "INPUT" else b.get_attribute("value")) or ""
            if pattern.match(text.strip()):
                return b
        except Exception:  # noqa: BLE001 - detached elements during re-render
            continue
    return None


def open_application(page, apply_url: str) -> None:
    page.goto(apply_url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    # Lever/Ashby job pages have an "Apply" link before the form.
    if not page.locator("input[type=file], form input[type=email]").count():
        btn = _button(page, re.compile(r"(?i)^\s*apply( for this job| now)?\s*$"))
        if btn:
            btn.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(1500)


def fill(page, answerer: Answerer, docs: dict, prev_applied: bool = False, max_steps: int = 8) -> FillResult:
    res = FillResult()
    for _ in range(max_steps):
        res.steps += 1
        if page.evaluate(CAPTCHA_JS):
            res.captcha = True
            return res
        _fill_page(page, answerer, docs, res, prev_applied)
        if _button(page, SUBMIT_BTN):
            res.submit_ready = True
            break
        nxt = _button(page, NEXT_BTN)
        if not nxt or res.unresolved:
            break
        nxt.click()
        page.wait_for_timeout(2000)
        errs = page.evaluate(ERRORS_JS)
        if errs:
            res.errors = errs
            break
    if page.evaluate(CAPTCHA_JS):
        res.captcha = True
    # final validation: required fields still empty
    for f in page.evaluate(COLLECT_JS):
        if f["required"] and f["kind"] not in ("checkbox", "file") and not f.get("value"):
            lbl = f["label"] or "(unlabelled)"
            if lbl not in res.unresolved:
                res.unresolved.append(lbl)
    return res


def submit_and_verify(page) -> tuple[str, str]:
    """Click submit and look for proof. Returns (status, evidence)."""
    btn = _button(page, SUBMIT_BTN)
    if not btn:
        return "failed", "submit button not found"
    before = page.url
    btn.click()
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(2500)
    body = page.inner_text("body")[:5000]
    m = CONFIRM_TXT.search(body)
    if m:
        return "submitted", f"confirmation text: '{m.group(0)}' at {page.url}"
    if re.search(r"(?i)confirm|thank|success|submitted", page.url) and page.url != before:
        return "submitted", f"redirected to {page.url}"
    errs = page.evaluate(ERRORS_JS)
    if errs:
        return "failed", "form errors after submit: " + " | ".join(errs[:3])
    return "submitted_unverified", f"no confirmation found; page now {page.url}"
