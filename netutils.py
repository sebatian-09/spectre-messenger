import json


async def send_json(websocket, payload):
    """Serialize a payload to JSON and send it over a websocket."""
    await websocket.send(json.dumps(payload))


async def broadcast_json(clients, payload):
    """Send a JSON payload to every client, ignoring individual failures.

    ``clients`` may be any iterable of websocket connections (e.g. a dict's
    values). Failures to reach a single client are swallowed so one dead
    connection cannot break delivery to the rest.
    """
    message = json.dumps(payload)
    for client in list(clients):
        try:
            await client.send(message)
        except Exception:
            pass
