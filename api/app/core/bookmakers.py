MAX_BOOKMAKER_COUNT = 30


def normalize_bookmaker_scope(value: str) -> tuple[str, ...]:
    """Return a deduplicated provider bookmaker scope, preserving first use."""
    names = [name.strip() for name in value.split(",") if name.strip()]
    if not names:
        raise ValueError("At least one bookmaker is required.")

    scope: list[str] = []
    seen: set[str] = set()
    for name in names:
        key = name.casefold()
        if key not in seen:
            scope.append(name)
            seen.add(key)

    if len(scope) > MAX_BOOKMAKER_COUNT:
        raise ValueError(f"At most {MAX_BOOKMAKER_COUNT} bookmakers are allowed.")
    return tuple(scope)


def bookmaker_scope_param(value: str) -> str:
    """Normalize a bookmaker scope for a provider request parameter."""
    return ",".join(normalize_bookmaker_scope(value))
