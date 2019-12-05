import React from 'react'
import {Table, Button} from 'reactstrap'
import {Link} from 'react-router-dom'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {currency_lookup} from '../general/Money'
import {RenderDetails, ImageThumbnail, render} from '../general/Dashboard'
import {ModalForm} from '../forms/Form'
import {ModalDropzoneForm} from '../forms/Drop'
import WithContext from '../utils/context'
import FooterLinks from './FooterLinks'

const CO_FIELDS = [
  {name: 'name', required: true},
  {name: 'domain', required: true},
  {name: 'stripe_public_key', required: true},
  {name: 'stripe_secret_key', required: true},
  {name: 'stripe_webhook_secret', required: true},
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

const LinksTable = WithContext(({links, uri}) => (
  <div className="mb-5">
    <h4>
      Footer Links
      <Button tag={Link} to={uri + 'links/'} size="sm" className="ml-2">
        <FontAwesomeIcon icon="pencil-alt" className="mr-1"/>
        Edit
      </Button>
    </h4>
    <Table striped>
      <thead>
        <tr>
          <th>Title</th>
          <th>URL</th>
          <th>New Tab</th>
        </tr>
      </thead>
      <tbody>
        {links && links.map((link, i) => (
          <tr key={i}>
            <td>{link.title}</td>
            <td>
              <a href={link.url} target="_blank" rel="noopener noreferrer">
                <code>{link.url}</code>
              </a>
            </td>
            <td>{render(link.new_tab)}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  </div>
))

export default class CompanyDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = '/dashboard/company/'
    this.state.buttons = [
      {name: 'Edit', link: this.uri + 'edit/'},
    ]
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
      footer_links: null,
    }
  }

  id = () => this.props.ctx.company.company.id
  get_uri = () => `/companies/${this.id()}/`

  extra () {
    return [
      <LinksTable key="links" links={this.state.item.footer_links} uri={this.uri}/>,
      <ModalForm title="Edit Company"
                 key="edit"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg="Company Updated"
                 initial={this.state.item}
                 update={this.update}
                 action={`/companies/${this.id()}/`}
                 fields={CO_FIELDS}/>,
      <ModalDropzoneForm key="image"
                         parent_uri={this.uri}
                         regex={/set-image\/$/}
                         update={this.update}
                         title="Upload Background Image"
                         action="/companies/upload/image/"/>,
      <ModalDropzoneForm key="logo"
                         parent_uri={this.uri}
                         regex={/set-logo\/$/}
                         update={this.update}
                         title="Upload Company Logo"
                         action="/companies/upload/logo/"
                         help_text="This image is used in emails, it must be at least 256px x 256px."/>,
      <FooterLinks key="edit-links"
                   links={this.state.item.footer_links}
                   regex={/links\/$/}
                   update={this.update}
                   title="Edit Footer Links"/>
    ]
  }
}
