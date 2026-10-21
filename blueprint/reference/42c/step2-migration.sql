CREATE TABLE nba_injury_snapshots (
    id BIGSERIAL NOT NULL,
    fetched_at TIMESTAMP WITH TIME ZONE NOT NULL,
    source TEXT NOT NULL,
    source_timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    entry_count INTEGER NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT ck_nba_injury_source CHECK (source = 'ESPN'),
    CONSTRAINT ck_nba_injury_count CHECK (entry_count >= 0),
    UNIQUE (fetched_at)
);

CREATE TABLE nba_player_injuries (
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
    PRIMARY KEY (snapshot_id, espn_team_id, espn_athlete_id),
    FOREIGN KEY(snapshot_id) REFERENCES nba_injury_snapshots (id)
);
