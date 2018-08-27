import React from 'react'
import {currency_lookup} from '../general/Money'
import {RenderDetails, ImageThumbnail} from '../general/Dashboard'
import {ModalForm} from '../forms/Form'
import {ModalDropzoneForm} from '../forms/Drop'

const CO_FIELDS = [
  {name: 'name', required: true},
  {name: 'domain', required: true},
  {name: 'stripe_public_key', required: true},
  {name: 'stripe_secret_key', required: true},
  {
    name: 'currency',
    type: 'select',
    required: true,
    choices: Object.keys(currency_lookup).map(c => ({value: c, display_name: c.toUpperCase()})),
    help_text: 'WARNING: changing currency will cause all previous payments to display with the wrong currency',
  },
  {
    name: 'email_from',
    help_text: 'Address emails come from, either a simple email address "mynam@example.com", ' +
               'or "My Name <myname@example.com>" is permitted.',
  },
  {
    name: 'email_reply_to',
    help_text: 'Reply-To address for emails, either a simple email address "mynam@example.com", ' +
               'or "My Name <myname@example.com>" is permitted.',
  },
  {name: 'email_template', type: 'textarea'},
]

export default class CompanyDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = '/dashboard/company/'
    this.state.buttons = [
      {name: 'Edit', link: this.uri + 'edit/'},
    ]
    this.id = this.props.ctx.company.company.id
    this.state.formats = {
      image: {
        wide: true,
        edit_link: this.uri + 'set-image/',
        render: (v, item) => <ImageThumbnail image={v} alt={item.name}/>
      },
      logo: {
        wide: true,
        edit_link: this.uri + 'set-logo/',
        render: (v, item) => <ImageThumbnail image={v} alt={item.name} image_type="main"/>
      },
    }
  }

  get_uri () {
    return `/companies/${this.id}/`
  }

  extra () {
    return [
      <ModalForm title="Edit Company"
                 key="1"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg="Company Updated"
                 initial={this.state.item}
                 update={this.update}
                 action={`/companies/${this.id}/`}
                 fields={CO_FIELDS}/>,
      <ModalDropzoneForm key="2"
                         parent_uri={this.uri}
                         regex={/set-image\/$/}
                         update={this.update}
                         title="Upload Background Image"
                         action="/companies/upload/image/"/>,
      <ModalDropzoneForm key="3"
                         parent_uri={this.uri}
                         regex={/set-logo\/$/}
                         update={this.update}
                         title="Upload Company Logo"
                         action="/companies/upload/logo/"
                         help_text="This image is used in emails, it must be at least 256px x 256px."/>,
    ]
  }
}
