from app.libtype import classify, keep_latest


def test_names_pick_types():
    assert classify("workspace/weekly-report/status/scr-extre-2026-10-12.md") == "대본"
    assert classify("workspace/weekly-report/status/⭐scr-extre-2026-06-29-전사과제.md") == "대본"
    assert classify("workspace/cms/docs/2026-08-13-조건부쿠폰-발급방식-학습노트.md") == "학습"
    assert classify("workspace/strategy/docs/25-fx-settlement-walkthrough.ko.md") == "학습"
    assert classify("workspace/cms/docs/2026-10-22-GB-156-유관미팅-준비.md") == "조사"
    assert classify("workspace/manage/drafts/1on1/2026-08-04-진-조직변경.md") == "대본"
    assert classify("workspace/cms/docs/scr/2026-06-18-15시-선착순포인트-API공유.md") == "대본"


def test_false_friends_stay_out():
    for rel in [
        "workspace/strategy/docs/39-overseas-tour-cs-guide-master.ko.md",  # guided
        "workspace/cms/docs/2026-10-19-메모리-코드대조.md",
        "workspace/yeogithon/docs/scorecard.md",
        "workspace/cms/docs/2026-08-27-조건부쿠폰-9월7일-발급준비.md",
        "workspace/cms/docs/0-★-2026-10-01-부재대비-자동화점검-oof무장-세션-인계.md",
        "workspace/marketing/contexts/guidetour/pool/transcripts.md",
        "workspace/strategy/docs/15-gyg-meeting-debrief.ko.md",
        "workspace/manage/drafts/1on1/records/2026-11-04-진.md",
        "workspace/weekly-report/status/sources/scr-extre-2026-09-21.prev.md",
        "workspace/manage/drafts/upward/2026-10-15-mc-report-scr-remote.v5-backup.md",
        "code/gts/gts-ssot/docs/validation/x/_brief.md",
        ".claude/skills/scr/SKILL.md",
        "workspace/x/archive/대본.md",
    ]:
        assert classify(rel) is None, rel


def test_keep_latest_version_only():
    d = "workspace/manage/drafts/decks/pc/"
    got = keep_latest([d + "대본-21판.md", d + "대본-36판.md", d + "대본-4판.md", d + "엔진.md"])
    assert sorted(got) == [d + "대본-36판.md", d + "엔진.md"]


def test_generated_and_harness_paths_excluded():
    from app.libtype import excluded
    assert excluded(".claude/logs/kdc-autofix/20261104-발언대본.md")
    assert excluded("workspace/cms/tools/prd-pipeline/out/meeting-brief.md")
    assert not excluded("workspace/cms/docs/0-★-2026-11-04-조건부쿠폰-연동협의-대본.md")
