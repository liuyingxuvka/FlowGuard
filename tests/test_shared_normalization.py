from flowguard._normalization import (
    canonical_json_text,
    nonempty_string_sequence,
    string_sequence,
    string_set,
    unique_sorted_strings,
)


def test_string_sequence_preserves_the_replaced_private_helper_contract():
    assert string_sequence(None) == ()
    assert string_sequence(("first", "", 2)) == ("first", "", "2")
    assert string_sequence("ab") == ("a", "b")


def test_shared_normalizers_preserve_each_replaced_private_contract():
    assert nonempty_string_sequence(None) == ()
    assert nonempty_string_sequence(("first", "", 2)) == ("first", "2")
    assert string_set(("first", "first", 2)) == {"first", "2"}
    assert unique_sorted_strings(("b", "", "a", "b")) == ("a", "b")
    assert canonical_json_text({"b": 2, "a": "é"}) == '{"a":"é","b":2}'
