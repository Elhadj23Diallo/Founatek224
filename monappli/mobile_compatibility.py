import re

from django.conf import settings
from rest_framework.response import Response


CONTRACT = "2"
UPDATE_MESSAGE = "Mets à jour Founatek pour continuer."


def mobile_policy(request):
    minimum = settings.MOBILE_MINIMUM_BUILDS
    platform = request.headers.get("X-Founatek-Platform")
    build = request.headers.get("X-Founatek-Build", "")
    compatible = (
        platform in minimum
        and request.headers.get("X-Founatek-Contract") == CONTRACT
        and re.fullmatch(r"[1-9][0-9]{0,8}", build) is not None
        and int(build) >= minimum[platform]
    )
    return {
        "contract": CONTRACT,
        "minimum_builds": minimum,
        "compatible": compatible,
        "wallet_idempotency": True,
        "message": "" if compatible else UPDATE_MESSAGE,
    }


def mobile_update_required(policy):
    return Response({
        "code": "update_required",
        "error": UPDATE_MESSAGE,
        "minimum_builds": policy["minimum_builds"],
    }, status=409, headers={"Cache-Control": "no-store"})
