"""
Authentication routes for NASA Earthdata credentials
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import existing modules
from modules import data_discovery
from modules.errors import DataDiscoveryError

router = APIRouter()


class AuthValidateResponse(BaseModel):
    """Response for credential validation"""
    valid: bool
    message: str
    authenticated: bool = False


@router.post("/validate", response_model=AuthValidateResponse)
async def validate_credentials():
    """
    Validate NASA Earthdata credentials from environment variables or .netrc
    
    Returns:
        AuthValidateResponse with validation status
    """
    try:
        # Check if credentials are available
        if not data_discovery.validate_credentials():
            return AuthValidateResponse(
                valid=False,
                authenticated=False,
                message="No NASA Earthdata credentials found. Please set EARTHDATA_USERNAME and EARTHDATA_PASSWORD in .env file or configure ~/.netrc"
            )
        
        # Try to authenticate
        try:
            data_discovery.authenticate()
            return AuthValidateResponse(
                valid=True,
                authenticated=True,
                message="Successfully authenticated with NASA Earthdata"
            )
        except DataDiscoveryError as e:
            return AuthValidateResponse(
                valid=False,
                authenticated=False,
                message=f"Authentication failed: {str(e)}"
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error validating credentials: {str(e)}"
        )


@router.get("/status")
async def auth_status():
    """
    Quick check of authentication status without attempting login
    
    Returns:
        Simple status of whether credentials are configured
    """
    has_credentials = data_discovery.validate_credentials()
    return {
        "credentials_configured": has_credentials,
        "message": "Credentials found" if has_credentials else "No credentials configured"
    }
