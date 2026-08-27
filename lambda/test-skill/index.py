
def handler(event, context) -> dict:
    return {
    "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": "The test skill is working!"
            },
            "shouldEndSession": True
        }
    }
