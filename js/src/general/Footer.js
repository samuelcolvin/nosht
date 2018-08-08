import React from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {Row, Col} from 'reactstrap'
import Raven from 'raven-js'
import {user_full_name} from '../utils'

const update_raven_user = user => {
  if (user) {
    Raven.setUserContext({
      email: user.email,
      username: user_full_name(user),
      role: user.role,
      status: user.status,
    })
  } else {
    Raven.setUserContext()
  }
}

class Footer extends React.Component {
  async componentDidMount () {
    update_raven_user(this.props.user)
  }

  componentDidUpdate (prevProps) {
    if (this.props.user !== prevProps.user) {
      update_raven_user(this.props.user)
    }
  }

  render () {
    const user = this.props.user
    let menu = [
      {name: 'Login', to: '/login/'},
      {name: 'Signup', to: '/signup/'},
    ]
    if (user) {
      menu = [
        {name: 'Logout', to: '/logout/'}
      ]
    }
    return (
      <footer className="footer">
        <div className="container">
          <Row>
            <Col>
              {process.env.REACT_APP_COPYRIGHT_STATEMENT}
            </Col>
            <Col className="text-right footer-menu">
              {user && <div>
                <FontAwesomeIcon icon="user" className="mr-1"/>
                Logged in as {user_full_name(user)} ({user.role})
              </div>}
              {menu.map((item, i) => (
                  <Link key={i} to={item.to}>{item.name}</Link>
              ))}
            </Col>
          </Row>
        </div>
      </footer>
    )
  }
}

export default Footer
