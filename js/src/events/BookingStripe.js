import React from 'react'
import {
  Col,
  Form as BootstrapForm,
  ModalBody,
  Row,
} from 'reactstrap'
import {StripeProvider, Elements, CardElement, injectStripe} from 'react-stripe-elements'
import {ModalFooter} from '../general/Modal'


const STRIPE_STYLES = {
  invalid: {
    // from bootstrap > _variables.scss > $form-feedback-invalid-color
    color: '#dc3545'
  }
}

const StripeForm_ = props => {
  // console.log(props)
  return (
    <BootstrapForm onSubmit={e => props.take_payment(e, props.stripe)}>
      <ModalBody>
        <Row className="justify-content-center">
          <Col md="8">
            <div>
              <div>timer: {props.reservation.reserve_time} (prevent purchase near timeout)</div>
              <div>ticket count: {props.reservation.ticket_count}</div>
              <div>ticket price: {props.reservation.price_cent/100}</div>
            </div>
            <CardElement className="py-2 px-1"
                         hidePostalCode={true}
                         onChange={c => console.log('changed:', c)}
                         style={STRIPE_STYLES}/>
          </Col>
        </Row>
      </ModalBody>
      <ModalFooter finished={props.finished} label="Pay"/>
    </BootstrapForm>
  )
}
const StripeForm = injectStripe(StripeForm_)

export default class Stripe extends React.Component {
  constructor (props) {
    super(props)
    this.state = {stripe: null}
    this.stripe = window.Stripe(this.props.event.stripe_key)
  }

  async take_payment (e, stripe) {
    e.preventDefault()
    const payload = await stripe.createToken({name: this.props.user_name})
    console.log('payload:', payload)
  }

  render () {
    return (
      <StripeProvider stripe={this.stripe}>
        <Elements>
          <StripeForm {...this.props} take_payment={this.take_payment.bind(this)}/>
        </Elements>
      </StripeProvider>
    )
  }
}
