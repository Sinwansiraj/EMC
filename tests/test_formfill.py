from pathlib import Path

import pytest
import yaml

from job_agent import formfill
from job_agent.answers import Answerer

ROOT = Path(__file__).resolve().parent.parent
FORM = (Path(__file__).parent / "fixtures" / "form.html").resolve().as_uri()
PROFILE = yaml.safe_load((ROOT / "private" / "profile.yaml").read_text(encoding="utf-8"))

pw = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def docs(tmp_path):
    r = tmp_path / "resume.docx"
    r.write_bytes(b"x")
    c = tmp_path / "cover.docx"
    c.write_bytes(b"x")
    return {"resume_path": str(r), "cover_path": str(c), "cover_text": "Dear team", "resume_version": "test-1"}


def test_multistep_fill_flags_unknown_question(browser, docs):
    page = browser.new_page()
    page.goto(FORM)
    res = formfill.fill(page, Answerer(PROFILE), docs)
    a = res.answers
    assert res.steps == 2 and res.submit_ready and not res.captcha
    assert a["First Name *"]["value"] == "Mohammed"
    assert a["Resume/CV *"]["value"].startswith("[file]")
    assert a["What is your notice period? *"]["value"] == "Immediate"
    assert a["Will you now or in the future require visa sponsorship? *"]["value"] == "No"
    assert a["Gender"]["value"] == "Decline to self-identify"
    assert a["Subscribe me to the newsletter"]["value"] == "left unchecked"
    assert any("Why do you want to work at Acme" in u for u in res.unresolved)
    assert page.locator("#pp").is_checked() and not page.locator("#nl").is_checked()
    page.close()


def test_clean_form_submits_and_verifies(browser, docs):
    page = browser.new_page()
    page.goto(FORM + "#nowhy")
    page.reload()
    res = formfill.fill(page, Answerer(PROFILE), docs)
    assert res.unresolved == [] and res.submit_ready, res
    status, evidence = formfill.submit_and_verify(page)
    assert status == "submitted" and "Thank you" in evidence
    page.close()
