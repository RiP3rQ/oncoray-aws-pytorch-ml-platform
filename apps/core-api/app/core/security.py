from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel


oauth2_scheme_user = OAuth2PasswordBearer(tokenUrl="/user/token", scheme_name="User")


class TokenData(BaseModel):
    access_token: str
    token_type: str