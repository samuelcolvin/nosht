import React from 'react'
import {Row, Col, Button} from 'reactstrap'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {grecaptcha_execute} from '../utils'
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
    this.state = {enabled: true, email: null}
  }

  componentDidMount () {
    this.props.ctx.setRootState({active_page: 'login'})
  }

  async submit (e) {
    e.preventDefault()
    this.setState({enabled: false})
    const grecaptcha_token = await grecaptcha_execute('reset_password')
    try {
      await requests.post('reset-password/', {email: this.state.email, grecaptcha_token})
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
          <Col md="4">
            <form onSubmit={this.submit.bind(this)} className="hide-form-label">
              <Input field={FIELD}
                    value={this.state.email}
                    set_value={v => this.setState({email: v})}/>
              <button type="submit" id="submit-button" className="d-none">submit</button>
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
