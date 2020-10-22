import React from 'react'
import {
  Button,
  Col,
  Collapse,
  FormFeedback,
  ModalBody,
  Row,
} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import WithContext from '../utils/context'
import requests from '../utils/requests'
import Input from '../forms/Input'
import {setup_siw, google_login} from '../auth/login_with'
import Recaptcha from '../general/Recaptcha'
import {ModalFooter} from '../general/Modal'

const first_name_field = {
  name: 'first_name',
  required: true,
}
const last_name_field = {
  name: 'last_name',
  required: true,
}
const email_field = {
  name: 'email',
  type: 'email',
  required: true,
}

class BookingLogin extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      email: null,
      siw_error: null,
      email_error: null,
      submitting: false,
    }
    this.auth = this.auth.bind(this)
  }

  componentDidMount () {
    setup_siw()
  }

  async google_auth () {
    this.setState({siw_error: null, submitting: true})
    const auth_data = await google_login(this.props.ctx.setError)
    if (auth_data) {
      await this.auth('google', auth_data)
    } else {
      this.setState({submitting: false})
    }
  }

  async email_auth (e) {
    e.preventDefault()
    this.setState({email_error: null, submitting: true})
    if (this.state.email) {
      const data = {
        first_name: this.state.first_name,
        last_name: this.state.last_name,
        email: this.state.email,
        grecaptcha_token: this.state.grecaptcha_token,
      }
      const error_msg = await this.auth('email', data, [200, 470])
      error_msg && this.setState({email_error: error_msg})
      Recaptcha.reset()
    }
  }

  async auth (site, login_data, status) {
    let data
    try {
      data = await requests.post(`/signup/guest/${site}/`, login_data, {expected_statuses: status || 200})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    if (data._response_status !== 200) {
      this.setState({submitting: false})
      return data.message
    } else {
      this.props.ctx.setUser(data.user)
      this.props.setBookingState({
        reservation: null,
        ticket_0: {
          first_name: data.user.first_name,
          last_name: data.user.last_name,
          email: data.user.email,
        }
      })
    }
  }

  email_button () {
    if (this.state.email_form) {
      if (this.state.grecaptcha_token) {
        this.setState({email_error: null})
        document.getElementById('submit-button').click()
      } else {
        this.setState({email_error: 'Captcha required'})
      }
    } else {
      this.setState({email_form: true})
    }
  }

  render () {
    return [
      <ModalBody key="1">
        <p className="text-center">{this.props.message}</p>

        <Row className="justify-content-center">
          <Col md="6">

            <a className="width-100p my-1 btn btn-primary"
               href={`/login/?next=${window.location.pathname}`}>
              <FontAwesomeIcon icon="sign-in-alt" className="mr-2"/>
              Login
            </a>

            <Button disabled={this.state.email_form || this.state.submitting}
                    onClick={this.google_auth.bind(this)}
                    color="primary"
                    className="width-100p my-1">
              <FontAwesomeIcon icon={['fab', 'google']} className="mr-2"/>
              Signup with Google
            </Button>

            <Collapse isOpen={this.state.email_form}>
              <Button onClick={() => this.setState({email_form: false})}
                      color="link" size="sm">
                Close
              </Button>
              <form onSubmit={this.email_auth.bind(this)}>
                <Input field={first_name_field}
                       value={this.state.first_name}
                       onChange={v => this.setState({first_name: v})}/>
                <Input field={last_name_field}
                       value={this.state.last_name}
                       onChange={v => this.setState({last_name: v})}/>
                <Input field={email_field}
                       value={this.state.email}
                       onChange={v => this.setState({email: v})}/>

                <Row className="justify-content-center mb-2">
                  <Recaptcha callback={grecaptcha_token => this.setState({grecaptcha_token, email_error: null})}/>
                </Row>
                <button type="submit" id="submit-button" className="d-none">submit</button>
              </form>
              {this.state.email_error && <FormFeedback className="d-block">{this.state.email_error}</FormFeedback>}
            </Collapse>
            <Button onClick={this.email_button.bind(this)} color="primary" className="width-100p my-1"
                    disabled={this.state.submitting}>
              <FontAwesomeIcon icon="at" className="mr-2"/>
              Signup with Email
            </Button>
          </Col>
        </Row>
      </ModalBody>,
      <ModalFooter key="2" finished={this.props.finished} disabled={true} label={this.props.success_label}/>
    ]
  }
}
export default WithContext(BookingLogin)
