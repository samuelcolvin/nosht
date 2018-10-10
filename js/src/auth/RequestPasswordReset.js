import React from 'react'
import {Row, Col, Button} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import Recaptcha from '../general/Recaptcha'
import requests from '../utils/requests'
import WithContext from '../utils/context'
import Input from '../forms/Input'

const FIELD = {
  name: 'email',
  type: 'email',
  required: true,
  placeholder: 'me@example.com',
}

class RequestPasswordReset extends React.Component {
  constructor (props) {
    super(props)
    this.state = {enabled: false, email: null, grecaptcha_token: null}
  }

  componentDidMount () {
    this.props.ctx.setRootState({active_page: 'login'})
  }

  async submit (e) {
    e.preventDefault()
    this.setState({enabled: false})
    try {
      await requests.post('reset-password/', {email: this.state.email, grecaptcha_token: this.state.grecaptcha_token})
    } catch (error) {
      this.props.ctx.setError(error)
      return
    }
    this.props.history.replace('/')
    this.props.ctx.setMessage({
      icon: 'at',
      message: 'Password reset email sent if you entered a valid email address, check your emails.'})
  }

  render () {
    return (
      <div>
        <div className="text-center mb-4">
          <h1>Password Reset</h1>
          To reset your password, please enter your account email address.
        </div>

        <Row className="justify-content-center">
          <Col xl="4" lg="6" md="8">
            <form onSubmit={this.submit.bind(this)} className="hide-form-label">
              <Row className="justify-content-center mb-2">
                <Recaptcha callback={grecaptcha_token => this.setState({grecaptcha_token, enabled: true})}/>
              </Row>
              <Input field={FIELD} value={this.state.email} onChange={email => this.setState({email})}/>
              <Button color="primary" className="width-100p my-1"
                      disabled={!this.state.enabled}>
                <FontAwesomeIcon icon="unlock-alt" className="mr-2"/>
                Reset Password
              </Button>
            </form>
          </Col>
        </Row>
      </div>
    )
  }
}

export default WithContext(RequestPasswordReset)
