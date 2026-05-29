from fastapi import APIRouter, Depends, Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from service.userService import register_user, login_user, get_managers_with_online_status, mark_user_offline
from service.leadService import get_current_user_role

router = APIRouter(prefix="/auth", tags=["Auth"])
users_router = APIRouter(prefix="/users", tags=["Users"])
security = HTTPBearer()


def get_user_from_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Extract user info from Authorization header"""
    token = credentials.credentials
    return get_current_user_role(token)


def get_user_from_token_no_activity(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    return get_current_user_role(token, update_activity=False)


class User(BaseModel):
    username: str
    email: EmailStr
    password: str


@router.post("/register")
def register(user: User, user_info: dict = Depends(get_user_from_token)):
    if user_info.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can register new users")
    return register_user(user)


@router.post("/login")
def login(user: User):
    return login_user(user)


@router.post("/logout")
def logout(user_info: dict = Depends(get_user_from_token_no_activity)):
    if user_info.get("role") == "manager":
        mark_user_offline(user_info["id"])
    return {"msg": "Logged out successfully"}


@users_router.get("/managers/status")
def get_managers_status(_: dict = Depends(get_user_from_token)):
    return {"managers": get_managers_with_online_status()}
