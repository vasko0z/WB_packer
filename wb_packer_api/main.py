#!/usr/bin/env python
"""Entry point for running without Docker"""

import uvicorn
from app.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )
