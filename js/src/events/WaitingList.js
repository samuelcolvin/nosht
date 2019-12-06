import React from 'react'
import {ModalBody} from 'reactstrap'
import ReactGA from 'react-ga'
import requests from '../utils/requests'
import AsModal from '../general/Modal'
import BookingLogin from './BookingLogin'
import {ModalFooter} from '../general/Modal'

class WaitingListForm extends React.Component {
  onSubmit = async (e) => {
    e.preventDefault()
    try {
      await requests.post(`events/${this.props.event.id}/waiting-list/add/`)
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.props.ctx.setMessage({icon: 'user', message: "You've been successfully added to the waiting list"})
    ReactGA.event({category: 'waiting-list', action: 'add'})
    this.props.finished()
  }


  render () {
    if (!this.props.ctx.user) {
      return <BookingLogin finished={this.props.finished} success_label="Join Waiting List"/>
    } else {
      return (
        <form onSubmit={this.onSubmit}>
          <ModalBody>
            <p>
              Joining the waiting list for <b>{this.props.event.name}</b> means you'll get notified if more tickets
              become available.
            </p>
            <p>
              You can remove yourself from the list whenever you get an email about this event by following the
              link in the email.
            </p>
          </ModalBody>
          <ModalFooter label="Join Waiting List" finished={this.props.finished}/>
        </form>
      )
    }
  }
}
const ModalWaitingListForm = AsModal(WaitingListForm)

const WaitingListEvent = props => (
  <ModalWaitingListForm {...props} title={`Join waiting list for ${props.event.name}`} regex={/waiting-list\/$/}/>
)
export default WaitingListEvent
