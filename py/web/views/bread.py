from pydantic import BaseModel

from web.bread import Bread


class CategoryBread(Bread):
    class Model(BaseModel):
        name: str
        live: bool
        description: str
        sort_index: int
        event_content: str
        host_advice: str

    model = Model
    table = 'categories'
