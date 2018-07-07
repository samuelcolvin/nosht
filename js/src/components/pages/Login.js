import React from 'react'
import {Redirect} from 'react-router'
import {Row, Col, Button, FormFeedback} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'

import {setup_siw, facebook_login, google_login} from '../../login_with'

export default class Login extends React.Component {
  constructor (props) {
    super(props)
    this.state = {redirect_to: null, error: null}
    this.on_message = this.on_message.bind(this)
    this.authenticate = this.authenticate.bind(this)
  }

  async on_message (event) {
    if (event.origin !== 'null') {
      return
    }

    const data = JSON.parse(event.data)
    if (data.status !== 'success') {
      this.props.setRootState({error: data})
      return
    }
    await this.authenticate(data)
  }

  async authenticate (data) {
    try {
      await this.props.requests.post('auth-token/', {token: data.auth_token})
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    this.props.setRootState({user: data.user})
    this.setState({redirect_to: '/'})
    this.props.set_message({icon: 'user', message: `Logged in successfully as ${data.user.name}`})
  }

  async componentDidMount () {
    window.addEventListener('message', this.on_message)
    this.props.setRootState({user: null})
    await setup_siw()
  }

  async google_auth () {
    this.setState({error: null})
    const auth_data = await google_login(this.props.setRootState)
    if (!auth_data) {
      return
    }

    let data
    try {
      data = await this.props.requests.post('/login/google/', auth_data, {expected_statuses: [200, 470]})
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    if (data._response_status === 470) {
      this.setState({error: data.message})
    } else {
      await this.authenticate(data)
    }
  }

  async facebook_auth () {
    this.setState({error: null})

    const auth_data = await facebook_login(this.props.setRootState)
    if (!auth_data) {
      return
    }

    let data
    try {
      data = await this.props.requests.post('/login/facebook/', auth_data, {expected_statuses: [200, 470]})
    } catch (error) {
      this.props.setRootState({error})
      return
    }

    if (data._response_status === 470) {
      this.setState({error: data.message})
    } else {
      await this.authenticate(data)
    }
  }

  render () {
    if (this.state.redirect_to) {
      return <Redirect to={this.state.redirect_to}/>
    }
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
            <FormFeedback style={{display: 'block'}}>{this.state.error}</FormFeedback>
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
            src="/login/iframe.html"/>
        </Col>
      </Row>
    ]
  }
}
