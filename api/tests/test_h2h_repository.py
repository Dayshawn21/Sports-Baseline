from app.repositories import matches


def test_orient_h2h_record_keeps_direct_order():
    oriented = matches._orient_h2h_record(10, 20, 10, 20, 3, 1)
    assert oriented == {"p1_wins": 3, "p2_wins": 1}


def test_orient_h2h_record_flips_reverse_order():
    oriented = matches._orient_h2h_record(10, 20, 20, 10, 3, 1)
    assert oriented == {"p1_wins": 1, "p2_wins": 3}


def test_orient_h2h_record_rejects_unrelated_row():
    oriented = matches._orient_h2h_record(10, 20, 30, 40, 3, 1)
    assert oriented is None
