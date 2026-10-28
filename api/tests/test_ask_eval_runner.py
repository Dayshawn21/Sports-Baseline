import asyncio
import datetime as dt
import json
from contextlib import asynccontextmanager

import anthropic
import pytest

from app.core.ask_cost import AskPrices
from app.core.ask_eval import EvalCase, ToolExpectation
from app.core.ask_messages import AskUsage
from app.evals import ask as runner
from app.services.ask import tools
from app.services.ask.loop import AskOutcome, ToolCallRecord
from tests.test_ask_loop import SETTINGS, FakeClient, _message, _text, _tool_result, _tool_use

NOW = dt.datetime(2026, 10, 28, 19, 40, tzinfo=dt.UTC)
PRICES = AskPrices(input=1.0, output=10.0, cache_read=0.1, cache_write=1.25)
SLATE = EvalCase(
    id="nba-slate", question="Who plays tonight?",
    expect_tools=(ToolExpectation("get_slate", {"sport": "nba"}),), must_match=("/nba",),
)
OFF_TOPIC = EvalCase(id="off-topic", question="Who won in 1998?", expect_no_tools=True)


class Overloaded(anthropic.APIError):
    def __init__(self):
        Exception.__init__(self, "overloaded")


def scripted(outcomes):
    """An Answer that replays outcomes by case id, adding usage like the real loop."""
    async def answer(case, usage):
        outcome = outcomes[case.id]
        usage.requests += 1
        usage.input_tokens += 1_000
        usage.output_tokens += 100
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    return answer


def slate_outcome(text, content='{"url": "/nba/game/7"}'):
    call = ToolCallRecord(name="get_slate", input={"sport": "nba"}, is_error=False, ms=5, content=content)
    return AskOutcome(text=text, stop="answered", tool_calls=[call])


def run_all(cases, answer):
    async def collect():
        return [run async for run in runner.run_cases(cases, answer, PRICES)]
    return asyncio.run(collect())


def test_the_real_question_file_validates():
    cases = runner.load_cases()
    assert [case.id for case in cases][:2] == ["nba-slate-tonight", "off-topic-world-series"]


def test_a_broken_question_file_is_a_setup_error(tmp_path):
    path = tmp_path / "q.json"
    path.write_text('{"version": 1, "cases": []}', encoding="utf-8")
    with pytest.raises(runner.SetupError, match="q.json: eval file has no cases"):
        runner.load_cases(path)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(runner.SetupError, match="cannot read q.json"):
        runner.load_cases(path)


def test_only_selects_a_subset_in_file_order():
    assert runner.select_cases([SLATE, OFF_TOPIC], "off-topic, nba-slate") == [SLATE, OFF_TOPIC]
    assert runner.select_cases([SLATE, OFF_TOPIC], "off-topic") == [OFF_TOPIC]
    assert runner.select_cases([SLATE, OFF_TOPIC], None) == [SLATE, OFF_TOPIC]


def test_only_rejects_unknown_ids():
    with pytest.raises(runner.SetupError, match="unknown cases: nope"):
        runner.select_cases([SLATE], "nba-slate,nope")


def test_a_passing_and_a_failing_case():
    answer = scripted({
        "nba-slate": slate_outcome("Two games: [Celtics at Knicks](/nba/game/7)."),
        "off-topic": slate_outcome("The Yankees."),
    })
    passed, failed = run_all([SLATE, OFF_TOPIC], answer)

    assert passed.passed and passed.error is None
    assert passed.cost_usd == pytest.approx(0.002)  # 1,000 input at $1 + 100 output at $10 per million
    assert not failed.passed
    assert failed.result.failures == ("expected no tools, called get_slate",)


def test_an_api_error_marks_the_case_and_the_run_continues():
    answer = scripted({"nba-slate": Overloaded(), "off-topic": AskOutcome(text="Only Lineform.", stop="answered")})
    errored, passed = run_all([SLATE, OFF_TOPIC], answer)

    assert errored.error == "Overloaded: overloaded" and not errored.passed
    assert errored.usage.requests == 1 and errored.cost_usd > 0  # tokens before the failure still count
    assert passed.passed


def test_case_lines_show_status_failures_and_ungrounded_numbers():
    [run] = run_all([SLATE], scripted({"nba-slate": slate_outcome("No games, but 57.7% at /nba.")}))
    assert runner.format_case(run) == (
        "PASS nba-slate  answered  tools: get_slate  1 req  1,100 tok  $0.0020\n"
        "    ? ungrounded numbers: 57.7"
    )
    [failed] = run_all([SLATE], scripted({"nba-slate": slate_outcome("Nothing.")}))
    assert runner.format_case(failed).splitlines()[1:] == ["    - must_match //nba/ not found"]
    [errored] = run_all([SLATE], scripted({"nba-slate": Overloaded()}))
    assert runner.format_case(errored) == "ERROR nba-slate\n    ! Overloaded: overloaded"


def test_the_summary_totals_every_case():
    runs = run_all([SLATE, OFF_TOPIC], scripted({
        "nba-slate": slate_outcome("[game](/nba/game/7)"), "off-topic": Overloaded(),
    }))
    assert runner.format_summary(runs, "claude-haiku-5-5", NOW) == (
        "Passed 1 of 2 (1 error)\n"
        "Requests 2, input 2,000, output 200, cache read 0, cache write 0\n"
        "Estimated cost $0.0040\n"
        "Run 2026-10-28 2:40 PM CT, model claude-haiku-5-5"
    )


def test_exit_code_is_zero_only_when_every_case_passed():
    good = run_all([SLATE], scripted({"nba-slate": slate_outcome("[game](/nba/game/7)")}))
    bad = run_all([SLATE], scripted({"nba-slate": Overloaded()}))
    assert runner.exit_code(good) == 0
    assert runner.exit_code(good + bad) == 1
    assert runner.exit_code([]) == 1


def test_results_json_keeps_answers_but_not_tool_content():
    runs = run_all([SLATE], scripted({"nba-slate": slate_outcome("[game](/nba/game/7)", content='{"url": "/nba/game/7", "rows": "SECRET-ROWS"}')}))
    data = runner.results_json(runs, "claude-haiku-5-5", NOW)
    assert data["passed"] == 1 and data["total"] == 1 and data["cost_usd"] == 0.002
    [case] = data["cases"]
    assert case["answer"] == "[game](/nba/game/7)"
    assert case["tool_calls"] == [{"name": "get_slate", "input": {"sport": "nba"}, "is_error": False}]
    assert "SECRET-ROWS" not in json.dumps(data)


def test_make_answer_runs_the_real_loop_in_a_fresh_session(monkeypatch):
    async def get_slate(inp, ctx):
        return _tool_result("get_slate", inp.sport)

    monkeypatch.setitem(tools.EXECUTORS, "get_slate", get_slate)
    sessions = []

    @asynccontextmanager
    async def session_factory():
        sessions.append("opened")
        yield None

    client = FakeClient(
        _message(_tool_use("toolu_1", "get_slate", {"sport": "nba"}), stop="tool_use"),
        _message(_text("Tonight: [the slate](/nba).")),
    )
    answer = runner.make_answer(client, SETTINGS, session_factory, None, NOW)
    [run] = run_all([SLATE], answer)

    assert run.passed, run.result
    assert sessions == ["opened"]
    assert run.usage.requests == 2
    assert run.outcome.tool_calls[0].content == _tool_result("get_slate", "nba").model_dump_json()


def test_dry_run_lists_the_seed_cases_without_calling_the_api(capsys, monkeypatch):
    monkeypatch.setattr(runner, "make_client", lambda _: pytest.fail("dry run built a client"))
    assert runner.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "nba-slate-tonight: Who plays in the NBA tonight?" in out
    assert "off-topic-world-series: Who won the 1998 World Series?" in out
    assert "no API call made" in out


def test_a_real_run_needs_confirm_spend(capsys):
    assert runner.main([]) == 2
    assert "--confirm-spend" in capsys.readouterr().err


def test_an_unknown_only_id_exits_before_any_spend(capsys):
    assert runner.main(["--confirm-spend", "--only", "nope"]) == 2
    assert "unknown cases: nope" in capsys.readouterr().err


def test_a_missing_key_exits_two(capsys, monkeypatch):
    monkeypatch.setattr(runner, "settings", SETTINGS.model_copy(update={"anthropic_api_key": ""}))
    assert runner.main(["--confirm-spend", "--only", "nba-slate-tonight"]) == 2
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().err
