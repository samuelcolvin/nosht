import React from 'react'
import {
  Button,
  Col,
  Input,
  InputGroup,
  InputGroupAddon,
  Row,
} from 'reactstrap'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'

export class BookingLogin extends React.Component {
  constructor (props) {
    super(props)
    this.state = {
      email: '',
    }
  }

  render () {
    return (
      <div>
        <Row className="justify-content-center my-1">
          <Col md="8">
            <div className="d-flex justify-content-between">
              <Button onClick={() => (1)} color="primary">
                <FontAwesomeIcon icon={['fab', 'google']} className="mr-2"/>
                Signup with Google
              </Button>
              <Button onClick={() => (1)} color="primary">
                <FontAwesomeIcon icon={['fab', 'facebook-f']} className="mr-2"/>
                Signup with Facebook
              </Button>
            </div>
          </Col>
        </Row>
        <div className="text-center text-muted my-1">
          <small>Or</small>
        </div>
        <form>
          <Row className="justify-content-center my-1">
            <Col md="8">
              <InputGroup>
                <Input type="email" required value={this.state.email} onChange={e => this.setState({email: e.value})}/>
                <InputGroupAddon addonType="append">
                  <Button color="primary">Signin with Email</Button>
                </InputGroupAddon>
              </InputGroup>
            </Col>
          </Row>
        </form>
      </div>
    )
  }
}
