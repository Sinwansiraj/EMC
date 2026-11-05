from job_agent.seekers import readiness


def test_ready_when_every_targeted_role_has_a_resume():
    r = readiness(["data_analyst", "data_scientist"], ["data_analyst", "data_scientist"])
    assert r["ready"] is True
    assert r["missing"] == []
    assert set(r["covered"]) == {"data_analyst", "data_scientist"}


def test_blocked_when_a_targeted_role_lacks_a_resume():
    r = readiness(
        ["data_analyst", "data_scientist", "customer_support_mgmt"],
        ["data_analyst", "data_scientist"],
    )
    assert r["ready"] is False
    assert r["missing"] == ["customer_support_mgmt"]


def test_not_ready_without_any_target():
    assert readiness([], ["data_analyst"])["ready"] is False


def test_targets_dedup_and_report_extra_resumes():
    r = readiness(["data_analyst", "data_analyst"], ["data_analyst", "prompt_engineer"])
    assert r["targets"] == ["data_analyst"]
    assert r["ready"] is True
    assert r["extra"] == ["prompt_engineer"]
