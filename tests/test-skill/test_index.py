from index import handler


def test_handler_returns_dict():
    result = handler({}, None)
    assert isinstance(result, dict)


def test_handler_returns_correct_version():
    result = handler({}, None)
    assert result["version"] == "1.0"


def test_handler_returns_plain_text_speech():
    result = handler({}, None)
    output_speech = result["response"]["outputSpeech"]
    assert output_speech["type"] == "PlainText"


def test_handler_returns_expected_speech_text():
    result = handler({}, None)
    assert result["response"]["outputSpeech"]["text"] == "The test skill is working!"


def test_handler_ends_session():
    result = handler({}, None)
    assert result["response"]["shouldEndSession"] is True


def test_handler_ignores_event_contents():
    result_empty = handler({}, None)
    result_with_data = handler({"request": {"intent": {"name": "SomeIntent"}}}, None)
    assert result_empty == result_with_data
