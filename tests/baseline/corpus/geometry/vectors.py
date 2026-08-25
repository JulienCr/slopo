def compute_vector_length(vector):
    total = 0
    for component in vector:
        total += component * component
    length = total**0.5
    return round(length, 4)


def compute_dot_product(vector_a, vector_b):
    if len(vector_a) != len(vector_b):
        raise ValueError("vectors must be same length")
    total = 0
    for a, b in zip(vector_a, vector_b):
        total += a * b
    return round(total, 4)
