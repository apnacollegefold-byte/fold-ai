import sys
import os

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, SRC_DIR)

import api.config  
from api.middleware.clerk_auth import clerk_auth
from api.repositories.user_repository import get_or_create_user_from_clerk

TOKEN = "PASTE_YOUR_TOKEN_HERE"  # from browser console: await window.Clerk.session.getToken()


def main():
    print("Step 1: verify the token against Clerk's JWKS...")
    payload = clerk_auth.verify_token(TOKEN)
    if not payload:
        print("Token verification failed — check it hasn't been mistyped, or CLERK_DOMAIN in .env.")
        return
    print("  Verified. Decoded payload:", payload)

    clerk_user_id = payload["sub"]
    print(f"\nStep 2: sync this Clerk user (sub={clerk_user_id}) into our DB...")
    user = get_or_create_user_from_clerk(
        clerk_user_id=clerk_user_id,
        email=payload.get("email"),
        full_name=payload.get("name"),
        avatar_url=payload.get("picture"),
    )
    print("  Synced:", user)
    print("\nCheck the `users` table in Neon now — this row should be there.")


if __name__ == "__main__":
    main()
