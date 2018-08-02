import React from 'react'
import {
  Button,
  Col,
  Card,
  CardTitle,
  CardText,
  Form as BootstrapForm,
  FormFeedback,
  ModalBody,
  Row,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {format_money_free, user_full_name} from '../utils'
import Input from '../forms/Input'
import {ModalFooter} from '../general/Modal'
import {PricingList} from './BookingStripe'


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
          {user_full_name(this.props.user)}
        </small>
        <Button onClick={this.logout.bind(this)} color="link" size="sm" className="pl-1 pr-0">
          (Logout)
        </Button>
      </div>
    )
  }
}

const TicketInfo = ({index, state, set_ticket_state, user, event}) => {
  const key = `ticket_${index}`
  const ticket_info = state[key] || {}
  const first_name_field = {
    name: key + 'first_name',
    placeholder: 'first name',
    show_label: false,
    help_text: index === 0 ? '' : "Leave blank if you don't know the guest's name."
  }
  const last_name_field = {
    name: key + 'last_name',
    placeholder: 'last name',
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
  const extra_field = {
    name: key + 'extra',
    title: event.ticket_extra_title,
    help_text: event.ticket_extra_help_text
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
        <Col md="4">
          <Input className="my-0"
                value={!ticket_info.first_name && index === 0 && user.first_name ?
                       user.first_name : ticket_info.first_name}
                field={first_name_field}
                set_value={v => set_ticket_state(key, 'first_name', v)}/>
        </Col>
        <Col md="4">
          <Input className="my-0"
                value={!ticket_info.last_name && index === 0 && user.last_name ?
                       user.last_name :
                        ticket_info.last_name}
                field={last_name_field}
                set_value={v => set_ticket_state(key, 'last_name', v)}/>
        </Col>
        <Col md="4">
          <Input className="my-0"
                value={ticket_info.email === undefined && index === 0 ? user.email : ticket_info.email}
                field={email_field}
                set_value={v => set_ticket_state(key, 'email', v)}/>
        </Col>
      </Row>
      {event.ticket_extra_title &&
        <Input value={ticket_info.extra_info}
               field={extra_field}
               set_value={v => set_ticket_state(key, 'extra_info', v)}/>
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
  const max_tickets = Math.min(10, remaining || 10)
  const change_count = props.change_ticket_count

  const ticket_price = ticket_types.length && (
    props.state.ticket_type ?
      ticket_types.find(tt => tt.id === props.state.ticket_type).price :
      ticket_types[0].price
  )
  const items = [
    {name: 'Tickets', value: state.ticket_count},
    {name: 'Ticket Price', value: format_money_free(props.event.currency, ticket_price)},
    {name: 'Total Price', value: format_money_free(props.event.currency, state.ticket_count * ticket_price)},
  ]

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
        {ticket_types.length > 1 &&
          <div className="py-2">
            <div className="text-center font-weight-bold">
              Ticket Type
            </div>
            <Row className="d-flex justify-content-center my-1">
              {ticket_types.map(tt => (

                <Col key={tt.id} md="4" className="mb-3">
                  <Card body inverse color={props.state.ticket_type === tt.id ? 'primary': 'info'}
                        className={props.state.ticket_type === tt.id ? '': 'cursor-pointer select-image'}
                        onClick={() => props.set_ticket_type(tt.id)}>
                    <CardTitle className="text-center">{tt.name}</CardTitle>
                    <CardText className="text-center">
                      {format_money_free(props.event.currency, tt.price)}
                    </CardText>
                  </Card>
                </Col>
              ))}
            </Row>
            <div className="text-muted text-center small">
              Select which type of ticket you wish to purchase.
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
          <Col md={{size: 8, offset: 2}}>
            <PricingList className="mb-2" items={items}/>
          </Col>
        </Row>

        {state.reservation_error &&
          <FormFeedback className="text-center d-block">{state.reservation_error}</FormFeedback>}

        <div className="multiple-items">
          {[...Array(state.ticket_count).keys()].map(i => (
            <TicketInfo key={i} index={i} state={state} set_ticket_state={props.set_ticket_state}
                        user={props.user} event={props.event}/>
          ))}
        </div>
      </ModalBody>
      <ModalFooter finished={props.finished} disabled={ticket_types.length > 1 && !props.state.ticket_type}/>
    </BootstrapForm>
  )
}
export default TicketForm
