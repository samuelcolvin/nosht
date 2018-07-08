import React from 'react'
import {
  Button,
  ButtonGroup,
  Form as BootstrapForm,
  ModalBody,
  ModalFooter,
  Row,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import AsModal from '../forms/Modal'
import {BookingLogin, TicketForm} from '../utils/Booking'

class BookWrapper extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      ticket_count: 1,
    }
  }

  async logout () {
    try {
      await this.props.requests.post('logout/')
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.props.setRootState({user: null})
  }

  set_ticket_state (key, t_key, value) {
    const t = Object.assign({}, this.state[key] || {})
    t[t_key] = value
    this.setState({[key]: t})
  }

  change_ticket_count (change) {
    this.setState({ticket_count: this.state.ticket_count + change})
  }

  async submit (e) {
    e.preventDefault()
    const tickets = [...Array(this.state.ticket_count).keys()]
      .map(index => this.state[`ticket_${index}`] || {})
      .map(t => ({
        name: t.name || null,
        email: t.email || null,
        dietary_req: t.dietary_req || null,
        extra_info: t.extra_info || null,
      }))

    tickets[0].name = tickets[0].name || this.props.user.name
    tickets[0].email = tickets[0].email || this.props.user.email
    console.log(tickets)
  }

  render () {
    const user = this.props.user
    return (
      <BootstrapForm onSubmit={this.submit.bind(this)}>
        <ModalBody>
          {user ?
            <TicketForm
                user={user}
                state={this.state}
                logout={this.logout.bind(this)}
                set_ticket_state={this.set_ticket_state.bind(this)}
                change_ticket_count={this.change_ticket_count.bind(this)}/>
            :
            <BookingLogin setRootState={this.props.setRootState} requests={this.props.requests}/>
          }
        </ModalBody>
        <ModalFooter>
          <ButtonGroup>
            <Button type="button" color="secondary" onClick={() => this.props.finished && this.props.finished()}>
              Cancel
            </Button>
            <Button type="submit" color="primary" disabled={!user}>
              Book
            </Button>
          </ButtonGroup>
        </ModalFooter>
      </BootstrapForm>
    )
  }
}
const ModalBookForm = AsModal(BookWrapper)

const BookEvent = props => (
  <ModalBookForm {...props}
                 title={`Book Tickets for ${props.event.name}`}
                 regex={/book\/$/}/>
)
export default BookEvent
