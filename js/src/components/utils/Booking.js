import React from 'react'
import {
  Button,
  Col,
  Collapse,
  FormFeedback,
  Input as BsInput,
  InputGroup,
  InputGroupAddon,
  Row,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {setup_siw, facebook_login, google_login} from '../../login_with'
import Input from '../forms/Input'

export class BookingLogin extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      email: '',
      siw_error: null,
      email_error: null,
    }
    this.auth = this.auth.bind(this)
  }

  componentDidMount () {
    setup_siw()
  }

  async google_auth () {
    this.setState({siw_error: null})
    const auth_data = await google_login(this.props.setRootState)
    if (auth_data) {
      const error_msg = await this.auth('google', auth_data)
      error_msg && this.setState({siw_error: error_msg})
    }
  }

  async facebook_auth () {
    this.setState({siw_error: null})
    const auth_data = await facebook_login(this.props.setRootState)
    if (auth_data) {
      const error_msg = await this.auth('facebook', auth_data)
      error_msg && this.setState({siw_error: error_msg})
    }
  }

  async email_auth (e) {
    e.preventDefault()
    this.setState({email_error: null})
    if (this.state.email) {
      const error_msg = await this.auth('email', {email: this.state.email})
      error_msg && this.setState({email_error: error_msg})
    }
  }

  async auth (site, login_data) {
    let data
    try {
      data = await this.props.requests.post(`/login/guest/${site}/`, login_data, {expected_statuses: [200, 470]})
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    if (data._response_status === 470) {
      return data.message
    } else {
      this.props.setRootState({user: data.user})
    }
  }

  render () {
    return (
      <div>
        <Row className="justify-content-center my-1">
          <Col md="8">
            <div className="d-flex justify-content-between">
              <Button onClick={this.google_auth.bind(this)} color="primary">
                <FontAwesomeIcon icon={['fab', 'google']} className="mr-2"/>
                Signup with Google
              </Button>
              <Button onClick={this.facebook_auth.bind(this)} color="primary">
                <FontAwesomeIcon icon={['fab', 'facebook-f']} className="mr-2"/>
                Signup with Facebook
              </Button>
            </div>
          </Col>
        </Row>
        <div className="text-center text-muted my-1">
          <small>Or</small>
        </div>
        <form onSubmit={this.email_auth.bind(this)}>
          <Row className="justify-content-center my-1">
            <Col md="8">
              <InputGroup>
                <BsInput type="email"
                         invalid={!!this.state.email_error}
                         required value={this.state.email}
                         onChange={e => this.setState({email: e.target.value})}/>

                <InputGroupAddon addonType="append">
                  <Button color="primary">Signin with Email</Button>
                </InputGroupAddon>
                {this.state.email_error && <FormFeedback>{this.state.email_error}</FormFeedback>}
              </InputGroup>
            </Col>
          </Row>
        </form>
      </div>
    )
  }
}

export const User = ({user, logout}) => (
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

export const TicketInfo = ({index, state, set_ticket_state, user}) => {
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

export const TicketForm = ({user, state, logout, set_ticket_state, change_ticket_count, booking_info}) => {
  const remaining = (booking_info || {}).tickets_remaining
  if (!(remaining >= 1)) {
    return (
      <div>
        <h3>Sold out!</h3>
        <p>No more tickets available</p>
      </div>
    )
  }
  const max_tickets = Math.min(10, (booking_info || {}).tickets_remaining || 10)
  return (
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
        <Button color="success" disabled={state.ticket_count === max_tickets} onClick={() => change_ticket_count(1)}>
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
}
