BEGIN;

-- Running upgrade 0049 -> 0050

CREATE TABLE nhl_context_snapshots (
    id BIGSERIAL NOT NULL,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    scope_date DATE,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
    source_timestamp TIMESTAMP WITH TIME ZONE,
    entry_count INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT uq_nhl_context_batch UNIQUE NULLS NOT DISTINCT (source, kind, scope_date, fetched_at),
    CONSTRAINT ck_nhl_context_source CHECK (source = 'ESPN'),
    CONSTRAINT ck_nhl_context_count CHECK (entry_count >= 0),
    CONSTRAINT ck_nhl_context_scope CHECK ((kind = 'injuries' AND scope_date IS NULL AND source_timestamp IS NOT NULL) OR (kind = 'goalies' AND scope_date IS NOT NULL))
);

CREATE INDEX ix_nhl_context_latest ON nhl_context_snapshots (kind, scope_date, fetched_at DESC, id DESC);

CREATE TABLE nhl_player_injuries (
    snapshot_id BIGINT NOT NULL,
    espn_team_id TEXT NOT NULL,
    team_code VARCHAR(8) NOT NULL,
    espn_athlete_id TEXT NOT NULL,
    player_name TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    source_updated_at TIMESTAMP WITH TIME ZONE,
    return_date TEXT,
    athlete_team_id TEXT,
    player_id BIGINT,
    link_reason TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, espn_team_id, espn_athlete_id),
    CONSTRAINT ck_nhl_injury_link_reason CHECK (link_reason IN ('matched', 'no_candidate', 'ambiguous', 'team_mismatch', 'missing_team', 'position_mismatch', 'not_reported')),
    CONSTRAINT ck_nhl_injury_link CHECK ((player_id IS NOT NULL) = (link_reason = 'matched')),
    FOREIGN KEY(snapshot_id) REFERENCES nhl_context_snapshots (id),
    FOREIGN KEY(player_id) REFERENCES sport_players (id)
);

CREATE INDEX ix_nhl_injury_snapshot_team ON nhl_player_injuries (snapshot_id, team_code);

CREATE TABLE nhl_goalie_observations (
    snapshot_id BIGINT NOT NULL,
    espn_event_id TEXT NOT NULL,
    event_date DATE NOT NULL,
    start_utc TIMESTAMP WITH TIME ZONE NOT NULL,
    time_valid BOOLEAN NOT NULL,
    home_team VARCHAR(8) NOT NULL,
    away_team VARCHAR(8) NOT NULL,
    espn_team_id TEXT NOT NULL,
    team_code VARCHAR(8) NOT NULL,
    espn_athlete_id TEXT,
    player_name TEXT,
    status TEXT NOT NULL,
    raw_status TEXT,
    athlete_team_id TEXT,
    source_position TEXT,
    player_id BIGINT,
    player_link_reason TEXT NOT NULL,
    game_id BIGINT,
    game_link_reason TEXT NOT NULL,
    PRIMARY KEY (snapshot_id, espn_event_id, espn_team_id),
    CONSTRAINT ck_nhl_goalie_status CHECK (status IN ('expected', 'confirmed', 'unknown', 'not_reported')),
    CONSTRAINT ck_nhl_goalie_player_reason CHECK (player_link_reason IN ('matched', 'no_candidate', 'ambiguous', 'team_mismatch', 'missing_team', 'position_mismatch', 'not_reported')),
    CONSTRAINT ck_nhl_goalie_game_reason CHECK (game_link_reason IN ('matched', 'no_game', 'ambiguous', 'missing_start', 'start_mismatch')),
    CONSTRAINT ck_nhl_goalie_player_link CHECK ((player_id IS NOT NULL) = (player_link_reason = 'matched')),
    CONSTRAINT ck_nhl_goalie_game_link CHECK ((game_id IS NOT NULL) = (game_link_reason = 'matched')),
    CONSTRAINT ck_nhl_goalie_time_valid CHECK (time_valid OR game_id IS NULL),
    CONSTRAINT ck_nhl_goalie_teams CHECK (home_team <> away_team AND team_code IN (home_team, away_team)),
    CONSTRAINT ck_nhl_goalie_announcement CHECK ((status = 'not_reported' AND espn_athlete_id IS NULL AND player_name IS NULL AND raw_status IS NULL AND athlete_team_id IS NULL AND source_position IS NULL AND player_link_reason = 'not_reported') OR (status <> 'not_reported' AND espn_athlete_id IS NOT NULL AND player_name IS NOT NULL AND raw_status IS NOT NULL AND player_link_reason <> 'not_reported')),
    FOREIGN KEY(snapshot_id) REFERENCES nhl_context_snapshots (id),
    FOREIGN KEY(player_id) REFERENCES sport_players (id),
    FOREIGN KEY(game_id) REFERENCES sport_games (id)
);

CREATE INDEX ix_nhl_goalie_snapshot_game ON nhl_goalie_observations (snapshot_id, game_id, team_code);

UPDATE alembic_version SET version_num='0050' WHERE alembic_version.version_num = '0049';

COMMIT;
