from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

# User OAuth2 password bearer
oauth2_scheme_user = OAuth2PasswordBearer(tokenUrl="/user/token", scheme_name="User")


# Token data schema
class TokenData(BaseModel):
    """
    Token data schema.
    """

    access_token: str
    token_type: str
