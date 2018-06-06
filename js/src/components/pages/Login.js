import React, {Component} from 'react'
import {Redirect} from 'react-router'
import {Row, Col} from 'reactstrap'


export default class Login extends Component {
  constructor (props) {
    super(props)
    this.state = {redirect_to: null}
    this.on_message = this.on_message.bind(this)
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

  componentDidMount () {
    window.addEventListener('message', this.on_message)
  }

  render () {
    if (this.state.redirect_to) {
      return <Redirect to={this.state.redirect_to}/>
    }
    return (
      <Row className="justify-content-center">
        <Col md="4" className="login">
          <h1 className="text-center">Login</h1>
          <iframe
            id="login-iframe"
            title="Login"
            frameBorder="0"
            scrolling="no"
            sandbox="allow-forms allow-scripts"
            src="/login/iframe.html"/>
        </Col>
      </Row>
    )
  }
}
