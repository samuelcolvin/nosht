import React from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {Row, Col} from 'reactstrap'
import {user_full_name} from '../utils'

const Footer = ({user}) => {
  let menu = [
    {name: 'Login', to: '/login/'},
    {name: 'Create Event', to: '/signup/'},
  ]
  if (user) {
    if (user.role === 'admin') {
      menu = [
        {name: 'Settings', to: '/settings/events/'},
        {name: 'Create Event', to: '/create/'},
      ]
    } else if (user.role === 'host') {
      menu = [
        {name: 'Account Settings', to: '/account/'},
        {name: 'My Events', to: '/my-events/'},
        {name: 'Create Event', to: '/create/'},
      ]
    } else {
      // guest
      menu = [
        {name: 'Create Event', to: '/signup/'},
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
              <FontAwesomeIcon icon="user" className="mr-1" />
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
