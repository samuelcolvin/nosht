import React from 'react'
import {Link} from 'react-router-dom'
import {
  Button,
  Col,
  Collapse,
  FormFeedback,
  Row,
} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import ReactGA from 'react-ga'
import WithContext from '../utils/context'
import requests from '../utils/requests'
import {user_full_name} from '../utils'
import Input from '../forms/Input'
import {setup_siw, google_login} from './login_with'
import {next_url} from './Login'
import Recaptcha from '../general/Recaptcha'

const name_field = {
  name: 'name',
  required: true,
}
const email_field = {
  name: 'email',
  type: 'email',
  required: true,
}

class Signup extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      name: '',
      email: '',
    }
    this.auth = this.auth.bind(this)
  }

  async componentDidMount () {
    setup_siw()
    this.props.ctx.setRootState({active_page: 'login'})
  }

  async google_auth () {
    this.setState({error: null})
    const auth_data = await google_login(this.props.ctx.setError)
    if (auth_data) {
      ReactGA.event({category: 'auth', action: 'auth-signup', label: 'google'})
      await this.auth('google', auth_data)
    }
  }

  async email_auth (e) {
    this.setState({error: null})
    e.preventDefault()
    if (this.state.email) {
      ReactGA.event({category: 'auth', action: 'auth-signup', label: 'email'})
      await this.auth('email', {email: this.state.email, name: this.state.name})
      Recaptcha.reset()
    }
  }

  email_button () {
    if (this.state.email_form) {
      if (this.state.grecaptcha_token) {
        this.setState({error: null})
        document.getElementById('submit-button').click()
      } else {
        this.setState({error: 'Captcha required'})
      }
    } else {
      this.setState({email_form: true})
    }
  }

  async auth (site, post_data) {
    if (this.state.grecaptcha_token) {
      post_data.grecaptcha_token = this.state.grecaptcha_token
    }
    let data
    try {
      data = await requests.post(`/signup/host/${site}/`, post_data, {expected_statuses: [200, 470]})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    const next = next_url(this.props.location)
    if (data._response_status === 470 && data.status === 'existing user') {
      this.props.history.push(next ? `/login/?next=${encodeURIComponent(next)}` : '/login/')
      this.props.ctx.setMessage({icon: 'user', message: 'User already exists - please login.'})
    } else if (data._response_status === 470) {
      this.setState({error: data.status})
    } else {
      this.props.ctx.setUser(data.user)
      let message
      if (site === 'email') {
        message = `Thanks for signing up as ${user_full_name(data.user)} - you'll receive an email asking you to ` +
                  `confirm your email address and set your password.`
      } else {
        message = `Signed up successfully as ${user_full_name(data.user)}`
      }
      this.props.ctx.setMessage({icon: 'user', message})
      this.props.history.replace(next || '/dashboard/events/')
    }
  }

  render () {
    return (
      <div>
        <div className="text-center mb-4">
          <h1>Signup</h1>
          To host events please signup for an account, or log in using your existing account.
        </div>

        <Row className="justify-content-center">
          <Col md="4">
            <Button tag={Link}
                    to="/login/"
                    color="primary"
                    className="width-100p my-1">
              <FontAwesomeIcon icon="sign-in-alt" className="mr-2"/>
              Login
            </Button>
            <div className="text-center text-muted my-2">
              <small>Or</small>
            </div>

            <Button disabled={this.state.email_form}
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
                <Input field={name_field}
                       value={this.state.name}
                       onChange={v => this.setState({name: v})}/>
                <Input field={email_field}
                       value={this.state.email}
                       onChange={v => this.setState({email: v})}/>

                <Row className="justify-content-center mb-2">
                  <Recaptcha callback={grecaptcha_token => this.setState({grecaptcha_token, error: null})}/>
                </Row>
                <button type="submit" id="submit-button" className="d-none">submit</button>
              </form>
              {this.state.error && <FormFeedback className="d-block">{this.state.error}</FormFeedback>}
            </Collapse>
            <Button onClick={this.email_button.bind(this)} color="primary" className="width-100p my-1">
              <FontAwesomeIcon icon="at" className="mr-2"/>
              Signup with Email
            </Button>
          </Col>
        </Row>
      </div>
    )
  }
}
export default WithContext(Signup)
