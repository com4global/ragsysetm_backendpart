from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from typing import Optional
from database import supabase, user_db

# This is just for Swagger UI support
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Pydantic models
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Optional[str] = None
    email: Optional[str] = None

class User(BaseModel):
    id: str
    email: str
    full_name: Optional[str] = None
    company: Optional[str] = None
    is_active: bool = True
    access_token: Optional[str] = None  # Store JWT for RLS-authenticated DB calls

class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    company: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

# Dependency to get current user
async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )

    try:
        # Verify token with Supabase Auth
        user_response = supabase.auth.get_user(token)
        if not user_response or not user_response.user:
            raise credentials_exception
        
        user_data = user_response.user
        
        # Get profile data from our custom table
        profile = user_db.get_user_by_id(user_data.id)
        
        if profile is None:
            # If profile doesn't exist yet (race condition with trigger?), use auth data
            # or maybe just return basic info
            return User(
                id=user_data.id,
                email=user_data.email,
                full_name=user_data.user_metadata.get('full_name'),
                company=None,
                access_token=token  # Keep the JWT for database RLS
            )

        return User(
            id=profile['id'],
            email=profile.get('email'),
            full_name=profile.get('full_name'),
            company=profile.get('company'),
            is_active=profile.get('is_active', True),
            access_token=token  # Keep the JWT for database RLS
        )
        
    except Exception as e:
        print(f"Auth Error: {e}")
        raise credentials_exception

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user