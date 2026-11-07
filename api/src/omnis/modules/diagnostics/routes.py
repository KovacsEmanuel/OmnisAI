"""The ordinary local session/CSRF/body/query boundary applies unchanged."""

from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from omnis.core.errors import error_responses, request_correlation
from omnis.modules.diagnostics.schemas import PATH, UiAck, UiEvent
from omnis.modules.diagnostics.service import DiagnosticSink
from omnis.security.host_origin import error_response

router = APIRouter()


@router.post(PATH, response_model=UiAck, status_code=202, responses=error_responses(401, 422))
async def ui_event(event: UiEvent, request: Request) -> UiAck | JSONResponse:
    correlation = request_correlation.get()
    if correlation is None:
        return error_response("INTERNAL_ERROR", 500)
    sink: DiagnosticSink = request.app.state.ui_diagnostics
    state = sink.emit(event, str(correlation))
    return UiAck(version=1, event_id=event.event_id, accepted=True, state=state)
