import uuid

def generate_tracking_number() -> str:
    return f"SHIP-{uuid.uuid4().hex[:8].upper()}"
