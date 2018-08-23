import logging
from pathlib import Path

from buildpg import V
from buildpg.clauses import Join, Where
from pydantic import BaseModel, condecimal, constr

from shared.images import delete_image, upload_other
from web.auth import check_grecaptcha, check_session, is_admin
from web.bread import Bread
from web.stripe import StripeDonateModel, stripe_donate
from web.utils import JsonErrors, json_response, request_image

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


IMAGE_SIZE = 640, 480


@is_admin
async def donation_image_upload(request):
    co_id = request['company_id']
    don_opt_id = int(request.match_info['pk'])
    r = await request['conn'].fetchrow(
        """
        SELECT co.slug, cat.slug, d.image
        FROM donation_options AS d
        JOIN categories AS cat ON d.category = cat.id
        JOIN companies AS co ON cat.company = co.id
        WHERE d.id = $1 AND cat.company = $2
        """,
        don_opt_id,
        co_id,
    )
    if not r:
        raise JsonErrors.HTTPNotFound(message='donation option not found')

    co_slug, cat_slug, old_image = r
    content = await request_image(request, expected_size=IMAGE_SIZE)

    upload_path = Path(co_slug) / cat_slug / str(don_opt_id)
    image_url = await upload_other(
        content, upload_path=upload_path, settings=request.app['settings'], req_size=IMAGE_SIZE, thumb=True,
    )

    await request['conn'].execute('UPDATE donation_options SET image=$1 WHERE id=$2', image_url, don_opt_id)

    if old_image:
        await delete_image(old_image, request.app['settings'])
    return json_response(status='success')
