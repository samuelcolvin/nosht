import React from 'react'
import WithContext from '../utils/context'
import {Row, Col} from 'reactstrap'
import {authenticate} from './Login'
import IFrame from '../general/IFrame'

class SetPassword extends React.Component {
  constructor (props) {
    super(props)
    this.on_message = this.on_message.bind(this)
    this.authenticate = authenticate.bind(this)
  }

  async on_message (event) {
    if (event.origin !== 'null') {
      return
    }

    const data = JSON.parse(event.data)
    if (data.status !== 'success') {
      this.props.ctx.setError(data)
      return
    }
    await this.authenticate(data)
  }

  async componentDidMount () {
    window.addEventListener('message', this.on_message)
    this.props.ctx.setRootState({active_page: 'login'})
  }

  componentWillUnmount () {
    window.removeEventListener('message', this.on_message)
  }

  render () {
    return [
      <div key="1" className="d-flex justify-content-center">
          <h1 className="text-center">Set Password</h1>
      </div>,
      <Row key="2" className="justify-content-center">
        <Col md="4" className="password-reset">
          <IFrame title="Set Password" src={`/iframes/set-password.html${window.location.search}`}/>
        </Col>
      </Row>
    ]
  }
}
export default WithContext(SetPassword)
