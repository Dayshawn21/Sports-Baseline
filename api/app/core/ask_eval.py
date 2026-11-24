"""Eval cases for Ask Lineform (47e): the data file's contract and its checks.

Cases run against live data, so a rule names the shape of a good answer (a game
link, "reference", "no games") rather than today's numbers. The runner in
`app.evals.ask` reads the file and calls the real loop; this module only
validates and judges, so the tool names arrive as an argument instead of being
imported from the service layer.
"""
from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from typing import get_args

from app.core.ask_messages import AskStop

FILE_VERSION = 1
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CASE_KEYS = frozenset({
    "id", "question", "expect_tools", "forbid_tools", "expect_no_tools",
    "tools_optional", "expect_stop", "must_match", "must_not_match", "notes",
})
STOPS: frozenset[str] = frozenset(get_args(AskStop))


class EvalFileError(ValueError):
    """The eval file is malformed; the message names the case and field."""


@dataclass(frozen=True)
class ToolExpectation:
    name: str
    input: Mapping[str, object]


@dataclass(frozen=True)
class EvalCase:
    id: str
    question: str
    expect_tools: tuple[ToolExpectation, ...] = ()
    forbid_tools: tuple[str, ...] = ()
    expect_no_tools: bool = False
    tools_optional: bool = False
    expect_stop: AskStop = "answered"
    must_match: tuple[str, ...] = ()
    must_not_match: tuple[str, ...] = ()
    notes: str = ""


def _strings(case_id: str, field: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise EvalFileError(f"{case_id}: {field} must be a list of strings")
    return tuple(value)


def _patterns(case_id: str, field: str, value: object) -> tuple[str, ...]:
    patterns = _strings(case_id, field, value)
    for pattern in patterns:
        try:
            re.compile(pattern)
        except re.error as error:
            raise EvalFileError(f"{case_id}: {field} has an invalid regex {pattern!r}: {error}") from error
    return patterns


def _tool_name(case_id: str, field: str, name: object, tool_names: Collection[str]) -> str:
    if not isinstance(name, str) or name not in tool_names:
        raise EvalFileError(f"{case_id}: {field} names unknown tool {name!r}")
    return name


def _expectations(case_id: str, value: object, tool_names: Collection[str]) -> tuple[ToolExpectation, ...]:
    if not isinstance(value, list):
        raise EvalFileError(f"{case_id}: expect_tools must be a list")
    expectations = []
    for item in value:
        if not isinstance(item, dict) or set(item) - {"name", "input"}:
            raise EvalFileError(f"{case_id}: expect_tools entries take only name and input")
        tool_input = item.get("input", {})
        if not isinstance(tool_input, dict):
            raise EvalFileError(f"{case_id}: expect_tools input must be an object")
        expectations.append(ToolExpectation(_tool_name(case_id, "expect_tools", item.get("name"), tool_names), tool_input))
    return tuple(expectations)


def _identity(raw: Mapping[str, object], index: int) -> tuple[str, str]:
    case_id = raw.get("id")
    if not isinstance(case_id, str) or not ID_PATTERN.match(case_id):
        raise EvalFileError(f"case {index}: id must be kebab-case, got {case_id!r}")
    question = raw.get("question")
    if not isinstance(question, str) or not question.strip():
        raise EvalFileError(f"{case_id}: question must be a non-empty string")
    unknown = sorted(set(raw) - CASE_KEYS)
    if unknown:
        raise EvalFileError(f"{case_id}: unknown keys {', '.join(unknown)}")
    return case_id, question.strip()


def _flag(case_id: str, raw: Mapping[str, object], field: str) -> bool:
    value = raw.get(field, False)
    if not isinstance(value, bool):
        raise EvalFileError(f"{case_id}: {field} must be true or false")
    return value


def parse_case(raw: object, index: int, tool_names: Collection[str]) -> EvalCase:
    if not isinstance(raw, dict):
        raise EvalFileError(f"case {index}: must be an object")
    case_id, question = _identity(raw, index)
    stop = raw.get("expect_stop", "answered")
    if stop not in STOPS:
        raise EvalFileError(f"{case_id}: expect_stop must be one of {', '.join(sorted(STOPS))}")
    no_tools = _flag(case_id, raw, "expect_no_tools")
    optional = _flag(case_id, raw, "tools_optional")
    notes = raw.get("notes", "")
    if not isinstance(notes, str):
        raise EvalFileError(f"{case_id}: notes must be a string")
    expect = _expectations(case_id, raw.get("expect_tools", []), tool_names)
    if no_tools and expect:
        raise EvalFileError(f"{case_id}: expect_no_tools conflicts with expect_tools")
    if optional and expect:
        raise EvalFileError(f"{case_id}: tools_optional conflicts with expect_tools")
    if optional and no_tools:
        raise EvalFileError(f"{case_id}: tools_optional conflicts with expect_no_tools")
    if not expect and not no_tools and not optional and stop == "answered":
        raise EvalFileError(f"{case_id}: an answered case needs expect_tools, expect_no_tools or tools_optional")
    forbid = tuple(_tool_name(case_id, "forbid_tools", name, tool_names)
                   for name in _strings(case_id, "forbid_tools", raw.get("forbid_tools", [])))
    return EvalCase(
        id=case_id, question=question, expect_tools=expect, forbid_tools=forbid,
        expect_no_tools=no_tools, tools_optional=optional, expect_stop=stop,
        must_match=_patterns(case_id, "must_match", raw.get("must_match", [])),
        must_not_match=_patterns(case_id, "must_not_match", raw.get("must_not_match", [])),
        notes=notes,
    )


def parse_cases(raw: object, tool_names: Collection[str]) -> list[EvalCase]:
    """Validate a decoded eval file. An empty case list is an error, so a run
    that checked nothing can never read as passing."""
    if not isinstance(raw, dict) or raw.get("version") != FILE_VERSION:
        raise EvalFileError(f'eval file must be an object with "version": {FILE_VERSION}')
    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise EvalFileError("eval file has no cases")
    cases = [parse_case(item, index, tool_names) for index, item in enumerate(raw_cases)]
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise EvalFileError(f"{case.id}: duplicate id")
        seen.add(case.id)
    return cases


LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
# Thousands separators first, so "1,593" is one number rather than "1" and "593".
NUMBER = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])\d+(?:\.\d+)?")


@dataclass(frozen=True)
class ToolCallView:
    name: str
    input: Mapping[str, object]
    is_error: bool
    content: str


@dataclass(frozen=True)
class OutcomeView:
    text: str
    stop: str
    tool_calls: tuple[ToolCallView, ...]


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    failures: tuple[str, ...]
    ungrounded_numbers: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def _describe(expectation: ToolExpectation) -> str:
    if not expectation.input:
        return expectation.name
    pairs = ", ".join(f"{key}={value!r}" for key, value in expectation.input.items())
    return f"{expectation.name}({pairs})"


def _matches(expectation: ToolExpectation, call: ToolCallView) -> bool:
    """Subset match: extra arguments on the call never fail an expectation."""
    return call.name == expectation.name and all(
        key in call.input and call.input[key] == value for key, value in expectation.input.items()
    )


def tool_failures(case: EvalCase, calls: tuple[ToolCallView, ...]) -> list[str]:
    if case.expect_no_tools and calls:
        return [f"expected no tools, called {', '.join(call.name for call in calls)}"]
    failures = [
        f"missing tool {_describe(expectation)}"
        for expectation in case.expect_tools
        if not any(_matches(expectation, call) for call in calls)
    ]
    called = {call.name for call in calls}
    failures += [f"forbidden tool {name} called" for name in case.forbid_tools if name in called]
    return failures


def text_failures(case: EvalCase, text: str) -> list[str]:
    failures = [
        f"must_match /{pattern}/ not found"
        for pattern in case.must_match
        if not re.search(pattern, text, re.IGNORECASE)
    ]
    for pattern in case.must_not_match:
        found = re.search(pattern, text, re.IGNORECASE)
        if found:
            failures.append(f"must_not_match /{pattern}/ found {found.group(0)!r}")
    return failures


def link_failures(text: str, contents: tuple[str, ...]) -> list[str]:
    """Every link must be a Lineform path a tool returned this run, the same
    rule the system prompt gives the model."""
    failures = []
    for target in LINK.findall(text):
        if not target.startswith("/") or target.startswith("//"):
            failures.append(f"link {target} is not an internal path")
        elif not any(target in content for content in contents):
            failures.append(f"link {target} is in no tool result")
    return failures


def _number_in(number: str, source: str) -> bool:
    return re.search(rf"(?<![\d.]){re.escape(number)}(?!\.?\d)", source) is not None


def ungrounded_numbers(text: str, sources: tuple[str, ...]) -> tuple[str, ...]:
    """Numbers in the answer that no source contains. Only multi-digit or
    decimal numbers count: "3 games" and "top 5" are the model's own counting.
    Informational, since rounding or a percent from a 0-1 rate also lands here."""
    found = []
    for raw in NUMBER.findall(text):
        number = raw.replace(",", "")
        if len(number.replace(".", "")) < 2 and "." not in number:
            continue
        if not any(_number_in(number, source) or _number_in(raw, source) for source in sources) and raw not in found:
            found.append(raw)
    return tuple(found)


def check_case(case: EvalCase, outcome: OutcomeView) -> CaseResult:
    contents = tuple(call.content for call in outcome.tool_calls)
    failures = []
    if outcome.stop != case.expect_stop:
        failures.append(f"stop: expected {case.expect_stop}, got {outcome.stop}")
    failures += tool_failures(case, outcome.tool_calls)
    failures += text_failures(case, outcome.text)
    failures += link_failures(outcome.text, contents)
    return CaseResult(
        case_id=case.id,
        failures=tuple(failures),
        ungrounded_numbers=ungrounded_numbers(outcome.text, (*contents, case.question)),
    )
