import pytest

from app.grounding import check_numbers, check_quote, normalize, number_matches, numbers_in, quote_score
from app.upload import PageText, StoredDoc


def ar(*codes: int) -> str:
    return "".join(chr(c) for c in codes)


def test_arabic_indic_and_extended_digits():
    assert normalize(ar(0x661, 0x662, 0x663)) == "123"
    assert normalize(ar(0x6F4, 0x6F5)) == "45"


def test_arabic_separators_and_percent():
    # ١٧٫٩٪  -> 17.9%   and   ١٬٠٠٠ -> 1000
    assert normalize(ar(0x661, 0x667, 0x66B, 0x669, 0x66A)) == "17.9%"
    assert normalize(ar(0x661, 0x66C, 0x660, 0x660, 0x660)) == "1000"
    assert normalize("1,000 and 2,5") == "1000 and 2,5"


def test_tashkeel_tatweel_and_letter_unification():
    word = "مُحَمَّد"  # مُحَمَّد
    assert normalize(word) == "محمد"
    assert normalize("كــتاب") == "كتاب"  # tatweel
    assert normalize("أإآ") == "ااا"
    assert normalize("ى") == "ي" and normalize("ة") == "ه"


def test_presentation_forms_fold_via_nfkc():
    # U+FEDF U+FEE0 ... presentation forms of lam -> plain lam (U+0644)
    assert normalize("ﻟ") == "ل"


def test_hyphenation_whitespace_and_case():
    assert normalize("Reason-\ning  ABOUT\tit") == "reasoning about it"
    assert normalize("chain of thought—a series") == "chain of thought a series"


def test_numbers_ignore_identifiers():
    assert numbers_in("GPT-3 on GSM8K, code-davinci-002") == []
    assert numbers_in("4.4 (+0.3) 20.6 (-4.9) PaLM 540B") == [4.4, 0.3, 20.6, -4.9, 540.0]


@pytest.mark.parametrize(
    "value,quote_numbers,ok",
    [
        (56.9, [56.9], True),
        (56.9, [56.94], True),  # within 0.05
        (57, [56.9], True),  # one decimal place of rounding
        (56.9, [57.0], True),
        (59.6, [56.9], False),
        (99, [41.2, 55.0, 63.7], False),
        (17.9, [17.9], True),
    ],
)
def test_number_tolerance(value, quote_numbers, ok):
    assert number_matches(value, quote_numbers) is ok


def test_percent_and_plain_forms_are_equal():
    assert check_numbers([56.9], "accuracy of 56.9%", "accuracy of 56.9% on GSM8K")
    assert check_numbers([56.9], "accuracy of 56.9", None)


def test_number_must_also_be_on_page():
    # A quote that fuzzy-matches the page but has a digit changed must not verify a number.
    page = "540B 17.9 56.9 69.4 79.0 72.1 73.9 25.2 35.8 79.2 93.3"
    assert check_numbers([56.9], page, page)
    assert not check_numbers([59.6], page.replace("56.9", "59.6"), page)


def _doc(*texts: str) -> StoredDoc:
    pages = [PageText(number=i + 1, visible_text=t, all_text=t) for i, t in enumerate(texts)]
    return StoredDoc("d", "sha", "x.pdf", "x.pdf", 0, pages)


def test_quote_verified_and_neighbour_page_fix():
    doc = _doc("intro text only here", "A chain of thought is a series of intermediate reasoning steps.", "")
    assert check_quote(doc, 2, "a series of intermediate reasoning steps").status == "verified"
    fixed = check_quote(doc, 1, "a series of intermediate reasoning steps")
    assert fixed.status == "verified" and fixed.page == 2


def test_quote_failed_and_unverified():
    doc = _doc("alpha beta gamma delta", "")
    assert check_quote(doc, 1, "completely different sentence here").status == "failed"
    assert check_quote(doc, 2, "anything at all on a blank page").status == "unverified"
    assert check_quote(doc, 9, "page that does not exist at all").status == "failed"


def test_quote_score_tolerates_lost_spaces():
    assert quote_score("We explore how generating", "Weexplorehowgenerating a chain") >= 90
