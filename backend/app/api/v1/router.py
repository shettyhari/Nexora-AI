from fastapi import APIRouter
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.api.v1.conversations import router as conversations_router
from app.api.v1.messages import router as messages_router
from app.api.v1.feedback import router as feedback_router
from app.api.v1.models import router as models_router
from app.api.v1.attachments import router as attachments_router
from app.api.v1.projects import router as projects_router
from app.api.v1.memories import router as memories_router
from app.api.v1.rag import router as rag_router
from app.api.v1.router_eval import router as router_eval_router
from app.api.v1.gateway_health import router as gateway_health_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(conversations_router)
api_router.include_router(messages_router)
api_router.include_router(feedback_router)
api_router.include_router(models_router)
api_router.include_router(attachments_router)
api_router.include_router(projects_router)
api_router.include_router(memories_router)
api_router.include_router(rag_router)
api_router.include_router(router_eval_router)
api_router.include_router(gateway_health_router)

