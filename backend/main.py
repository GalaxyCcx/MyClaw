import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from agent.init_jobs import init_collector
    from agent.engine import load_system_prompt
    from agent.llm import get_llm
    from agent.skill_loader import get_skill_loader
    from agent.tool_registry import get_all_tools

    init_collector.clear()
    loader = get_skill_loader()

    init_collector.run_job("load_config", lambda: f"LLM_MODEL={os.getenv('LLM_MODEL', 'qwen-plus')}, BASE_URL={os.getenv('LLM_BASE_URL', 'dashscope')}")

    def _load_prompt():
        prompt = load_system_prompt()
        lines = prompt.strip().split('\n')
        preview = lines[0][:80] + (f'... ({len(lines)} lines)' if len(lines) > 1 else '')
        return preview
    init_collector.run_job("load_system_prompt", _load_prompt)

    def _check_llm():
        llm = get_llm()
        return f"model={llm.model_name}, streaming={llm.streaming}"
    init_collector.run_job("check_llm", _check_llm)

    def _discover():
        skills = loader.discover()
        if not skills:
            return "No skills found"
        details = "; ".join(f"{s.name} ({len(s.scripts)} scripts)" for s in skills)
        return f"{len(skills)} skill(s) discovered — {details}"
    init_collector.run_job("discover_skills", _discover)

    def _register_tools():
        tools = get_all_tools()
        names = [t.name for t in tools]
        return f"{len(tools)} builtin tools — [{', '.join(names)}]"
    init_collector.run_job("register_tools", _register_tools)

    logger.info("MyClaw V2 initialized — %d jobs completed", len(init_collector.jobs))
    yield


app = FastAPI(title="MyClaw", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "myclaw"}
