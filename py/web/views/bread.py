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
from functools import update_wrapper
from typing import List

from aiohttp import web
from buildpg import Var
from buildpg.asyncpg import Connection
from pydantic import BaseModel

from shared.settings import Settings
from web.utils import JsonErrors, raw_json_response


class Method(str, Enum):
    browse = 'browse'
    retrieve = 'retrieve'
    add = 'add'
    edit = 'edit'
    delete = 'delete'
    options = 'options'


class BaseCtrl:
    model: BaseModel = NotImplemented
    table: str = NotImplemented
    name: str = None

    fields: List[str] = None

    join = None
    where = None

    def __init__(self, request):
        self.request: web.Request = request
        self.app: web.Application = request.app
        self.conn: Connection = request['conn']
        self.settings: Settings = self.app['settings']

    @classmethod
    def routes(cls, root, name=None) -> List[web.RouteDef]:
        root = root.rstrip('/')
        name = name or cls.__name__.lower()
        return cls._routes(root, name)

    @classmethod
    def _routes(cls, root, name):
        return []

    @classmethod
    def view(cls, method: Method):
        method_func = getattr(cls, method.value)

        async def view(request):
            view_instance: cls = cls(request)
            await view_instance.precheck(method)
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

    async def precheck(self, method):
        pass

    def get_name(self):
        # or model title
        return self.name or self.table.title()

    def get_fields(self, method: Method) -> List[str]:
        return self.fields or list(self.model.__fields__.keys())

    def get_where(self, method: Method):
        return self.where

    async def _fetchval_response(self, sql, **kwargs):
        json_str = await self.conn.fetchval_b(sql, **kwargs)
        if not json_str:
            raise JsonErrors.HTTPNotFound(message=f'{self.get_name()} not found')
        return raw_json_response(json_str)

    @staticmethod
    def _as_values(f):
        # TODO
        return f


class ReadCtrl(BaseCtrl):
    """
    GET /?filter 200,403
    GET /{id}/ 200,403,404
    """
    filter_model: BaseModel = None

    browse_join = None
    browse_fields = None
    browse_where = None
    browse_order_by = None
    browse_limit = 50
    # TODO change to be dict with total
    browse_sql = """
    SELECT array_to_json(array_agg(row_to_json(t))) FROM (
      SELECT :fields
      FROM :table
      :join
      WHERE :where
      ORDER BY :order_by
      LIMIT :limit
    ) AS t
    """

    retrieve_join = None
    retrieve_fields = None
    retrieve_where = None

    @classmethod
    def _routes(cls, root, name) -> List[web.RouteDef]:
        return super()._routes(root, name) + [
            web.get(root + '/', cls.view(Method.browse), name=f'{name}-browse'),
            web.get(root + '/{id}/', cls.view(Method.retrieve), name=f'{name}-retrieve'),
            web.route('OPTIONS', root + '/', cls.view(Method.options), name=f'{name}-options'),
        ]

    def get_browse_where(self):
        return self.browse_where or self.get_where(Method.browse)

    def get_browse_fields(self):
        return self.browse_fields or self.get_fields(Method.browse)

    async def browser(self) -> web.Response:
        json_str = await self.conn.fetchval_b(
            self.browse_sql,
            fields=self._as_values(self.get_browse_fields()),
            table=Var(self.table),
            # TODO join
            where=self.get_browse_where(),
            order_by=self.browse_order_by,
            limit=self.browse_limit,
        )
        return raw_json_response(json_str or '[]')

    def get_retrieve_fields(self):
        return self.retrieve_fields or self.get_fields(Method.retrieve)

    def get_retrieve_where(self):
        return self.retrieve_where or self.get_where(Method.retrieve)

    async def retrieve(self, id) -> web.Response:
        pass

    async def options(self) -> web.Response:
        pass


class WriteCtrl(BaseCtrl):
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


class Ctrl(WriteCtrl, ReadCtrl):
    pass
