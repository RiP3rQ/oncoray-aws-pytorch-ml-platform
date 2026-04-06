from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ClientNotAuthorized, InvalidToken
from app.core.security import oauth2_scheme_user
from app.database.models import User
from app.database.redis import is_jti_blacklisted
from app.database.session import get_session
from app.utils import decode_access_token

# Asynchronous database session dep annotation
SessionDep = Annotated[AsyncSession, Depends(get_session)]


# Access token data dep
async def _get_access_token(token: str) -> dict:
    data = decode_access_token(token)

    # Validate the token
    if data is None or await is_jti_blacklisted(data["jti"]):
        raise InvalidToken()

    return data


# User access token data
async def get_user_access_token(
    token: Annotated[str, Depends(oauth2_scheme_user)],
) -> dict:
    return await _get_access_token(token)


# Logged In User
async def get_current_user(
    token_data: Annotated[dict, Depends(get_user_access_token)],
    session: SessionDep,
):
    user = await session.get(
        User,
        UUID(token_data["user"]["id"]),
    )

    if user is None:
        raise ClientNotAuthorized()

    return user



# # Shipment service dep
# def get_shipment_service(
#     session: SessionDep
# ):
#     return ShipmentService(
#         session,
#         DeliveryPartnerService(session),
#         ShipmentEventService(session),
#     )


# # Seller service dep
# def get_seller_service(session: SessionDep):
#     return SellerService(session)


# # Seller dep annotation
# SellerDep = Annotated[
#     Seller,
#     Depends(get_current_seller),
# ]


# # Seller service dep annotation
# SellerServiceDep = Annotated[
#     SellerService,
#     Depends(get_seller_service),
# ]
