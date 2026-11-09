import os
import logging
import uvicorn
import pandas as pd

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from src.app.modals import QueryRequest, QueryResponse
from src.pipeline.transaction_pipeline import (
    TransactionRAGPipeline,
    UserNotFoundError,
)


load_dotenv()
logger = logging.getLogger(__name__)
df = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global df
    file_path = os.getenv("SOURCE_FILE_PATH")
    if not file_path:
        raise ValueError("SOURCE_FILE_PATH not configured")
    df = pd.read_excel(file_path)
    yield
    df = None


app = FastAPI(
    title="Personal Finance Analysis API",
    version="1.0.0",
    description="HTTP interface for the transaction analysis pipeline.",
    lifespan=lifespan
)


@app.get("/health", tags=["health"])
def health():
    return JSONResponse(
        status_code=200,
        content="Hi I'm Alive" 
    )


@app.post(
    "/chat",
    response_model=QueryResponse,
)
async def chat(request: QueryRequest) -> QueryResponse | JSONResponse:
    try:
        return await TransactionRAGPipeline(request.user_id.strip(), request.prompt, df)
    except UserNotFoundError:
        return JSONResponse(
            status_code=404,
            content={"detail": "User not found."},
        )
    except Exception:
        logger.exception("Unexpected error while processing chat request")
        return JSONResponse(
            status_code=500,
            content={
                "detail": "An unexpected error occurred while processing your request."
            },
        )

if __name__ == "__main__":
    uvicorn.run(app)
