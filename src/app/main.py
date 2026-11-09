import os
import logging
import uvicorn
import pandas as pd

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from src.app.modals import QueryRequest, QueryResponse
from src.app.settings import APP_NAME
from src.tracing.tracing import (
    initialize_tracing,
    observe_span,
    shutdown_tracing,
    trace_error_details,
    trace_user_identifier,
)
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
    initialize_tracing()
    try:
        file_path = os.getenv("SOURCE_FILE_PATH")
        if not file_path:
            raise ValueError("SOURCE_FILE_PATH not configured")
        df = pd.read_excel(file_path)
        yield
    finally:
        shutdown_tracing()
        df = None


app = FastAPI(
    title=APP_NAME,
    version="1.0.0",
    description=f"HTTP interface for {APP_NAME}.",
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
    with observe_span(
        "POST /chat",
        input=request.model_dump(mode="json"),
        trace_user_id=trace_user_identifier(request.user_id.strip()),
    ) as trace:
        try:
            response = await TransactionRAGPipeline(
                request.user_id.strip(),
                request.prompt,
                df,
            )
            if trace is not None:
                response_body = response.model_dump(mode="json")
                trace.set_trace_io(
                    input=request.model_dump(mode="json"),
                    output=response_body,
                )
            return response
        except UserNotFoundError:
            error_response = {"detail": "User not found."}
            if trace is not None:
                trace.set_trace_io(
                    input=request.model_dump(mode="json"),
                    output=error_response,
                )
            return JSONResponse(
                status_code=404,
                content=error_response,
            )
        except Exception as exc:
            logger.exception("Unexpected error while processing chat request")
            error_response = {
                "detail": "An unexpected error occurred while processing your request."
            }
            if trace is not None:
                details = trace_error_details(exc)
                trace.update(
                    level="ERROR",
                    status_message=details["error_type"],
                    metadata=details,
                )
                trace.set_trace_io(
                    input=request.model_dump(mode="json"),
                    output=error_response,
                )
            return JSONResponse(
                status_code=500,
                content=error_response,
            )

if __name__ == "__main__":
    uvicorn.run(app)
