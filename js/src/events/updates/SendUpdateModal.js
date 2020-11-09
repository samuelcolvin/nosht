import React from 'react'

import {ModalForm} from '../../forms/Form'


const EVENT_EMAIL_UPDATE_FIELDS = [
  {name: 'subject', required: true},
  {name: 'message', required: true, type: 'md', max_length: 255000}
]
const MESSAGE_NAME_TT_SLUG = 'message_to_ticket_type__'


export class SendUpdateModal extends React.Component {
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
      return EVENT_EMAIL_UPDATE_FIELDS
    }
  }

  dataFormatter (formData) {
    return Object.keys(formData).reduce((data, k) => {
      if (formData[k]) {
        if (k.startsWith(MESSAGE_NAME_TT_SLUG))
          data.group_messages.push({
            ticketType: k.replace(MESSAGE_NAME_TT_SLUG, ''),
            message: formData[k]
          })
        else
          data[k] = formData[k]
      }
      return data
    }, {group_messages: []})
  }

  render () {
    return (
      <ModalForm key="send-update"
                 title="Send Event update to Guests"
                 parent_uri={this.props.parentUri}
                 regex={/send-update\/$/}
                 mode="edit"
                 success_msg='Event Update Sent'
                 initial={this.props.event.status}
                 action={`/events/${this.props.event.id}/updates/send/`}
                 fields={this.buildFieldList()}
                 useRequestFormatter={this.dataFormatter}
                 save="Send Email" />
    )
  }
}
export default SendUpdateModal
