def compute_circle_area(radius):
    if radius < 0:
        raise ValueError("radius must be non-negative")
    pi = 3.14159265358979
    area = pi * radius * radius
    return round(area, 4)


def compute_circle_circumference(radius):
    if radius < 0:
        raise ValueError("radius must be non-negative")
    pi = 3.14159265358979
    circumference = 2 * pi * radius
    return round(circumference, 4)


def point_in_polygon(point, vertices):
    x, y = point
    inside = False
    n = len(vertices)
    j = n - 1
    for i in range(n):
        xi, yi = vertices[i]
        xj, yj = vertices[j]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def point_in_circle(point, center, radius):
    dx = point[0] - center[0]
    dy = point[1] - center[1]
    distance_sq = dx * dx + dy * dy
    return distance_sq <= radius * radius


def compute_polygon_area(vertices):
    area = 0
    n = len(vertices)
    for i in range(n):
        x1, y1 = vertices[i]
        x2, y2 = vertices[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2


def compute_segment_magnitude(offsets):
    accumulator = 0
    for delta in offsets:
        accumulator += delta * delta
    magnitude = accumulator**0.5
    return round(magnitude, 4)
