import pytest

from molycow.errors import NotFoundError
from molycow.store import Book
from molycow.store.doses import DoseRepository
from molycow.store.generators import GeneratorRepository
from molycow.store.records import Records
from molycow.store.register import CustomerRepository


def test_a_repository_carries_the_book_it_reads(book: Book) -> None:
    repo = CustomerRepository(book)
    assert isinstance(repo, Records)
    assert repo.book is book


def test_required_gives_back_what_was_found() -> None:
    records = Records.__new__(Records)
    assert records.required("CU-0001", "no such customer") == "CU-0001"


def test_required_refuses_with_the_words_the_caller_wants() -> None:
    records = Records.__new__(Records)
    with pytest.raises(NotFoundError) as caught:
        records.required(None, "no such customer", id="CU-0404")
    assert caught.value.detail["id"] == "CU-0404"
    assert "no such customer" in str(caught.value)


def test_every_repository_refuses_the_same_way(book: Book) -> None:
    for repo, missing, words in (
        (CustomerRepository(book), "CU-0404", "no such customer"),
        (GeneratorRepository(book), "GEN-0404", "no such generator"),
        (DoseRepository(book), "DS-250408-99", "no such dose"),
    ):
        assert repo.find(missing) is None
        with pytest.raises(NotFoundError, match=words):
            repo.get(missing)
