from fastapi import Request

from apps.api.content import ContentStore


def get_content(request: Request) -> ContentStore:
    return request.app.state.content
