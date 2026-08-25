def compute_segment_magnitude(offsets):
    accumulator = 0
    for delta in offsets:
        accumulator += delta * delta
    magnitude = accumulator**0.5
    return round(magnitude, 4)
