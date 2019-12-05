"""
views:

GET /?filter 200,403
POST /add/ 201,400,403
GET /{pk}/ 200,403,404
POST /{pk}/ 200,400,403,404
POST /{pk}/delete/ 200,403,404
OPTIONS / 200,403

rules:
* options should be the same for create and update and for every update

To update:
* get all fields
* update fields data with request data
* validate that data
* SQL update with put data only via dict(include_fields=request_data.keys())
"""
import logging
import re
from enum import Enum
from functools import update_wrapper, wraps
from typing import Generator, List, Optional, Tuple, Type

from aiohttp import web
from asyncpg import UniqueViolationError
from buildpg import SetValues, Values, Var, funcs
from buildpg.asyncpg import BuildPgConnection
from buildpg.clauses import Clause, Clauses, From, Join, Limit, OrderBy, Select, Where
from pydantic import BaseModel

from web.utils import (
    JsonErrors,
    get_offset,
    json_response,
    parse_request,
    parse_request_ignore_missing,
    raw_json_response,
)

logger = logging.getLogger('nosht.bread')


class Method(str, Enum):
    browse = 'browse'
    retrieve = 'retrieve'
    add = 'add'
    edit = 'edit'
    delete = 'delete'
    options = 'options'


class BaseBread:
    __slots__ = 'method', 'request', 'app', 'conn', 'settings'
    model: Type[BaseModel] = NotImplemented
    table: str = NotImplemented
    table_as: str = None
    name: str = None
    pk_field: str = 'id'
    print_queries = False

    def __init__(self, method, request):
        self.method: Method = method
        self.request: web.Request = request
        self.app: web.Application = request.app
        self.conn: BuildPgConnection = request['conn']
        self.settings = self.app['settings']

    @classmethod
    def routes(cls, root, name=None) -> Tuple[web.RouteDef]:
        root = root.rstrip('/')
        name = name or cls.name or re.sub(r'Bread$', '', cls.__name__).lower()
        return tuple(cls._routes(root, name))

    @classmethod
    def _routes(cls, root, name) -> Generator[web.RouteDef, None, None]:
        raise NotImplementedError

    @classmethod
    def view(cls, method: Method):
        method_func = getattr(cls, method.value)

        async def view(request):
            self: cls = cls(method, request)
            await self.check_permissions(method)
            if method in {Method.retrieve, Method.edit, Method.delete}:
                return await method_func(self, pk=self.get_pk())
            else:
                return await method_func(self)

        view.view_class = cls

        # take name and docstring from class
        update_wrapper(view, cls, updated=())
        # and possible attributes set by decorators
        update_wrapper(view, method_func, assigned=())
        return view

    def get_pk(self):
        return int(self.request.match_info['pk'])

    async def check_permissions(self, method):
        pass

    @property
    def meta(self):
        return {
            'single_title': self.name or self.table.title(),
        }

    def from_(self) -> From:
        v = Var(self.table)
        if self.table_as:
            v = v.as_(self.table_as)
        return From(v)

    def join(self) -> Join:
        pass

    def where(self) -> Where:
        pass

    def pk_ref(self) -> Var:
        if self.table_as:
            return Var(self.table_as + '.' + self.pk_field)
        else:
            return Var(self.pk_field)

    def where_pk(self, pk) -> Where:
        if pk < 1:
            raise JsonErrors.HTTPBadRequest(message='request pk must be greater than 0')
        where = self.where()
        is_pk = self.pk_ref() == pk
        if where:
            where.logic = where.logic & is_pk
        else:
            where = Where(is_pk)
        return where

    async def _fetchval_response(self, sql, **kwargs):
        json_str = await self.conn.fetchval_b(sql, **kwargs)
        if not json_str:
            raise JsonErrors.HTTPNotFound(message=f'{self.meta["single_title"]} not found')
        return raw_json_response(json_str)


def as_clauses(gen):
    @wraps(gen)
    async def gen_wrapper(*args, **kwargs):
        return Clauses(*[c async for c in gen(*args, **kwargs) if c])

    return gen_wrapper


class Offset(Clause):
    base = 'OFFSET'

    def __init__(self, offset_value):
        super().__init__(offset_value)


class ReadBread(BaseBread):
    """
    GET /?filter 200,403
    GET /{pk}/ 200,403,404
    """

    filter_model: BaseModel = None

    browse_enabled = False
    retrieve_enabled = False
    browse_fields: List[str] = None
    browse_order_by_fields: List[str] = None
    browse_limit_value = 50
    browse_sql = """
    SELECT json_build_object(
      'items', items,
      'count', count_,
      'pages', ceil(count_ / :pagination::float)
    )
    FROM (
      SELECT coalesce(array_to_json(array_agg(row_to_json(t))), '[]') as items FROM (
        :items_query
      ) AS t
    ) AS items,
    (
      :count_query
    ) AS count_
    """

    retrieve_fields: List[str] = None
    retrieve_sql = """
    SELECT row_to_json(t) FROM (
      :query
    ) AS t
    """

    def select(self) -> Select:
        f = None
        if self.method == Method.browse:
            f = self.browse_fields
        elif self.method == Method.retrieve:
            f = self.retrieve_fields
        f = f or [self.pk_ref()] + list(self.model.__fields__.keys())
        return Select(f)

    def browse_order_by(self) -> Optional[OrderBy]:
        if self.browse_order_by_fields:
            return OrderBy(*self.browse_order_by_fields)

    def browse_limit(self) -> Optional[Limit]:
        if self.browse_limit_value:
            return Limit(Var(str(self.browse_limit_value)))

    def browse_offset(self) -> Optional[Offset]:
        if self.browse_limit_value:
            offset = get_offset(self.request, paginate_by=self.browse_limit_value)
            if offset:
                return Offset(offset)

    @as_clauses
    async def browse_items_query(self):
        yield self.select()
        yield self.from_()
        yield self.join()
        yield self.where()
        yield self.browse_order_by()
        yield self.browse_limit()
        yield self.browse_offset()

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
            pagination=Var(str(self.browse_limit_value)),
            print_=self.print_queries,
        )
        return raw_json_response(json_str)

    @as_clauses
    async def retrieve_query(self, pk):
        yield self.select()
        yield self.from_()
        yield self.join()
        yield self.where_pk(pk)
        yield Limit(Var('1'))

    async def retrieve(self, pk) -> web.Response:
        return await self._fetchval_response(
            self.retrieve_sql, query=await self.retrieve_query(pk), print_=self.print_queries,
        )

    async def options(self) -> web.Response:
        pass

    @classmethod
    def _routes(cls, root, name) -> List[web.RouteDef]:
        if cls.browse_enabled:
            yield web.get(root + '/', cls.view(Method.browse), name=f'{name}-browse')
            # yield web.options(root + '/', cls.view(Method.options), name=f'{name}-options')
        if cls.retrieve_enabled:
            yield web.get(root + r'/{pk:\d+}/', cls.view(Method.retrieve), name=f'{name}-retrieve')


class Bread(ReadBread):
    """
    POST /add/ 201,400,403
    POST /{pk}/ 200,400,403,404
    DELETE /{pk}/ 200,400,403,404
    """

    add_enabled = False
    edit_enabled = False
    delete_enabled = False
    add_sql = """
    INSERT INTO :table (:values__names) VALUES :values RETURNING :pk_field
    """

    edit_sql = """
    UPDATE :table
    SET :values
    :where
    """
    delete_sql = """
    DELETE FROM :table
    :where
    """
    check_ok_sql = """
    SELECT row_to_json(t) FROM (
      :query
    ) AS t
    """

    async def prepare_add_data(self, data):
        return data

    async def add_execute(self, **data):
        return await self.conn.fetchval_b(
            self.add_sql,
            table=Var(self.table),
            values=Values(**data),
            pk_field=Var(self.pk_field),
            print_=self.print_queries,
        )

    async def add(self) -> web.Response:
        m = await parse_request(self.request, self.model)
        data = await self.prepare_add_data(m.dict())
        try:
            pk = await self.add_execute(**data)
        except UniqueViolationError as e:
            raise self.conflict_exc(e)
        else:
            return json_response(status='ok', pk=pk, status_=201)

    async def add_options(self) -> web.Response:
        pass

    @as_clauses
    async def check_item_permissions_query(self, pk):
        yield Select([self.pk_ref()])
        yield self.from_()
        yield self.join()
        yield self.where_pk(pk)
        yield Limit(Var('1'))

    async def check_item_permissions(self, pk):
        v = await self.conn.fetchval_b(
            ':query', query=await self.check_item_permissions_query(pk), print_=self.print_queries,
        )
        if not v:
            raise JsonErrors.HTTPNotFound(message=f'{self.meta["single_title"]} not found')

    async def prepare_edit_data(self, pk, data):
        return data

    async def edit_execute(self, pk, **data):
        await self.conn.execute_b(
            self.edit_sql,
            table=Var(self.table),
            values=SetValues(**data),
            where=Where(Var(self.pk_field) == pk),
            print_=self.print_queries,
        )

    async def edit(self, pk) -> web.Response:
        await self.check_item_permissions(pk)
        m = await parse_request_ignore_missing(self.request, self.model)

        data = await self.prepare_edit_data(pk, m.dict(exclude_unset=True))
        if not data:
            raise JsonErrors.HTTPBadRequest(message=f'no data to save')

        try:
            await self.edit_execute(pk, **data)
        except UniqueViolationError as e:
            raise self.conflict_exc(e)
        else:
            return json_response(status='ok')

    async def edit_options(self) -> web.Response:
        pass

    async def delete_execute(self, pk):
        logger.info('%s %s=%d deleted by user %s', self.table, self.pk_field, pk, self.request['session']['user_id'])
        await self.conn.execute_b(
            self.delete_sql, table=Var(self.table), where=Where(Var(self.pk_field) == pk), print_=self.print_queries,
        )

    async def delete(self, pk) -> web.Response:
        await self.check_item_permissions(pk)
        await self.delete_execute(pk)
        return json_response(message=f'{self.table} {pk} deleted')

    @classmethod
    def _routes(cls, root, name) -> List[web.RouteDef]:
        yield from super()._routes(root, name)
        if cls.add_enabled:
            yield web.post(root + '/add/', cls.view(Method.add), name=f'{name}-add')
            # yield web.options(root + '/add/', cls.view(Method.add_options), name=f'{name}-add-options')
        if cls.edit_enabled:
            yield web.post(root + r'/{pk:\d+}/', cls.view(Method.edit), name=f'{name}-edit')
            # yield web.options(root + '/{pk:\d+}/', cls.view(Method.edit_options), name=f'{name}-edit-options')
        if cls.delete_enabled:
            yield web.post(root + r'/{pk:\d+}/delete/', cls.view(Method.delete), name=f'{name}-delete')

    def conflict_exc(self, exc: UniqueViolationError):
        columns = re.search(r'\((.+?)\)', exc.as_dict()['detail']).group(1).split(', ')
        return JsonErrors.HTTPConflict(
            message='Conflict',
            details=[
                {
                    'loc': [col],
                    'msg': f'This value conflicts with an existing "{col}", try something else.',
                    'type': 'value_error.conflict',
                }
                for col in columns
                if col in self.model.__fields__
            ],
        )
