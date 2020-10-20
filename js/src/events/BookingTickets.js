import React from 'react'
import {
  Button,
  Col,
  Form as BootstrapForm,
  FormFeedback,
  ModalBody,
  Row,
} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import WithContext from '../utils/context'
import requests from '../utils/requests'
import {user_full_name} from '../utils'
import Input from '../forms/Input'
import {ModalFooter} from '../general/Modal'
import {MoneyFree} from '../general/Money'
import {PricingList} from './BookingStripe'
import {Overlay} from './Stripe'

const MAX_TICKETS = 20


export class User extends React.Component {
  async logout () {
    try {
      await requests.post('logout/')
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.props.ctx.setUser(null)
  }

  render () {
    return (
      <div className="text-right">
        <small className="text-muted">
          {this.props.donating ? 'Donating' : 'Booking'} as:
        </small>
        &nbsp;
        <small className="text-dark">
          {user_full_name(this.props.ctx.user)}
        </small>
        <Button onClick={this.logout.bind(this)} color="link" size="sm" className="pl-1 pr-0">
          (Logout)
        </Button>
      </div>
    )
  }
}

const TicketInfo = ({index, state, set_ticket_state, event}) => {
  const key = `ticket_${index}`
  const ticket_info = state[key] || {}
  const first_name_field = {
    name: key + 'first_name',
    placeholder: 'first name',
    show_label: false,
    help_text: index === 0 ? '' : "Leave blank if you don't know the guest's name.",
    required: !index
  }
  const last_name_field = {
    name: key + 'last_name',
    placeholder: 'last name',
    show_label: false,
    help_text: index === 0 ? '' : "Leave blank if you don't know the guest's name.",
    required: !index
  }
  const email_field = {
    name: key + 'email',
    type: 'email',
    placeholder: 'email',
    show_label: false,
    help_text: index === 0 ? '' : "Leave blank if you don't know the guest's email address.",
    required: true
  }
  const extra_field = {
    name: key + 'extra',
    title: event.ticket_extra_title,
    help_text: event.ticket_extra_help_text
  }

  let title = `Guest ${index + 1}'s Details`
  const name = `${ticket_info.first_name || ''} ${ticket_info.last_name || ''}`
  if (index === 0) {
    title = 'Your Details (required)'
  } else if (name && name.endsWith('s')) {
    title = `${name}' Details`
  } else if (name !== ' ') {
    title = `${name}'s Details`
  }
  return (
    <div className="mb-1 pb-1">
      <h5>{title}</h5>
      <Row>
        <Col lg="4" md="6">
          <Input className="my-0"
                value={ticket_info.first_name}
                field={first_name_field}
                onChange={v => set_ticket_state(key, 'first_name', v)}/>
        </Col>
        <Col lg="4" md="6">
          <Input className="my-0"
                value={ticket_info.last_name}
                field={last_name_field}
                onChange={v => set_ticket_state(key, 'last_name', v)}/>
        </Col>
        <Col lg="4">
          <Input className="my-0"
                value={ticket_info.email}
                field={email_field}
                onChange={v => set_ticket_state(key, 'email', v)}/>
        </Col>
      </Row>
      {event.ticket_extra_title &&
        <Input value={ticket_info.extra_info}
               field={extra_field}
               onChange={v => set_ticket_state(key, 'extra_info', v)}/>
      }
    </div>
  )
}

const TicketForm = props => {
  const state = props.state
  const remaining = state.booking_info ? state.booking_info.tickets_remaining : null
  const existing_tickets = state.booking_info ? state.booking_info.existing_tickets : null
  const ticket_types = state.booking_info ? state.booking_info.ticket_types : []
  if (remaining !== null && remaining < 1) {
    return (
      <div>
        <h3>Sold out!</h3>
        <p>No more tickets available</p>
      </div>
    )
  }
  const max_tickets = Math.min(MAX_TICKETS, remaining || MAX_TICKETS)
  const change_count = props.change_ticket_count

  let items = [
    {name: 'Tickets', value: state.ticket_count},
    {name: 'Ticket Price', value: <div>&mdash;</div>},
    {name: 'Total Price', value: <div>&mdash;</div>},
  ]
  let ticket_price = null
  if (ticket_types.length === 1 || props.state.ticket_type) {
    ticket_price = ticket_types.length && (
      props.state.ticket_type ?
        ticket_types.find(tt => tt.id === props.state.ticket_type).price :
        ticket_types[0].price
    )
    let total = state.ticket_count * ticket_price
    if (ticket_price && state.ticket_0 && state.ticket_0.cover_costs) {
      total = total * (1 + props.event.cover_costs_percentage / 100)
    }
    items = [
      {name: 'Tickets', value: state.ticket_count},
      {name: 'Ticket Price', value: <MoneyFree>{ticket_price}</MoneyFree>},
      {name: 'Total Price', value: <MoneyFree>{total}</MoneyFree>},
    ]
  }

  return (
    <BootstrapForm onSubmit={props.reserve}>
      <Overlay element_id="modal-body" show={state.submitting_reservation} text="reserving tickets"/>
      <ModalBody id="modal-body">
        <Row className="justify-content-between">
          <div>
            {existing_tickets ?
              <b>
                You've already booked {existing_tickets} ticket{existing_tickets > 1 ? 's': ''} for this event.
              </b>
              :
              null
            }
          </div>
          <User {...props}/>
        </Row>
        {ticket_types.length > 1 &&
          <div className="py-2">
            <div className="text-center font-weight-bold">
              Ticket Types
            </div>
            <div className="px-4 pb-2">
              {ticket_types.map(tt => (
                <label key={tt.id} className="d-block">
                  <input
                    className="mr-2"
                    type="radio"
                    checked={props.state.ticket_type === tt.id}
                    onChange={() => props.set_ticket_type(tt.id)}
                  />
                  <b><MoneyFree>{tt.price}</MoneyFree></b> &mdash; {tt.name}
                </label>
              ))}
            </div>
            <div className="text-muted text-center small">
              Select which type of ticket you wish to purchase.
              Please note that you can only buy one ticket type at a time. If you wish to buy different ticket types,
              return to "book now" after your initial ticket is booked.
            </div>
          </div>
        }

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

        <Row className="mt-1 mb-2">
          <Col lg={{size: 8, offset: 2}}>
            <PricingList className="mb-2" items={items}/>

            {props.event.allow_marketing_message &&
              <Input value={state.ticket_0 && state.ticket_0.allow_marketing}
                     field={{name: 'allow_marketing', title: props.event.allow_marketing_message, type: 'bool'}}
                     onChange={v => props.set_ticket_state('ticket_0', 'allow_marketing', v)}/>
            }

            {props.event.cover_costs_message && props.event.cover_costs_percentage !== null &&
              <Input value={state.ticket_0 && state.ticket_0.cover_costs}
                     field={{name: 'cover_costs', title: props.event.cover_costs_message, type: 'bool'}}
                     onChange={v => props.set_ticket_state('ticket_0', 'cover_costs', v)}/>
            }
          </Col>
        </Row>

        {state.reservation_error &&
          <FormFeedback className="text-center d-block">{state.reservation_error}</FormFeedback>}

        <div className="multiple-items">
          {[...Array(state.ticket_count).keys()].map(i => (
            <TicketInfo key={i} index={i} state={state} set_ticket_state={props.set_ticket_state} event={props.event}/>
          ))}
        </div>
      </ModalBody>
      <ModalFooter finished={props.finished}
                   cancel_disabled={state.submitting_reservation}
                   label="Book"
                   disabled={state.submitting_reservation || (ticket_types.length > 1 && !props.state.ticket_type)}/>
    </BootstrapForm>
  )
}
export default WithContext(TicketForm)
