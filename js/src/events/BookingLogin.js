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
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import WithContext from '../utils/context'
import requests from '../utils/requests'
import {setup_siw, facebook_login, google_login} from '../auth/login_with'
import {ModalFooter} from '../general/Modal'


class BookingLogin extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      email: '',
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

  async facebook_auth () {
    this.setState({siw_error: null, submitting: true})
    const auth_data = await facebook_login(this.props.ctx.setError)
    if (auth_data) {
      await this.auth('facebook', auth_data)
    } else {
      this.setState({submitting: false})
    }
  }

  async email_auth (e) {
    e.preventDefault()
    this.setState({email_error: null, submitting: true})
    if (this.state.email) {
      const error_msg = await this.auth('email', {email: this.state.email}, [200, 470])
      error_msg && this.setState({email_error: error_msg})
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
      this.props.clear_reservation()
    }
  }

  render () {
    return [
      <ModalBody key="1">
        <p className="text-center">{this.props.event.booking_trust_message}</p>
        <Row>
          <Col lg={{size: 4, offset: 2}} md="6" className="text-center text-md-left my-1">
              <Button disabled={this.state.submitting} onClick={this.google_auth.bind(this)} color="primary">
                <FontAwesomeIcon icon={['fab', 'google']} className="mr-2"/>
                Signup with Google
              </Button>
          </Col>
          <Col lg="4" md="6" className="text-center text-md-right my-1">
              <Button disabled={this.state.submitting} onClick={this.facebook_auth.bind(this)} color="primary">
                <FontAwesomeIcon icon={['fab', 'facebook-f']} className="mr-2"/>
                Signup with Facebook
              </Button>
          </Col>
        </Row>
        <div className="text-center text-muted my-1">
          <small>Or</small>
        </div>
        <form onSubmit={this.email_auth.bind(this)}>
          <Row className="justify-content-center my-1">
            <Col lg="8">
              <InputGroup>
                <Input type="email"
                       invalid={!!this.state.email_error}
                       value={this.state.email}
                       required={true}
                       disabled={this.state.submitting}
                       onChange={e => this.setState({email: e.target.value})}/>

                <InputGroupAddon addonType="append">
                  <Button color="primary" disabled={this.state.submitting}>Signin with Email</Button>
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
