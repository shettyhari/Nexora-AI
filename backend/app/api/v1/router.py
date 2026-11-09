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
from app.api.v1.documents import router as documents_router
from app.api.v1.multimodal import router as multimodal_router
from app.api.v1.voice import router as voice_router
from app.api.v1.research import router as research_router
from app.api.v1.agents import router as agents_router
from app.api.v1.tools import router as tools_router
from app.api.v1.lab import router as lab_router
from app.api.v1.lab_training import router as lab_training_router
from app.api.v1.inference import lab_deployments_router, openai_router

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
api_router.include_router(documents_router)
api_router.include_router(multimodal_router)
api_router.include_router(voice_router)
api_router.include_router(research_router)
api_router.include_router(agents_router)
api_router.include_router(tools_router)
api_router.include_router(lab_router)
api_router.include_router(lab_training_router)
api_router.include_router(lab_deployments_router)
api_router.include_router(openai_router, prefix="/inference")
