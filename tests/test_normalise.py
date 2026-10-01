import pytest

from disclosures.normalise import normalise_entity


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Commonwealth Bank of Australia Ltd", "commonwealth bank of australia"),
        ("BHP Group Limited", "bhp group"),
        ("The Smith Family Trust", "smith family trust"),
        ("ANZ", "anz"),
        ("Smith & Sons Pty. Ltd.", "smith and sons"),
        ("ACME Holdings Pty Limited", "acme holdings"),
        ("Foo Co Pty Ltd", "foo"),  # suffixes stripped repeatedly
        ("Westpac Banking Corporation", "westpac banking"),
        ("Bendigo Bank", "bendigo bank"),
        ("  Ｗｏｏｌｗｏｒｔｈｓ   Group  ", "woolworths group"),  # NFKC + whitespace
        ("Rio Tinto plc", "rio tinto"),
        ("Ltd", "ltd"),  # never reduced to nothing
        ("", ""),
        (None, ""),
    ],
)
def test_normalise_entity(raw, expected):
    assert normalise_entity(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Delta pty.ltd", "delta"),           # full stop between words is a space
        ("A.N.Z.", "anz"),                     # dotted acronym: full stops deleted
        ("B.H.P", "bhp"),
        ("Qantas Airways Ltd.", "qantas airways"),
        ("St. George Bank", "st george bank"),
        ("Pty Ltd", "pty ltd"),                # suffix-only name kept whole
        ("PTY. LTD.", "pty ltd"),
        ("Co Ltd", "co ltd"),
    ],
)
def test_normalise_full_stops_and_suffix_only_names(raw, expected):
    assert normalise_entity(raw) == expected
