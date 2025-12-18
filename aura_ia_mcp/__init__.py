__all__ = ["create_app"]


# Lazy import to avoid pulling in heavy dependencies during test imports
def create_app():
    from .main import create_app as _create_app

    return _create_app()
