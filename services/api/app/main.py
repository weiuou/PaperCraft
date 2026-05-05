from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.errors import ApiError, api_error_response
from app.api.router import api_router
from app.domain.enums import ErrorCode


def create_app() -> FastAPI:
    app = FastAPI(title="AI PaperCraft Studio API")

    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError):
        return api_error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": ErrorCode.REQUEST_VALIDATION_FAILED.value,
                    "message": "Request validation failed.",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_router)
    return app


app = create_app()
