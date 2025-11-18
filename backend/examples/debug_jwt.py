"""
Debug JWT token creation and verification
"""

import sys
sys.path.insert(0, 'd:\\bybit_strategy_tester_v2')

from backend.auth.jwt_bearer import token_manager, jwt_bearer
import jwt

# Create token
print("="*80)
print("Creating JWT token...")
print("="*80)

token = token_manager.create_access_token(
    user_id="admin",
    scopes=["read", "write", "admin"]
)

print(f"Token: {token[:80]}...")
print()

# Decode without verification to see payload
print("="*80)
print("Decoded payload (no verification):")
print("="*80)
try:
    decoded = jwt.decode(token, options={"verify_signature": False})
    print(f"Subject: {decoded.get('sub')}")
    print(f"Type: {decoded.get('type')}")
    print(f"Scopes: {decoded.get('scopes')}")
    print(f"Expiration: {decoded.get('exp')}")
    print(f"Issued at: {decoded.get('iat')}")
    print()
except Exception as e:
    print(f"Error decoding: {e}")
    print()

# Try to verify
print("="*80)
print("Verifying with JWTBearer...")
print("="*80)

bearer = jwt_bearer
result = bearer.verify_jwt(token)

if result:
    print("✓ Verification SUCCESS")
    print(f"  User: {result.get('sub')}")
    print(f"  Scopes: {result.get('scopes')}")
else:
    print("✗ Verification FAILED")

print()
print("="*80)
