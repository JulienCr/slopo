def compute_vector_length(vector):
    total = 0
    for component in vector:
        total += component * component
    length = total**0.5
    return round(length, 4)
