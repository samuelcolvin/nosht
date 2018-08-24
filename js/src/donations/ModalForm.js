import React from 'react'
import {
  ModalBody,
  Form as BootstrapForm,
  Row,
  Col,
  Collapse,
} from 'reactstrap'
import AsModal, {SetModalTitle, ModalFooter} from '../general/Modal'
import Markdown from '../general/Markdown'
import {Money} from '../general/Money'
import {get_card, stripe_pay, StripeContext, StripeForm} from '../events/Stripe'
import Input from '../forms/Input'
import ReactGA from 'react-ga'

const gift_aid_field = {
  type: 'bool',
  name: 'gift_aid',
  title: 'Make my donation worth even more with Gift Aid',
  help_text: (  // TODO this needs to be a cat field so the link isn't too specific
    <span>
      Adding Gift Aid increases your donation by 25%, that’s £2.50 in every £10 – at no cost to you.
      To read more about Gift aid and donations which can’t include gift aid click&nbsp;
      <a href="https://handsupfoundation.org/news/gift-aid-the-low-down-on-increasing-your-donation-by-25"
         target="_blank" rel="noopener noreferrer">here</a>.
    </span>
  )
}

class DonateForm extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      gift_aid: false,
      submitting: false,
      submitted: false,
      payment: {},
    }
    this.stripe_pay = stripe_pay.bind(this)
  }

  componentDidMount () {
    if (!this.props.ctx.user) {
      this.props.ctx.setError('You must be logged in to make a donation')
      return
    }
    const stored_card = get_card(this.props.ctx.user)
    this.setState({
      first_name: this.props.ctx.user.first_name,
      first_name_error: null,
      last_name: this.props.ctx.user.last_name,
      last_name_error: null,
      address: stored_card.address_line1,
      address_error: null,
      city: stored_card.address_city,
      city_error: null,
      postcode: stored_card.address_zip,
      postcode_error: null,
    })
  }

  async submit (e) {
    e.preventDefault()
    this.setState({submitting: true})
    const data = {
      donation_option_id: this.props.donation_option.id,
      gift_aid: this.state.gift_aid,
      event_id: this.props.event.id,
      first_name: this.state.first_name,
      last_name: this.state.last_name,
      address: this.state.address,
      city: this.state.city,
      postcode: this.state.postcode,
    }
    const ok = await this.stripe_pay('donate/', data)
    if (ok) {
      this.props.ctx.setMessage({icon: ['fas', 'check-circle'], message: 'Donation successful, check your email'})
      ReactGA.event({
        category: 'donation',
        action: 'donation-complete',
        label: this.props.donation_option.id,
        value: Math.round(this.props.donation_option.amount * 100),
      })
      this.props.finished(true)
    }
  }

  render () {
    if (!this.props.ctx.user) {
      return null
    }
    const can_submit = !this.state.submitting && (this.state.payment.complete || this.state.payment.source_hash)

    const first_name_field = {name: 'first_name', required: this.state.gift_aid}
    const last_name_field = {name: 'last_name', required: this.state.gift_aid}
    const address_field = {name: 'address', required: this.state.gift_aid}
    const city_field = {name: 'city', required: this.state.gift_aid}
    const postcode_field = {name: 'postcode', required: this.state.gift_aid}

    const opt = this.props.donation_option
    return (
      <BootstrapForm className="pad-less" onSubmit={this.submit.bind(this)}>
        <SetModalTitle>
          {opt.name} &bull; <Money>{opt.amount}</Money> donation
        </SetModalTitle>
        <ModalBody key="mb">
          <div>
            <div className="text-center">
              {opt.image &&
                <img src={opt.image} className="img-fluid" alt={opt.name}/>
              }
            </div>
            <Markdown content={opt.long_description}/>
          </div>
          <Row className="justify-content-center">
            <Col lg="8">
              <hr/>
              <Input field={gift_aid_field} value={this.state.gift_aid}
                     disabled={this.state.submitted || this.state.submitting}
                     set_value={gift_aid => this.setState({gift_aid})}/>

              <Collapse isOpen={this.state.gift_aid}>
                <Row>
                  <Col md="6">
                    <Input field={first_name_field} value={this.state.first_name} error={this.state.first_name_error}
                           disabled={this.state.submitted || this.state.submitting}
                           set_value={v => this.setState({first_name: v, first_name_error: null})}/>
                  </Col>
                  <Col md="6">
                    <Input field={last_name_field} value={this.state.last_name} error={this.state.last_name_error}
                           disabled={this.state.submitted || this.state.submitting}
                           set_value={v => this.setState({last_name: v, last_name_error: null})}/>
                  </Col>
                </Row>
                <Input field={address_field} value={this.state.address} error={this.state.address_error}
                       disabled={this.state.submitted || this.state.submitting}
                       set_value={v => this.setState({address: v, address_error: null})}/>
                <Row>
                  <Col md="6">
                    <Input field={city_field} value={this.state.city} error={this.state.city_error}
                           disabled={this.state.submitted || this.state.submitting}
                           set_value={v => this.setState({city: v, city_error: null})}/>
                  </Col>
                  <Col md="6">
                    <Input field={postcode_field} value={this.state.postcode} error={this.state.postcode_error}
                           disabled={this.state.submitted || this.state.submitting}
                           set_value={v => this.setState({postcode: v, postcode_error: null})}/>
                  </Col>
                </Row>
              </Collapse>
              <hr/>
              <StripeForm
                  submitted={this.state.submitted}
                  payment_state={this.state.payment}
                  setPaymentState={payment => this.setState({payment})}>
              </StripeForm>
            </Col>
          </Row>
        </ModalBody>
        <ModalFooter finished={this.props.finished}
                     label={<span>Donate <Money>{opt.amount}</Money></span>}
                     cancel_disabled={this.state.submitting}
                     disabled={!can_submit}/>
      </BootstrapForm>
    )
  }
}
export default AsModal(StripeContext(DonateForm))
