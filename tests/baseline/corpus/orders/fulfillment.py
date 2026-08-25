def retry_with_backoff(operation, max_attempts=3):
    attempt = 0
    delay = 1
    while attempt < max_attempts:
        try:
            return operation()
        except Exception:
            attempt += 1
            delay = delay * 2
    raise RuntimeError("operation failed after retries")


def pack_shipment(items, max_weight):
    boxes = []
    current_box = []
    current_weight = 0
    for item in items:
        if current_weight + item["weight"] > max_weight:
            boxes.append(current_box)
            current_box = []
            current_weight = 0
        current_box.append(item)
        current_weight += item["weight"]
    if current_box:
        boxes.append(current_box)
    return boxes


def process_shipment_batch(shipments):
    ready = []

    def is_shipment_ready(shipment):
        if shipment.get("packed") is not True:
            return False
        if shipment.get("address") is None:
            return False
        return shipment.get("weight", 0) > 0

    for shipment in shipments:
        if is_shipment_ready(shipment):
            ready.append(shipment)
    return ready
