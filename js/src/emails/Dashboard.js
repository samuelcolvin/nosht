import React from 'react'
import {as_title} from '../utils'
import {RenderList, RenderDetails} from '../general/Dashboard'
import {ModalForm} from '../forms/Form'

const FIELDS = [
  {
    name: 'active',
    type: 'bool',
    help_text: 'Whether this email should send.'
  },
  {
    name: 'subject',
    required: true,
    help_text: "The email's subject."
  },
  {
    name: 'title',
    help_text: 'A title shown in the head of the email next to the company logo.',
  },
  {
    name: 'body',
    required: true,
    type: 'textarea',
    help_text: 'The body of the emails.',
    max_length: 2000,
  },
]

export class EmailDefList extends RenderList {
  constructor (props) {
    super(props)
    this.state.formats = {
      trigger: {render: as_title},
    }
  }

  get_link (item) {
    return `${item.trigger}/`
  }
}

export class EmailDefDetails extends RenderDetails {
  constructor (props) {
    super(props)
    this.uri = `/dashboard/email-defs/${this.id()}/`
    this.state.formats = {
      trigger: {render: as_title},
      body: {
        wide: true,
        render: item => <pre>{item}</pre>
      },
    }
  }

  async got_data (data) {
    await super.got_data(data)
    this.setState({buttons: [
      {name: 'Edit', link: this.uri + 'edit/'},
      data.customised && {
        name: 'Clear Customisation',
        action: `/email-defs/${this.id()}/clear/`,
        confirm_msg: (
          <div>
            <p>Are you sure you want to clear this email definition? It will be replaced by the default definition.</p>
            <p className="font-weight-bold">This cannot be undone.</p>
          </div>
        ),
        success_msg: 'Custom Email Definition Deleted',
        redirect_to: `/dashboard/email-defs/${this.id()}/`,
        done: () => this.update(),
      }
    ]})
  }

  extra () {
    return [
      <ModalForm key="edit"
                 title="Edit Email Definition"
                 parent_uri={this.uri}
                 mode="edit"
                 success_msg="Email Definition updated"
                 initial={this.state.item}
                 update={this.update}
                 action={`/email-defs/${this.id()}/edit/`}
                 submit_initial={true}
                 fields={FIELDS}/>,
    ]
  }
}
