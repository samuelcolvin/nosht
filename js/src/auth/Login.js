import React from 'react'
import {Row, Col, Button, FormFeedback} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import ReactGA from 'react-ga'
import {Link} from 'react-router-dom'
import Recaptcha from '../general/Recaptcha'
import requests from '../utils/requests'
import WithContext from '../utils/context'
import {user_full_name, sleep} from '../utils'
import {setup_siw, google_login} from './login_with'
import IFrame from '../general/IFrame'

export const next_url = location => {
  const match = location.search.match('next=([^&]+)')
  const next = match ? decodeURIComponent(match[1]) : null
  return next === '/logout/' || next === null ? null : next
}

export async function authenticate (data) {
  try {
    await requests.post('auth-token/', {token: data.auth_token})
  } catch (error) {
    this.props.ctx.setError(error)
    return
  }
  this.props.ctx.setUser(data.user)
  this.props.history.replace(next_url(this.props.location) || '/dashboard/events/')
  this.props.ctx.setMessage({icon: 'user', message: `Logged in successfully as ${user_full_name(data.user)}`})
  window.sessionStorage.clear()
}
const recaptcha_callback = grecaptcha_token => (
  document.getElementById('login-iframe').contentWindow.postMessage(JSON.stringify({grecaptcha_token}), '*')
)


class Login extends React.Component {
  constructor (props) {
    super(props)
    this.state = {error: null, recaptcha_shown: false}
    this.on_message = this.on_message.bind(this)
    this.authenticate = authenticate.bind(this)
    this.login_with = this.login_with.bind(this)
  }

  async on_message (event) {
    if (event.origin !== 'null') {
      return
    }
    if (event.data === 'grecaptcha-reset') {
      if (this.state.recaptcha_shown) {
        Recaptcha.reset()
      } else {
        this.setState({recaptcha_shown: true})
        document.getElementById('login-iframe').contentWindow.postMessage('{"grecaptcha_required": true}', '*')
      }
      return
    }

    const data = JSON.parse(event.data)
    if (data.status !== 'success') {
      this.props.ctx.setError(data)
      return
    }
    ReactGA.event({category: 'auth', action: 'auth-login', label: 'email'})
    await this.authenticate(data)
  }

  async componentDidMount () {
    window.addEventListener('message', this.on_message)
    this.props.ctx.setUser(null)
    this.props.ctx.setRootState({active_page: 'login'})
    await setup_siw()

    let r
    try {
      r = await requests.get('/login/captcha/')
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    if (r.captcha_required) {
      this.setState({recaptcha_shown: true})
      await sleep(2000)
      document.getElementById('login-iframe').contentWindow.postMessage('{"grecaptcha_required": true}', '*')
    }
  }

  componentWillUnmount () {
    window.removeEventListener('message', this.on_message)
  }

  async login_with (site, login_data) {
    ReactGA.event({category: 'auth', action: 'auth-login', label: site})
    let data
    try {
      data = await requests.post(`/login/${site}/`, login_data, {expected_statuses: [200, 470]})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    if (data._response_status === 470) {
      this.setState({error: data.message})
    } else {
      await this.authenticate(data)
    }
  }

  async google_auth () {
    this.setState({error: null})
    const auth_data = await google_login(this.props.ctx.setError)
    if (!auth_data) {
      return
    }
    await this.login_with('google', auth_data)
  }

  render () {
    const next = next_url(this.props.location)
    return (
      <div>
        <Row className="justify-content-center mb-2">
          <Col lg="6">
            <h1 className="text-center">Login</h1>
            {next ?
              <div className="text-center mb-2">
                Login to view <code>{next}</code>.
              </div>
              :
              <div className="text-center mb-2">
                Not yet a user? Go to <Link to="/signup/">Sign up</Link> to create an account
                and start hosting events.
              </div>
            }
          </Col>
        </Row>

        <Row className="justify-content-center">
          <Col xl="4" lg="6" md="8" className="text-center my-1">
            <Button onClick={this.google_auth.bind(this)} color="primary">
              <FontAwesomeIcon icon={['fab', 'google']} className="mr-2"/>
              Login with Google
            </Button>
            <hr className="mt-4 mb-0"/>
          </Col>
        </Row>

        {this.state.error &&
          <div className="text-center mt-2">
            <FormFeedback className="d-block">{this.state.error}</FormFeedback>
          </div>
        }

        {this.state.recaptcha_shown && (
          <Row className="justify-content-center mt-4">
            <Recaptcha callback={recaptcha_callback}/>
          </Row>
        )}

        <Row className="justify-content-center">
          <Col xl="4" lg="6" md="8" className="login">
            <IFrame id="login-iframe" title="Login" src="/iframes/login.html"/>
          </Col>
        </Row>
        <div className="text-center">
          <Button tag={Link} to="/password-reset/" color="link" size="sm">Reset Password</Button>
        </div>
      </div>
    )
  }
}

export default WithContext(Login)
