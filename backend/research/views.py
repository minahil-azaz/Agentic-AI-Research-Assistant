import json
import logging
import queue
import threading

from django.contrib.auth import authenticate
from django.conf import settings
from django.contrib.auth.models import User
from django.db import close_old_connections, connection
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import ResearchQuery
from .serializers import (
    ResearchQueryCreateSerializer, ResearchQueryListSerializer, ResearchQuerySerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def sse_event(event_type: str, data: dict) -> str:
    payload = json.dumps({"type": event_type, **data})
    return f"data: {payload}\n\n"


def _decode_token(request):
    """
    Return the User for a valid JWT.
    Accepts token from:
      - Authorization: Bearer <token>   header
      - ?token=<token>                  query param  (needed for EventSource)
    Returns (user, error_string).
    """
    from rest_framework_simplejwt.tokens import AccessToken
    token_str = (
        request.GET.get("token")
        or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    )
    if not token_str:
        return None, "Authentication required."
    try:
        access = AccessToken(token_str)
        user = User.objects.get(id=access["user_id"])
        return user, None
    except Exception as exc:
        return None, f"Invalid token: {exc}"


# ─────────────────────────────────────────────────────────────────────────────
# Auth views
# ─────────────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    """POST /api/auth/register/  body: {username, email, password, password2}"""
    data      = request.data
    username  = data.get("username", "").strip()
    email     = data.get("email", "").strip()
    password  = data.get("password", "")
    password2 = data.get("password2", "")

    errors = {}
    if not username:
        errors["username"] = "Username is required."
    elif User.objects.filter(username=username).exists():
        errors["username"] = "Username already taken."
    if not email:
        errors["email"] = "Email is required."
    elif User.objects.filter(email=email).exists():
        errors["email"] = "Email already registered."
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 8:
        errors["password"] = "Password must be at least 8 characters."
    if password != password2:
        errors["password2"] = "Passwords do not match."

    if errors:
        return Response(errors, status=status.HTTP_400_BAD_REQUEST)

    user    = User.objects.create_user(username=username, email=email, password=password)
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "message": "Account created.",
            "user":    {"id": user.id, "username": user.username, "email": user.email},
            "access":  str(refresh.access_token),
            "refresh": str(refresh),
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """POST /api/auth/login/  body: {username, password}"""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")

    if not username or not password:
        return Response({"error": "Username and password are required."}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"error": "Invalid credentials."}, status=401)

    refresh = RefreshToken.for_user(user)
    return Response({
        "user":    {"id": user.id, "username": user.username, "email": user.email},
        "access":  str(refresh.access_token),
        "refresh": str(refresh),
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """POST /api/auth/logout/  body: {refresh}"""
    try:
        token = RefreshToken(request.data.get("refresh"))
        token.blacklist()
    except Exception:
        pass
    return Response({"message": "Logged out."})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    u = request.user
    return Response({"id": u.id, "username": u.username, "email": u.email})


@api_view(["GET"])
@permission_classes([AllowAny])
def health_view(request):
    """GET /api/health/  — which model/backends are active, so the UI can show it."""
    from .agent.tools import is_mock_embeddings, is_mock_gemini
    return Response({
        "gemini_model":      settings.GEMINI_MODEL,
        "gemini_mock":       is_mock_gemini(),
        "embedding_model":   settings.EMBEDDING_MODEL,
        "embeddings_mock":   is_mock_embeddings(),
        "tavily_configured": bool(settings.TAVILY_API_KEY),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Research views
# ─────────────────────────────────────────────────────────────────────────────

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_research(request):
    """POST /api/research/  body: {query}"""
    serializer = ResearchQueryCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)
    obj = serializer.save(user=request.user)
    return Response({"id": obj.id, "stream_url": f"/api/research/{obj.id}/stream/"}, status=201)


@csrf_exempt
def stream_research(request, pk):
    """
    GET /api/research/<pk>/stream/

    Plain Django view — NOT decorated with @api_view.
    @api_view triggers DRF content-negotiation which rejects text/event-stream
    with 406 Not Acceptable.  Using a plain view bypasses that entirely.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed."}, status=405)

    user, err = _decode_token(request)
    if err:
        return JsonResponse({"error": err}, status=401)

    try:
        query_obj = ResearchQuery.objects.get(pk=pk, user=user)
    except ResearchQuery.DoesNotExist:
        return JsonResponse({"error": "Not found."}, status=404)

    # Only the first stream for a query runs the agent. Re-opening the stream
    # (browser reconnect, reopened tab) replays the stored result instead of
    # re-running the whole pipeline and duplicating sources.
    claimed = ResearchQuery.objects.filter(pk=pk, status="pending").update(status="planning")

    if not claimed:
        query_obj.refresh_from_db()

        def replay_stream():
            yield sse_event("connected", {"query_id": pk, "query": query_obj.query})
            if query_obj.status == "done":
                data = ResearchQuerySerializer(query_obj).data
                yield sse_event("report",  {"report": data["report"]})
                yield sse_event("sources", {"sources": data["sources"]})
            elif query_obj.status == "error":
                yield sse_event("error", {"message": query_obj.status_message or "Research failed."})
            else:
                yield sse_event("status", {"step": query_obj.status, "message": query_obj.status_message or "Still running…"})
                yield sse_event("running", {"query_id": pk})
            yield sse_event("done", {"query_id": pk})

        stream = replay_stream()
    else:
        event_queue: queue.Queue = queue.Queue()
        sentinel = object()

        def on_event(event_type, data):
            event_queue.put((event_type, data))

        def run_agent():
            from .agent.agent import ResearchAgent
            close_old_connections()
            try:
                agent = ResearchAgent(on_event=on_event)
                agent.run(query_obj.id, query_obj.query)
            except Exception as exc:
                logger.exception("Agent failed: %s", exc)
            finally:
                connection.close()  # threads get their own DB connection; don't leak it
                event_queue.put(sentinel)

        threading.Thread(target=run_agent, daemon=True).start()

        def event_stream():
            yield sse_event("connected", {"query_id": pk, "query": query_obj.query})
            while True:
                try:
                    item = event_queue.get(timeout=15)
                except queue.Empty:
                    yield ": keep-alive\n\n"  # stops proxies closing an idle stream during long steps
                    continue
                if item is sentinel:
                    yield sse_event("done", {"query_id": pk})
                    break
                event_type, data = item
                yield sse_event(event_type, data)

        stream = event_stream()

    resp = StreamingHttpResponse(stream, content_type="text/event-stream")
    resp["Cache-Control"]     = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_research(request):
    qs = ResearchQuery.objects.filter(user=request.user).order_by("-created_at")[:50]
    return Response(ResearchQueryListSerializer(qs, many=True).data)


@api_view(["GET", "DELETE"])
@permission_classes([IsAuthenticated])
def research_detail(request, pk):
    try:
        obj = ResearchQuery.objects.get(pk=pk, user=request.user)
    except ResearchQuery.DoesNotExist:
        return Response({"error": "Not found."}, status=404)

    if request.method == "DELETE":
        obj.delete()
        return Response(status=204)

    return Response(ResearchQuerySerializer(obj).data)
