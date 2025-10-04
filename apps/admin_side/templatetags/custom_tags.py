from django import template

register = template.Library()

@register.filter
def truncate_team_name(name):
    if len(name) > 7:
        return name[:7] + '..'
    return name

@register.filter
def ordinal_day(value):
    """
    Adds ordinal suffix to the day of the month.
    Example: 1 -> 1st, 2 -> 2nd, 3 -> 3rd, etc.
    """
    try:
        value = int(value)
        if 10 <= value % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
        return f"{value}{suffix}"
    except (ValueError, TypeError):
        return value
    

@register.filter
def times(number):
    try:
        return range(int(number))
    except:
        return range(0)