def get_star_rating(score):
    if score >= 80:
        return 1
    elif score >= 60:
        return 2
    elif score >= 40:
        return 3
    elif score >= 20:
        return 4
    else:
        return 5

def update_star_rating(score):
    return get_star_rating(score)