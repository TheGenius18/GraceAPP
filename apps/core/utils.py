from rest_framework.response import Response

def api_response(success=True, message="", data=None, status=200):
    return Response({
        "status": "success" if success else "error",
        "message": message,
        "data": data
    }, status=status)
