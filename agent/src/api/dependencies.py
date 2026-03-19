from fastapi import Header, HTTPException
import os

async def verify_internal_token(x_service_token: str = Header(...)):
    """
    Validates that requests are originating from the Next.js frontend
    by checking the internal signed service token.
    Bypasses the need for Python to independently fetch and verify Clerk JWTs.
    """
    # Defaulting to a dev skeleton token for scaffolding
    expected_token = os.getenv("INTERNAL_SERVICE_KEY_SIGNER", "dev_service_token_123")
    
    if x_service_token != expected_token:
        raise HTTPException(status_code=403, detail="Forbidden: Invalid internal service token")
        
    return x_service_token
