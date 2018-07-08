import React from 'react'
import {
  Button,
  ButtonGroup,
  Col,
  Form as BootstrapForm,
  ModalBody,
  ModalFooter,
  Row,
  Collapse,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import AsModal from '../forms/Modal'
import Input from '../forms/Input'
import {BookingLogin} from '../utils/Booking'

const User = ({user, logout}) => (
  <div className="text-right">
    <small className="text-muted">
      Booking as:
    </small>
    &nbsp;
    <small className="text-dark">
      {user.name}
    </small>
    <Button onClick={logout} color="link" size="sm" className="pl-1 pr-0">
      (Logout)
    </Button>
  </div>
)

const TicketInfo = ({index, state, set_ticket_state, user}) => {
  const key = `ticket_${index}`
  const ticket_info = state[key] || {}
  const name_field = {
    name: key + 'name',
    placeholder: 'name',
    show_label: false,
    help_text: index === 0 ? '' : "Leave blank if you don't know the guest's name."
  }
  const email_field = {
    name: key + 'email',
    type: 'email',
    placeholder: 'email',
    show_label: false,
    help_text: index === 0 ? '' : "Leave blank if you don't know the guest's email address."
  }
  const dietary_field = {
    name: key + 'dietary',
    title: 'Dietary Requirements',
    type: 'select',
    choices: [
      {value: 'thing_1'},
      {value: 'thing_2'},
      {value: 'thing_3'},
    ]
  }
  const extra_field = {
    name: key + 'extra',
    title: 'Extra Information',
    type: 'textarea',
    help_text: 'Any other information about this booking for the Host.'
  }

  let title = `Guest ${index + 1}'s Details`
  if (index === 0) {
    title = 'Your Details'
  } else if (ticket_info.name && ticket_info.name.endsWith('s')) {
    title = `${ticket_info.name}' Details`
  } else if (ticket_info.name) {
    title = `${ticket_info.name}'s Details`
  }
  return (
    <div className="mb-1 pb-1">
      <h5>{title}</h5>
      <Row>
        <Col md="6">
          <Input className="my-0"
                value={!ticket_info.name && index === 0 && user.name ? user.name : ticket_info.name}
                field={name_field}
                set_value={v => set_ticket_state(key, 'name', v)}/>
        </Col>
        <Col md="6">
          <Input className="my-0"
                value={!ticket_info.email && index === 0 ? user.email : ticket_info.email}
                field={email_field}
                set_value={v => set_ticket_state(key, 'email', v)}/>
        </Col>
      </Row>
      <Button color="link"
              size="sm"
              className="mb-1 p-0 no-dec"
              onClick={e => set_ticket_state(key, 'extra', !ticket_info.extra)}>
        extra &nbsp;
        <span className="rotate" style={{transform: `rotate(${ticket_info.extra ? '90' : '0'}deg)`}}>&rsaquo;</span>
      </Button>
      <Collapse isOpen={ticket_info.extra}>
        <Input className="my-0"
              value={ticket_info.dietary_req}
              field={dietary_field}
              set_value={v => set_ticket_state(key, 'dietary_req', v)}/>
        <Input className="my-0"
              value={ticket_info.extra_info}
              field={extra_field}
              set_value={v => set_ticket_state(key, 'extra_info', v)}/>
      </Collapse>
    </div>
)
}

const BookForm = ({user, state, logout, set_ticket_state, change_ticket_count}) => (
  <div>
    <User user={user} logout={logout}/>

    <div className="text-center font-weight-bold">
      Ticket Quantity
    </div>
    <Row className="justify-content-center my-1">
      <Button color="danger" disabled={state.ticket_count === 1} onClick={() => change_ticket_count(-1)}>
        <FontAwesomeIcon icon="minus"/>
      </Button>
      <span className="my-1 mx-3 larger font-weight-bold">{state.ticket_count}</span>
      <Button color="success" disabled={state.ticket_count === 10} onClick={() => change_ticket_count(1)}>
        <FontAwesomeIcon icon="plus"/>
      </Button>
    </Row>
    <div className="text-muted text-center small">
      Select the number of tickets you would like to purchase.
    </div>

    <div className="guests-info">
      {[...Array(state.ticket_count).keys()].map(i => (
        <TicketInfo key={i} index={i} state={state} set_ticket_state={set_ticket_state} user={user}/>
      ))}
    </div>
  </div>
)

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
            <BookForm
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
