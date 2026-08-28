import os

from django.http import JsonResponse


NAMES = ("EBAY_CLIENT_ID", "EBAY_CLIENT_SECRET", "EBAY_RUNAME")


def ebay_env_presence(request):
    data = {}
    for name in NAMES:
        value = os.getenv(name)
        data[name] = {
            "in_environ": name in os.environ,
            "nonempty": bool(value),
            "length": len(value) if value is not None else None,
        }
    return JsonResponse(data)
