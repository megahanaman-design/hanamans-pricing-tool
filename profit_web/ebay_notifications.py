import hashlib
import os

from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest, HttpResponseNotAllowed
from django.views.decorators.csrf import csrf_exempt


@csrf_exempt
def marketplace_account_deletion(request):
    """Endpoint required by eBay Marketplace Account Deletion notifications.

    GET validates endpoint ownership using eBay's challenge_code flow.
    POST acknowledges notifications. This app does not persist eBay buyer identifiers,
    so there is no buyer-keyed local record to delete here.
    """
    if request.method == "GET":
        challenge_code = request.GET.get("challenge_code")
        if not challenge_code:
            return HttpResponseBadRequest("missing challenge_code")

        verification_token = os.getenv("EBAY_DELETION_VERIFY_TOKEN", "")
        if not verification_token:
            return HttpResponse("verification token not configured", status=503)

        endpoint = request.build_absolute_uri(request.path)
        digest = hashlib.sha256(
            (challenge_code + verification_token + endpoint).encode("utf-8")
        ).hexdigest()
        return JsonResponse({"challengeResponse": digest})

    if request.method == "POST":
        # We intentionally do not persist notification payloads or buyer identifiers.
        return HttpResponse(status=204)

    return HttpResponseNotAllowed(["GET", "POST"])
