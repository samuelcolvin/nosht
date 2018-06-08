"""
views:

GET /?filter 200,403
POST /add/ 200,400,403
GET /{id}/ 200,403,404
PUT /{id}/ 200,400,403,404
DELETE /{id}/ 200,400,403,404
OPTIONS / 200,403

rules:
* options should be the same for create and update and for every update

To update:
* get all fields
* update fields data with request data
* validate that data
* SQL update with put data only via dict(include_fields=request_data.keys())
"""
from enum import Enum
from functools import update_wrapper, wraps
from typing import Dict, List

from aiohttp import web
from buildpg import SelectFields, Var, funcs
from buildpg.asyncpg import BuildPgConnection
from buildpg.clauses import Clause, Clauses, From, Limit, OrderBy, Select
from pydantic import BaseModel

from web.utils import JsonErrors, raw_json_response


class Method(str, Enum):
    browse = 'browse'
    retrieve = 'retrieve'
    add = 'add'
    edit = 'edit'
    delete = 'delete'
    options = 'options'


class BaseBread:
    __slots__ = 'method', 'request', 'app', 'conn', 'settings', 'extra'
    model: BaseModel = NotImplemented
    table: str = NotImplemented
    name: str = None

    def __init__(self, method, request):
        self.method: Method = method
        self.request: web.Request = request
        self.app: web.Application = request.app
        self.conn: BuildPgConnection = request['conn']
        self.settings = self.app['settings']
        self.extra = {}

    @classmethod
    def routes(cls, root, name=None) -> List[web.RouteDef]:
        root = root.rstrip('/')
        name = name or cls.name or cls.__name__.lower()
        return cls._routes(root, name)

    @classmethod
    def _routes(cls, root, name):
        return []

    @classmethod
    def view(cls, method: Method):
        method_func = getattr(cls, method.value)

        async def view(request):
            view_instance: cls = cls(method, request)
            await view_instance.check_permissions(method)
            if method in {Method.retrieve, Method.edit, Method.delete}:
                return await method_func(view_instance, id=request.match_info['id'])
            else:
                return await method_func(view_instance)

        view.view_class = cls

        # take name and docstring from class
        update_wrapper(view, cls, updated=())
        # and possible attributes set by decorators
        update_wrapper(view, method_func, assigned=())
        return view

    async def check_permissions(self, method):
        pass

    @property
    def meta(self):
        return {
            'single_title': self.name or self.table.title(),
        }

    def from_(self):
        return From(self.table)

    def join(self) -> Clause:
        pass

    def where(self) -> Clause:
        pass

    async def _fetchval_response(self, sql, **kwargs):
        json_str = await self.conn.fetchval_b(sql, **kwargs)
        if not json_str:
            raise JsonErrors.HTTPNotFound(message=f'{self.meta["single_title"]} not found')
        return raw_json_response(json_str)

    @staticmethod
    def _as_values(f):
        # TODO
        return f


def as_clauses(gen):
    @wraps(gen)
    async def gen_wrapper(*args, **kwargs):
        return Clauses(*[c async for c in gen(*args, **kwargs) if c])

    return gen_wrapper


class ReadBread(BaseBread):
    """
    GET /?filter 200,403
    GET /{id}/ 200,403,404
    """
    filter_model: BaseModel = None
    fields_lookup: Dict[Method, List[str]] = {}

    browse_order_by_fields: List[str] = None
    browse_limit_value = 50
    browse_sql = """
    SELECT json_build_object(
      'items', items,
      'count', count_
    )
    FROM (
      SELECT array_to_json(array_agg(row_to_json(t))) as items FROM (
        :items_query
      ) AS t
    ) AS items,
    (
      :count_query
    ) AS count_
    """

    @classmethod
    def _routes(cls, root, name) -> List[web.RouteDef]:
        return super()._routes(root, name) + [
            web.get(root + '/', cls.view(Method.browse), name=f'{name}-browse'),
            web.get(root + '/{id}/', cls.view(Method.retrieve), name=f'{name}-retrieve'),
            # web.options(, root + '/', cls.view(Method.options), name=f'{name}-options'),
        ]

    def select(self) -> Select:
        f = self.fields_lookup.get(self.method) or list(self.model.__fields__.keys())

        if isinstance(f, list):
            fields = SelectFields(*f)
        else:
            fields = SelectFields(**f)
        return Select(fields)

    def browse_order_by(self):
        if self.browse_order_by_fields:
            return OrderBy(*self.browse_order_by_fields)

    def browse_limit(self):
        if self.browse_limit_value:
            return Limit(self.browse_limit_value)

    @as_clauses
    async def browse_items_query(self):
        yield self.select()
        yield self.from_()
        yield self.join()
        yield self.where()
        yield self.browse_order_by()
        yield self.browse_limit()

    @as_clauses
    async def browse_count_query(self):
        yield Select(funcs.count('*', as_='count_'))
        yield self.from_()
        yield self.join()
        yield self.where()

    async def browse(self) -> web.Response:
        json_str = await self.conn.fetchval_b(
            self.browse_sql,
            items_query=await self.browse_items_query(),
            count_query=await self.browse_count_query(),
        )
        return raw_json_response(json_str or '[]')

    async def retrieve(self, id) -> web.Response:
        pass

    async def options(self) -> web.Response:
        pass


class WriteBread(BaseBread):
    """
    POST /add/ 200,400,403
    PUT /{id}/ 200,400,403,404
    DELETE /{id}/ 200,400,403,404
    """

    @classmethod
    def _routes(cls, root, name) -> List[web.RouteDef]:
        return super()._routes(root, name) + [
            web.post(root + '/add/', cls.view(Method.add), name=f'{name}-add'),
            web.put(root + '/{id}/', cls.view(Method.edit), name=f'{name}-edit'),
            web.delete(root + '/{id}/', cls.view(Method.delete), name=f'{name}-delete'),
        ]

    async def add(self) -> web.Response:
        pass

    async def edit(self, id) -> web.Response:
        pass

    async def delete(self, id) -> web.Response:
        pass


class Bread(WriteBread, ReadBread):
    pass
