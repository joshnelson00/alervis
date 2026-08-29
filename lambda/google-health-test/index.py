import socket

def ping_status(host: str, port: int, timeout_int: int, num_retries: int) -> bool:
    for _ in range(num_retries):
        try:
            with socket.create_connection((host, port), timeout=timeout_int):
                return True
        except OSError:
            continue
    return False

def get_output_message() -> str:
    host = "www.google.com"
    retries = 5
    timeout = 3
    port = 443

    success_text = "The google health test passed."
    failed_text = "The google health test failed."


    if ping_status(host=host, port=port, timeout_int=timeout, num_retries=retries):
        return success_text
    else:
        return failed_text


def handler(event, context) -> dict:
    resp_message = get_output_message()

    return {
        "version": "1.0",
        "response": {
            "outputSpeech": {
                "type": "PlainText",
                "text": resp_message,
            },
            "shouldEndSession": True
        }
    }
