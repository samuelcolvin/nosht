import React from 'react'
import {Row, Col, Button, FormFeedback} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import requests from '../requests'
import WithContext from '../context'
import {grecaptcha_execute, user_full_name} from '../utils'
import {setup_siw, facebook_login, google_login} from './login_with'

class Login extends React.Component {
  constructor (props) {
    super(props)
    this.state = {redirect_to: null, error: null}
    this.on_message = this.on_message.bind(this)
    this.authenticate = this.authenticate.bind(this)
    this.login_with = this.login_with.bind(this)
  }

  async on_message (event) {
    if (event.origin !== 'null') {
      return
    }
    if (event.data === 'grecaptcha_token_request') {
      const grecaptcha_token = await grecaptcha_execute('login_password')
      document.getElementById('login-iframe').contentWindow.postMessage(grecaptcha_token, '*')
      return
    }

    const data = JSON.parse(event.data)
    if (data.status !== 'success') {
      this.props.ctx.setError(data)
      return
    }
    await this.authenticate(data)
  }

  async authenticate (data) {
    try {
      await requests.post('auth-token/', {token: data.auth_token})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.props.ctx.setRootState({user: data.user})
    this.props.history.replace('/dashboard/events/')
    this.props.ctx.setMessage({icon: 'user', message: `Logged in successfully as ${user_full_name(data.user)}`})
  }

  async componentDidMount () {
    window.addEventListener('message', this.on_message)
    this.props.ctx.setRootState({user: null})
    await setup_siw()
  }

  componentWillUnmount () {
    window.removeEventListener('message', this.on_message)
  }

  async login_with (site, login_data) {
    login_data.grecaptcha_token = await grecaptcha_execute(`login_with_${site}`)
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

  async facebook_auth () {
    this.setState({error: null})

    const auth_data = await facebook_login(this.props.ctx.setError)
    if (!auth_data) {
      return
    }
    await this.login_with('facebook', auth_data)
  }

  render () {
    return [
      <Row key="1" className="justify-content-center mb-2">
        <Col md="6">
          <h1 className="text-center">Login</h1>
          <div className="d-flex justify-content-around">
            <Button onClick={this.google_auth.bind(this)} color="primary">
              <FontAwesomeIcon icon={['fab', 'google']} className="mr-2"/>
              Login with Google
            </Button>
            <Button onClick={this.facebook_auth.bind(this)} color="primary">
              <FontAwesomeIcon icon={['fab', 'facebook-f']} className="mr-2"/>
              Login with Facebook
            </Button>
          </div>
        </Col>
        {this.state.error &&
          <Col md="12" className="text-center mt-2">
            <FormFeedback className="d-block">{this.state.error}</FormFeedback>
          </Col>
        }
      </Row>,
      <Row key="2" className="justify-content-center">
        <Col md="4" className="login">
          <iframe
            id="login-iframe"
            title="Login"
            frameBorder="0"
            scrolling="no"
            sandbox="allow-forms allow-scripts"
            src="/iframes/login.html"/>
        </Col>
      </Row>
    ]
  }
}

export default WithContext(Login)
