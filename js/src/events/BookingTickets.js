import React from 'react'
import {
  Button,
  Col,
  Collapse,
  Form as BootstrapForm,
  FormFeedback,
  ModalBody,
  Row,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import Input from '../forms/Input'
import {ModalFooter} from '../general/Modal'


export class User extends React.Component {
  async logout () {
    try {
      await this.props.requests.post('logout/')
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.props.setRootState({user: null})
  }

  render () {
    return (
      <div className="text-right">
        <small className="text-muted">
          Booking as:
        </small>
        &nbsp;
        <small className="text-dark">
          {this.props.user.name}
        </small>
        <Button onClick={this.logout.bind(this)} color="link" size="sm" className="pl-1 pr-0">
          (Logout)
        </Button>
      </div>
    )
  }
}

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
                value={!ticket_info.name && index === 0 && user.name && user.name !== user.email ?
                       user.name : ticket_info.name}
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

const TicketForm = props => {
  const state = props.state
  const remaining = state.booking_info ? state.booking_info.tickets_remaining : null
  const existing_tickets = state.booking_info ? state.booking_info.existing_tickets : null
  if (remaining !== null && remaining < 1) {
    return (
      <div>
        <h3>Sold out!</h3>
        <p>No more tickets available</p>
      </div>
    )
  }
  const max_tickets = Math.min(10, remaining || 10)
  const change_count = props.change_ticket_count
  return (
    <BootstrapForm onSubmit={props.reserve}>
      <ModalBody>
        <Row className="justify-content-between">
          <div>
            {existing_tickets ?
              <b>
                You've already bought {existing_tickets} ticket{existing_tickets > 1 ? 's': ''} for this event.
              </b>
              :
              null
            }
          </div>
          <User {...props}/>
        </Row>

        <div className="text-center font-weight-bold">
          Ticket Quantity
        </div>
        <Row className="justify-content-center my-1">
          <Button color="danger" disabled={state.ticket_count <= 1} onClick={() => change_count(-1)}>
            <FontAwesomeIcon icon="minus"/>
          </Button>
          <span className="my-1 mx-3 larger font-weight-bold">{state.ticket_count}</span>
          <Button color="success" disabled={state.ticket_count >= max_tickets} onClick={() => change_count(1)}>
            <FontAwesomeIcon icon="plus"/>
          </Button>
        </Row>
        <div className="text-muted text-center small">
          Select the number of tickets you would like to purchase.
        </div>
        {state.reservation_error &&
          <FormFeedback className="text-center display-block">{state.reservation_error}</FormFeedback>}

        <div className="guests-info">
          {[...Array(state.ticket_count).keys()].map(i => (
            <TicketInfo key={i} index={i} state={state} set_ticket_state={props.set_ticket_state} user={props.user}/>
          ))}
        </div>
      </ModalBody>
      <ModalFooter finished={props.finished}/>
    </BootstrapForm>
  )
}
export default TicketForm
