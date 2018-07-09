import React from 'react'
import {
  Col,
  Form as BootstrapForm,
  FormFeedback,
  FormGroup,
  Label,
  ModalBody,
  Row,
} from 'reactstrap'
import {StripeProvider, Elements, CardElement, injectStripe} from 'react-stripe-elements'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {ModalFooter} from '../general/Modal'
import {load_script} from '../utils'
import Input from '../forms/Input'
import {User} from './BookingTickets'

const stripe_styles = {
  invalid: {
    // from bootstrap > _variables.scss > $form-feedback-invalid-color
    color: '#dc3545'
  }
}

const currency_lookup = {
  gbp: '£',
  usd: '$',
  eur: '€',
}
const name_field = {
  name: 'billing_name',
  required: true,
}
const address_field = {
  name: 'billing_address',
  required: true,
}
const city_field = {
  name: 'billing_city',
  required: true,
}
const postcode_field = {
  name: 'billing_postcode',
  required: true,
}

class StripeForm_ extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      time_left: 600,
      card_error: null,
      card_complete: false,
      submitted: false,
      name: props.user_name,
      address: null,
      city: null,
      postcode: null,
    }
    this.clear = setInterval(() => {
      const t = 600 + props.reservation.reserve_time - (new Date()).getTime() / 1000
      this.setState({time_left: Math.floor(t / 60)})
    }, 500)
    this.as_price = p => (
      currency_lookup[this.props.event.currency] + (p/100).toPrecision(2)
    )
  }

  componentWillUnmount () {
    clearInterval(this.clear)
  }

  async take_payment (e) {
    e.preventDefault()
    this.setState({submitted: true})
    const payload = await this.props.stripe.createToken({
      name: this.state.name,
      address_line1: this.state.address,
      address_city: this.state.city,
      address_zip: this.state.postcode,
    })
    console.log('payload:', payload)
  }

  update_stripe_status (status) {
    this.setState({
      card_error: status.error && status.error.message,
      card_complete: status.complete,
    })
  }

  render () {
    const res = this.props.reservation
    const items = [
      {
        name: 'Reservation expires in',
        value: `${this.state.time_left} minutes`,
        className: this.state.time_left < 3 ? 'mb-4 has-error h4' : 'mb-4'
      },
      {name: 'Tickets', value: res.ticket_count},
      {name: 'Ticket Price', value: this.as_price(res.item_price_cent)},
      {name: 'Total Price', value: this.as_price(res.total_price_cent)},
    ]
    const expired = this.state.time_left < 1
    return (
      <BootstrapForm className="pad-less" onSubmit={this.take_payment.bind(this)}>
        <ModalBody>
          <User {...this.props}/>
          <Row className="justify-content-center">
            <Col md="8">
              <div className="mb-2">
                {items.map((item, i) => (
                  <div key={i} className={`d-flex justify-content-between ${item.className || ''}`}>
                    <div>{item.name}:</div>
                    <div className="font-weight-bold">{item.value}</div>
                  </div>
                ))}
              </div>
              <hr/>
              {
                expired ?
                <h4 className="has-error">Rervation expired</h4>
                :
                <div>
                  <Input field={name_field}
                         value={this.state.name}
                         set_value={v => this.setState({name: v})}/>
                  <Input field={address_field}
                         value={this.state.address}
                         set_value={v => this.setState({address: v})}/>
                  <Row>
                    <Col md="6">
                      <Input field={city_field}
                             value={this.state.city}
                             set_value={v => this.setState({city: v})}/>
                    </Col>
                    <Col md="6">
                      <Input field={postcode_field}
                             value={this.state.postcode}
                             set_value={v => this.setState({postcode: v})}/>
                    </Col>
                  </Row>
                  <FormGroup>
                    <Label className="required">
                      Card Details
                    </Label>
                    <CardElement className="py-2 px-1"
                                 hidePostalCode={true}
                                 onChange={this.update_stripe_status.bind(this)}
                                 style={stripe_styles}/>
                    {
                      this.state.card_error &&
                      <FormFeedback style={{display: 'block'}}>
                        <FontAwesomeIcon icon="times" className="mr-1"/>
                        {this.state.card_error}
                      </FormFeedback>
                    }
                  </FormGroup>
                </div>
              }
            </Col>
          </Row>
        </ModalBody>
        <ModalFooter finished={this.props.finished}
                     label="Take Payment"
                     disabled={expired || this.state.submitted || !this.state.card_complete}/>
      </BootstrapForm>
    )
  }
}
const StripeForm = injectStripe(StripeForm_)

export default class Stripe extends React.Component {
  constructor (props) {
    super(props)
    this.state = {stripe: null}
  }

  async componentDidMount () {
    await load_script('https://js.stripe.com/v3/')
    this.setState({stripe: window.Stripe(this.props.event.stripe_key)})
  }

  render () {
    return (
      <StripeProvider stripe={this.state.stripe}>
        <Elements>
          <StripeForm {...this.props} stripe={this.state.stripe}/>
        </Elements>
      </StripeProvider>
    )
  }
}
