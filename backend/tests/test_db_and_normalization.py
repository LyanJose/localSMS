from localsms.db import address_digits, compute_dedup_hash, fold, thread_key


def test_fold_removes_accents_and_case():
    assert fold("Élève Café ÇA") == "eleve cafe ca"


def test_thread_key_groups_number_formats():
    keys = {thread_key(a) for a in ("0321234567", "+261 32 12 345 67", "+261-32-12-345-67", "00261321234567")}
    assert len(keys) == 1


def test_thread_key_alphanumeric_sender():
    assert thread_key("ORANGE") == thread_key("orange ")
    assert thread_key("ORANGE") != thread_key("0321234567")


def test_address_digits():
    assert address_digits("+261 (32) 12-345") == "26132 12345".replace(" ", "")


def test_dedup_hash_stable_and_sensitive():
    a = compute_dedup_hash("n:1", 1, "in", "x")
    assert a == compute_dedup_hash("n:1", 1, "in", "x")
    assert a != compute_dedup_hash("n:1", 2, "in", "x")
    assert a != compute_dedup_hash("n:1", 1, "out", "x")
