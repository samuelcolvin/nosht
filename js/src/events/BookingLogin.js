import React from 'react'
import {
  Button,
  Col,
  FormFeedback,
  Input as BsInput,
  InputGroup,
  InputGroupAddon,
  ModalBody,
  Row,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {setup_siw, facebook_login, google_login} from '../auth/login_with'
import {ModalFooter} from '../general/Modal'


export default class BookingLogin extends React.Component {
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
    const auth_data = await google_login(this.props.setRootState)
    if (auth_data) {
      const error_msg = await this.auth('google', auth_data)
      error_msg && this.setState({siw_error: error_msg})
    }
  }

  async facebook_auth () {
    this.setState({siw_error: null})
    const auth_data = await facebook_login(this.props.setRootState)
    if (auth_data) {
      const error_msg = await this.auth('facebook', auth_data)
      error_msg && this.setState({siw_error: error_msg})
    }
  }

  async email_auth (e) {
    e.preventDefault()
    this.setState({email_error: null})
    if (this.state.email) {
      const error_msg = await this.auth('email', {email: this.state.email})
      error_msg && this.setState({email_error: error_msg})
    }
  }

  async auth (site, login_data) {
    let data
    try {
      data = await this.props.requests.post(`/login/guest/${site}/`, login_data, {expected_statuses: [200, 470]})
    } catch (error) {
      this.props.setRootState({error})
      return
    }
    if (data._response_status === 470) {
      return data.message
    } else {
      this.props.setRootState({user: data.user})
    }
  }

  render () {
    return [
      <ModalBody key="1">
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
                <BsInput type="email"
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
