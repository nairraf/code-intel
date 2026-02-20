from auth import verify_token
from fastapi import Depends

def analysis(token=Depends(verify_token)):
    pass
