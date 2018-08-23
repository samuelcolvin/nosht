import logging

from buildpg import V
from buildpg.clauses import Join, Where
from pydantic import BaseModel, condecimal, constr

from web.auth import check_grecaptcha, check_session
from web.bread import Bread
from web.stripe import StripeDonateModel, stripe_donate

from .booking import UpdateViewAuth

logger = logging.getLogger('nosht.booking')


class Donate(UpdateViewAuth):
    Model = StripeDonateModel

    async def execute(self, m: StripeDonateModel):
        await check_grecaptcha(m, self.request)
        action_id, _ = await stripe_donate(m, self.request['company_id'], self.session['user_id'], self.app, self.conn)
        await self.app['email_actor'].send_donation_thanks(action_id)


class DonationOptionBread(Bread):
    class Model(BaseModel):
        category: int
        name: constr(max_length=255)
        amount: condecimal(ge=1, max_digits=6, decimal_places=2)
        live: bool = True
        short_description: str
        long_description: str
        sort_index: int = None

    browse_enabled = True
    retrieve_enabled = True
    edit_enabled = True
    add_enabled = True
    delete_enabled = True

    model = Model
    table = 'donation_options'
    table_as = 'opt'
    browse_order_by_fields = 'opt.category', 'opt.sort_index', 'opt.amount'
    browse_fields = (
        'opt.id',
        'opt.name',
        V('cat.name').as_('category_name'),
        'opt.live',
        'opt.amount',
    )
    retrieve_fields = browse_fields + (
        'opt.category',
        'opt.sort_index',
        'opt.short_description',
        'opt.long_description',
        'opt.image',
    )

    async def check_permissions(self, method):
        await check_session(self.request, 'admin')

    def where(self):
        return Where(V('cat.company') == self.request['company_id'])

    def join(self):
        return Join(V('categories').as_('cat').on(V('cat.id') == V('opt.category')))
