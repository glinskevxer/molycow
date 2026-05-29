from molycow.tools import check_errors


def test_every_refusal_in_this_package_reads_the_same_way() -> None:
    assert check_errors.findings() == []
    assert check_errors.main() == 0


def test_every_error_class_is_actually_used() -> None:
    built = check_errors.raised_classes()
    for name in check_errors.error_classes():
        if name == "MolycowError":
            continue
        assert name in built


def test_the_messages_are_read_out_of_the_raise_sites() -> None:
    messages = [message for _, message, _, _ in check_errors.raised_messages()]
    assert "an empty box is not a shipment" in messages
    assert all(message == message.strip() for message in messages)


def test_no_message_starts_with_a_capital_or_ends_in_a_stop() -> None:
    for _, message, _, _ in check_errors.raised_messages():
        assert not message[0].isupper()
        assert not message.endswith(".")


def test_the_error_classes_are_the_ones_in_the_module() -> None:
    names = check_errors.error_classes()
    assert "ValidationError" in names
    assert "SafetyError" in names
    assert "ReleaseError" in names
