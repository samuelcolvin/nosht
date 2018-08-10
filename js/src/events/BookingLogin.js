import React from 'react'
import {
  Button,
  Col,
  FormFeedback,
  Input,
  InputGroup,
  InputGroupAddon,
  ModalBody,
  Row,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import WithContext from '../utils/context'
import requests from '../utils/requests'
import {grecaptcha_execute} from '../utils'
import {setup_siw, facebook_login, google_login} from '../auth/login_with'
import {ModalFooter} from '../general/Modal'


class BookingLogin extends React.Component {
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
    const auth_data = await google_login(this.props.ctx.setError)
    if (auth_data) {
      await this.auth('google', auth_data)
    }
  }

  async facebook_auth () {
    this.setState({siw_error: null})
    const auth_data = await facebook_login(this.props.ctx.setError)
    if (auth_data) {
      await this.auth('facebook', auth_data)
    }
  }

  async email_auth (e) {
    e.preventDefault()
    this.setState({email_error: null})
    if (this.state.email) {
      const error_msg = await this.auth('email', {email: this.state.email}, [200, 470])
      error_msg && this.setState({email_error: error_msg})
    }
  }

  async auth (site, login_data, status) {
    login_data.grecaptcha_token = await grecaptcha_execute('guest_signup')
    let data
    try {
      data = await requests.post(`/signup/guest/${site}/`, login_data, {expected_statuses: status || 200})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    if (data._response_status !== 200) {
      return data.message
    } else {
      this.props.ctx.setUser(data.user)
      this.props.clear_reservation()
    }
  }

  render () {
    return [
      <ModalBody key="1">
        <p className="text-center">{this.props.event.booking_trust_message}</p>
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
                <Input type="email"
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
      </ModalBody>,
      <ModalFooter key="2" finished={this.props.finished} disabled={true}/>
    ]
  }
}
export default WithContext(BookingLogin)
