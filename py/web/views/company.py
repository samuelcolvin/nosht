from functools import partial
from pathlib import Path

from buildpg import V
from pydantic import BaseModel, NameEmail

from shared.images import delete_image, upload_background, upload_other
from shared.utils import Currencies
from web.auth import check_session, is_admin
from web.bread import Bread
from web.utils import JsonErrors, json_response, request_image


class CompanyBread(Bread):
    class Model(BaseModel):
        name: str
        domain: str
        stripe_public_key: str
        stripe_secret_key: str
        currency: Currencies
        email_from: NameEmail = None
        email_reply_to: NameEmail = None
        email_template: str = None

    retrieve_enabled = True
    edit_enabled = True

    model = Model
    table = 'companies'

    retrieve_fields = (
        'name',
        'slug',
        'domain',
        'stripe_public_key',
        'stripe_secret_key',
        'currency',
        'email_from',
        'email_reply_to',
        'email_template',
        'image',
        'logo',
    )

    async def check_permissions(self, method):
        await check_session(self.request, 'admin')
        if int(self.request.match_info['pk']) != self.request['company_id']:
            raise JsonErrors.HTTPForbidden(message='wrong company')

    async def prepare_edit_data(self, data):
        if 'email_from' in data:
            data['email_from'] = str(data['email_from'])
        if 'email_reply_to' in data:
            data['email_reply_to'] = str(data['email_reply_to'])
        return data


LOGO_SIZE = 256, 256
upload_logo = partial(upload_other, req_width=LOGO_SIZE[0], req_height=LOGO_SIZE[1])


@is_admin
async def company_upload(request):
    field_name = request.match_info['field']
    assert field_name in {'image', 'logo'}, field_name  # double check
    content = await request_image(request, expected_size=None if field_name == 'image' else LOGO_SIZE)

    co_id = request['company_id']
    co_slug, old_image = await request['conn'].fetchrow_b(
        'SELECT slug, :image_field FROM companies WHERE id=:id',
        image_field=V(field_name),
        id=co_id
    )

    upload_path = Path(co_slug) / 'co' / field_name
    method = upload_background if field_name == 'image' else upload_logo
    image_url = await method(content, upload_path=upload_path, settings=request.app['settings'])

    await request['conn'].execute_b('UPDATE companies SET :set WHERE id=:id', set=V(field_name) == image_url, id=co_id)

    # delete the image from S3 before uploading a new one
    if old_image:
        await delete_image(old_image, request.app['settings'])
    return json_response(status='success')
