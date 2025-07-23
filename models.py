from pydantic import BaseModel

class SignalMessage(BaseModel):
    type: str
    from_user: str
    target: str
    data: dict
