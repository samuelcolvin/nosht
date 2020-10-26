import React from 'react'

import {ModalForm} from '../../forms/Form'


const EVENT_EMAIL_UPDATE_FIELDS = [
  {name: 'subject', required: true},
  {name: 'message', required: true, type: 'md', max_length: 255000}
]
const MESSAGE_NAME_TT_SLUG = 'message_to_ticket_type__'


export class SendUpdateModal extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      initialValue: {status: props.event.status},
      fields: this.buildFieldList()
    }
  }

  componentDidUpdate (prevProps) {
    if (prevProps.ticketTypes !== this.props.ticketTypes)
      this.setState({fields: this.buildFieldList()})
  }

  buildFieldList () {
    if (this.props.ticketTypes && this.props.ticketTypes.length > 1) {
      const messages = this.props.ticketTypes
        .map(tt => Object.assign({}, EVENT_EMAIL_UPDATE_FIELDS[1], {
          name: MESSAGE_NAME_TT_SLUG + tt.id,
          title: `Message to ${tt.name} ticket holders`,
          required: false
        }))
      return [EVENT_EMAIL_UPDATE_FIELDS[0]].concat(messages)
    } else {
      return JSON.parse(JSON.stringify(EVENT_EMAIL_UPDATE_FIELDS))
    }
  }

  render () {
    return (
      <ModalForm key="send-update"
                 title="Send Event update to Guests"
                 parent_uri={this.props.parentUri}
                 regex={/send-update\/$/}
                 mode="edit"
                 success_msg='Event Update Sent'
                 initial={this.state.initialValue}
                 action={`/events/${this.props.event.id}/updates/send/`}
                 fields={this.state.fields}
                 save="Send Email" />
    )
  }
}
export default SendUpdateModal
