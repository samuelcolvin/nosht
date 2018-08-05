import React from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {Row, Col} from 'reactstrap'
import {user_full_name} from '../utils'

const Footer = ({user}) => {
  let menu = [
    {name: 'Login', to: '/login/'},
    {name: 'Signup', to: '/signup/'},
  ]
  if (user) {
    menu = []
    if (user.role === 'admin' || user.role === 'host') {
      menu = [
        {name: 'Dashboard', to: '/dashboard/events/'},
      ]
    }
    menu.push({name: 'Logout', to: '/logout/'})
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

export default Footer
