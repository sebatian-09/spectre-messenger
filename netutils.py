import json

from websockets.exceptions import ConnectionClosed


async def send_json(websocket, payload):
    """Serialize a payload to JSON and send it over a websocket."""
    await websocket.send(json.dumps(payload))


async def broadcast_json(clients, payload, logger=None, context=""):
    """Send a JSON payload to every client, logging per-client failures.

    ``clients`` may be a mapping of ``name -> websocket`` (e.g. a dict) or a
    plain iterable of websocket connections. Failures to reach a single client
    are contained so one dead connection cannot break delivery to the rest; if
    a ``logger`` is provided they are logged (using the client name and
    ``context`` when available).
    """
    message = json.dumps(payload)
    if hasattr(clients, "items"):
        items = list(clients.items())
    else:
        items = [(None, client) for client in list(clients)]

    suffix = f" during {context}" if context else ""
    for name, client in items:
        try:
            await client.send(message)
        except ConnectionClosed:
            if logger is not None:
                who = f"Client {name}" if name is not None else "A client"
                logger.info(f"{who} disconnected{suffix}")
        except Exception as e:
            if logger is not None:
                who = name if name is not None else "a client"
                logger.error(f"Failed to send to {who}{suffix}: {e}")
