import pytest

from app.core.ask_eval import (
    EvalCase,
    EvalFileError,
    OutcomeView,
    ToolCallView,
    ToolExpectation,
    check_case,
    link_failures,
    parse_cases,
    ungrounded_numbers,
)

TOOLS = {"get_slate", "get_top_props", "get_game_detail", "get_player", "get_model_track_record", "find"}


def case(**fields: object) -> dict[str, object]:
    return {"id": "nba-slate", "question": "Who plays tonight?", "expect_tools": [{"name": "get_slate"}], **fields}


def parse(*cases: object) -> list[EvalCase]:
    return parse_cases({"version": 1, "cases": list(cases)}, TOOLS)


def rejects(message: str, *cases: object) -> None:
    with pytest.raises(EvalFileError, match=message):
        parse(*cases)


def test_parses_a_full_case():
    [parsed] = parse({
        "id": "nba-best-bet-honesty",
        "question": "  What's the best NBA bet tonight?  ",
        "expect_tools": [{"name": "get_top_props", "input": {"sport": "nba"}}],
        "forbid_tools": ["get_player"],
        "expect_stop": "answered",
        "must_match": ["reference|not (a )?validated"],
        "must_not_match": [r"\block\b"],
        "notes": "NBA has no validated picks.",
    })
    assert parsed == EvalCase(
        id="nba-best-bet-honesty",
        question="What's the best NBA bet tonight?",
        expect_tools=(ToolExpectation("get_top_props", {"sport": "nba"}),),
        forbid_tools=("get_player",),
        must_match=("reference|not (a )?validated",),
        must_not_match=(r"\block\b",),
        notes="NBA has no validated picks.",
    )


def test_defaults_fill_optional_fields():
    [parsed] = parse(case())
    assert parsed.expect_tools == (ToolExpectation("get_slate", {}),)
    assert parsed.expect_stop == "answered"
    assert parsed.forbid_tools == parsed.must_match == parsed.must_not_match == ()
    assert parsed.expect_no_tools is False


def test_a_no_tools_case_needs_no_expectations():
    [parsed] = parse({"id": "off-topic", "question": "Who won the 1998 World Series?", "expect_no_tools": True})
    assert parsed.expect_no_tools and parsed.expect_tools == ()


def test_a_non_answered_stop_needs_no_expectations():
    [parsed] = parse({"id": "refused", "question": "q", "expect_stop": "refused"})
    assert parsed.expect_stop == "refused"


@pytest.mark.parametrize("raw", [[], {}, {"version": 2, "cases": [case()]}, {"version": 1, "cases": []}])
def test_rejects_an_empty_or_unversioned_file(raw: object):
    with pytest.raises(EvalFileError):
        parse_cases(raw, TOOLS)


def test_rejects_a_bad_id():
    rejects("case 0: id must be kebab-case", case(id="NBA Slate"))
    rejects("case 0: id must be kebab-case", {"question": "q", "expect_no_tools": True})


def test_rejects_a_duplicate_id():
    rejects("nba-slate: duplicate id", case(), case())


def test_rejects_an_empty_question():
    rejects("nba-slate: question must be a non-empty string", case(question="   "))


def test_rejects_unknown_keys():
    rejects("nba-slate: unknown keys must_contain", case(must_contain=["x"]))


def test_rejects_unknown_tools():
    rejects("nba-slate: expect_tools names unknown tool 'get_odds'", case(expect_tools=[{"name": "get_odds"}]))
    rejects("nba-slate: forbid_tools names unknown tool 'get_nhl'", case(forbid_tools=["get_nhl"]))


def test_rejects_a_malformed_expectation():
    rejects("expect_tools entries take only name and input", case(expect_tools=[{"name": "find", "args": {}}]))
    rejects("expect_tools input must be an object", case(expect_tools=[{"name": "find", "input": "nba"}]))


def test_rejects_an_unknown_stop():
    rejects("nba-slate: expect_stop must be one of", case(expect_stop="done"))


def test_rejects_an_invalid_regex():
    rejects(r"nba-slate: must_not_match has an invalid regex '\(lock'", case(must_not_match=["(lock"]))


def test_rejects_non_string_patterns():
    rejects("nba-slate: must_match must be a list of strings", case(must_match="reference"))


def test_an_answered_case_must_say_what_tools_it_expects():
    rejects("nba-slate: an answered case needs expect_tools or expect_no_tools", case(expect_tools=[]))


def test_rejects_no_tools_with_expected_tools():
    rejects("nba-slate: expect_no_tools conflicts with expect_tools", case(expect_no_tools=True))


SLATE_JSON = '{"tool": "get_slate", "url": "/nba?date=2026-10-28", "data": [{"url": "/nba/game/21265", "spread": -3.5}]}'


def call(name: str = "get_slate", content: str = SLATE_JSON, **tool_input: object) -> ToolCallView:
    return ToolCallView(name=name, input=tool_input, is_error=False, content=content)


def outcome(text: str = "Two games tonight.", stop: str = "answered", *calls: ToolCallView) -> OutcomeView:
    return OutcomeView(text=text, stop=stop, tool_calls=calls)


def evaluate(text: str = "Two games tonight.", *calls: ToolCallView, stop: str = "answered", **fields: object):
    [parsed] = parse(case(**fields))
    return check_case(parsed, outcome(text, stop, *calls))


def test_a_matching_answer_passes():
    result = evaluate("[Celtics at Knicks](/nba/game/21265), Knicks -3.5.", call(sport="nba", date="2026-10-28"),
                      expect_tools=[{"name": "get_slate", "input": {"sport": "nba"}}], must_match=["/nba/game/"])
    assert result.passed and result.failures == () and result.case_id == "nba-slate"


def test_a_wrong_stop_fails():
    assert evaluate("", call(), stop="truncated").failures == ("stop: expected answered, got truncated",)


def test_expected_input_is_a_subset_match():
    expect = [{"name": "get_slate", "input": {"sport": "nba"}}]
    assert evaluate("x", call(sport="nba", date="2026-10-28"), expect_tools=expect).passed
    assert evaluate("x", call(sport="nfl"), expect_tools=expect).failures == ("missing tool get_slate(sport='nba')",)
    assert evaluate("x", call(date="2026-10-28"), expect_tools=expect).failures == (
        "missing tool get_slate(sport='nba')",
    )


def test_extra_and_out_of_order_calls_never_fail():
    expect = [{"name": "get_slate"}, {"name": "find"}]
    assert evaluate("x", call("find", "{}"), call(), call("get_player", "{}"), expect_tools=expect).passed


def test_a_forbidden_tool_fails():
    result = evaluate("x", call(), call("get_player", "{}"), forbid_tools=["get_player"])
    assert result.failures == ("forbidden tool get_player called",)


def test_expect_no_tools_fails_on_any_call():
    [parsed] = parse({"id": "off-topic", "question": "q", "expect_no_tools": True})
    assert check_case(parsed, outcome("I only cover Lineform.")).passed
    assert check_case(parsed, outcome("x", "answered", call("find", "{}"), call())).failures == (
        "expected no tools, called find, get_slate",
    )


def test_text_rules_are_case_insensitive_regexes():
    rules = {"must_match": ["reference|not validated"], "must_not_match": [r"\block\b"]}
    assert evaluate("These are REFERENCE gaps.", call(), **rules).passed
    assert evaluate("A LOCK tonight.", call(), **rules).failures == (
        "must_match /reference|not validated/ not found",
        r"must_not_match /\block\b/ found 'LOCK'",
    )
    assert evaluate("Reference only; blocks 1.5 is a gap.", call(), **rules).passed


def test_links_must_be_internal_paths_a_tool_returned():
    contents = (SLATE_JSON,)
    assert link_failures("[game](/nba/game/21265) and [slate](/nba?date=2026-10-28)", contents) == []
    assert link_failures("[game](/nba/game/99999)", contents) == ["link /nba/game/99999 is in no tool result"]
    assert link_failures("[espn](https://espn.com/nba)", contents) == [
        "link https://espn.com/nba is not an internal path"
    ]
    assert link_failures("[x](//evil.example/nba/game/21265)", contents) == [
        "link //evil.example/nba/game/21265 is not an internal path"
    ]
    assert link_failures("No links here.", contents) == []


def test_a_link_failure_fails_the_case():
    assert evaluate("[game](/nba/game/1)", call()).failures == ("link /nba/game/1 is in no tool result",)


def test_ungrounded_numbers_skip_small_counts_and_match_signed_odds():
    sources = ('{"price": -110, "hit_rate": 57.7, "line": 1.5, "picks": 1593}',)
    text = "3 games: -110 and +110, a 57.7% hit rate on 1,593 picks over 1.5, and 4 of 5."
    assert ungrounded_numbers(text, sources) == ()


def test_ungrounded_numbers_reports_numbers_no_source_holds():
    sources = ('{"hit_rate": 0.577, "line": 21.5, "total": 215}',)
    text = "57.7% on 21.5, not 21, and 21.5 again; 2.5 too."
    assert ungrounded_numbers(text, sources) == ("57.7", "21", "2.5")


def test_numbers_from_the_question_are_grounded():
    result = evaluate("Over 24.5 points.", call(content="{}"), question="Is 24.5 points a good line?")
    assert result.ungrounded_numbers == ()
    assert result.passed
