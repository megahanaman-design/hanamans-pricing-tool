from django import template

register = template.Library()


@register.filter
def percent(value):
    if value is None:
        return "-"
    return f"{float(value) * 100:.2f}%"
