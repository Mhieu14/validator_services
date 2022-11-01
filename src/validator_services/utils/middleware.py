import jwt
from config import Config
from aiohttp.web import middleware
from utils.response import ApiUnauthorized


REQUIRED_FIELDS = ["user_name", "user_id", "user_type"]
def validate_fields_user_info(user_info):
    for field in REQUIRED_FIELDS:
        if field not in user_info:
            # raise ApiUnauthorized(f"'{field}' parameter is required")
            raise ApiUnauthorized('Invalid user info')

@middleware
async def self_authorize(request, handler):
    if request.method != "OPTIONS":
        if request.path == '/v1/healthz':
            resp = await handler(request)
            return resp
        else:
            token = request.headers.get("AUTHORIZATION")
            if token is None:
                raise ApiUnauthorized("No auth token provided!")

            token_prefixes = ("Bearer", "Token")
            for prefix in token_prefixes:
                if prefix in token:
                    token = token.partition(prefix)[2].strip()
            try:
                user_info = jwt.decode(token, Config.JWT_KEY, algorithms=['HS256'])
            except:
                raise ApiUnauthorized('Invalid auth token')
            print(user_info)
            validate_fields_user_info(user_info)
            resp = await handler(request, user_info)
            return resp
    else:
        resp = await handler(request)
        return resp
