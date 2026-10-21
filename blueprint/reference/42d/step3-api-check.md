# 42d Step 3 API check

Date: 2026-10-21. Scope: API assembly and response serialization.

Exercised `app.main.app` through FastAPI TestClient, with fixed data from
`api/tests/test_nba_team_stats_context.py` and an overridden `get_db` dependency.
The application lifespan ran. Repository methods were mocked; no shared
database connection or provider request was needed. This does not establish
real database query performance or hosted deployment behavior.

| Endpoint | Populated history | Empty history |
|---|---|---|
| `/nba/games/1` | 200 | 200 |
| `/nba/games/1/props` | 200 | 200 |
| `/nba/games/1/line-only-props` | 200 | 200 |
| `/nba/props?date=2026-11-01` | 200 | 200 |

For each history case, all four `teamStats` objects were equal. Populated
history showed BOS at 100.0 points/game; empty history showed null, with both
team objects retained. All three `/nba/games/999` routes returned 404 after
the game repository was set to return no game.

Assembly tests additionally compare complete prop arrays and prior fields
against the context-free builders, preserve probabilities/flags/versions,
check date-wide batching and verify the `for` and `threes_made` wire keys.

Final Verify passed: 673 web tests, production build, 3,611 API tests.
The existing large-bundle and Starlette/AnyIO deprecation warnings remain.
