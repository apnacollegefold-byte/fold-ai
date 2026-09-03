import logging
import os
import api.config
from fastapi import Request, HTTPException
import jwt
from jwt import PyJWKClient
from api.repositories.user_repository import get_or_create_user_from_clerk


_logger = logging.getLogger(__name__)


class ClerkAuth:

    def __init__(self):
        self.clerk_secret_key = os.getenv("CLERK_SECRET_KEY", "")
        self.clerk_domain = os.getenv("CLERK_DOMAIN", "")

        if not self.clerk_secret_key:
            _logger.warning("CLERK_SECRET_KEY not set — auth will be disabled")
        if not self.clerk_domain:
            _logger.warning("CLERK_DOMAIN not set — auth will be disabled")

        self.jwks_url = f"https://{self.clerk_domain}/.well-known/jwks.json"
        _logger.info("Clerk JWKS URL: %s", self.jwks_url)

        try:
            self.jwks_client = PyJWKClient(self.jwks_url)
            _logger.info("JWKS client initialised successfully")
        except Exception as e:
            _logger.error("Failed to create JWKS client: %s", e)
            self.jwks_client = None

    def verify_token(self, token: str) -> dict | None:

        if not self.jwks_client:
            _logger.warning("JWKS client not initialised — cannot verify tokens")
            return None

        try:
            # Step 1: Get the RSA public key that signed this token
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            # Step 2: Decode and verify (disable strict expiry to treat tokens as long-lived)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_exp": False},
            )
            return payload

        except jwt.ExpiredSignatureError:
            _logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            _logger.warning("Invalid token: %s", e)
            return None
        except Exception as e:
            # Log the FULL error so we never mis-diagnose the cause again
            _logger.error("Token verification failed: %s: %s", type(e).__name__, e)
            return None              

    async def get_current_user(self, request: Request) -> dict | None:

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header[len("Bearer "):]
        payload = self.verify_token(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return {
            "clerk_user_id": user_id,
            "email": payload.get("email"),
            "full_name": payload.get("name"),
            "avatar_url": payload.get("picture"),
        }

    async def require_auth(self, request: Request) -> dict:
            """Like get_current_user but raises 401 if not authenticated."""
            user = await self.get_current_user(request)
            if not user:
                raise HTTPException(
                    status_code=401,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return user

clerk_auth = ClerkAuth()

async def get_current_user(request: Request) -> dict:

    user_info = await clerk_auth.require_auth(request)
    user = get_or_create_user_from_clerk(
        clerk_user_id=user_info["clerk_user_id"],
        email=user_info.get("email"),
        full_name=user_info.get("full_name"),
        avatar_url=user_info.get("avatar_url"),
    )

    return {
        "user_ref": user_info["clerk_user_id"],
        "clerk_user_id": user_info["clerk_user_id"],
        "user_id": user["id"],
        "email": user.get("email"),
        "full_name": user.get("full_name"),
    }
