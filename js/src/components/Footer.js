import React from 'react'
import {Link} from 'react-router-dom'
import FontAwesomeIcon from '@fortawesome/react-fontawesome'
import {Row, Col} from 'reactstrap'

const Footer = ({user}) => {
  let menu = [
    {name: 'Login', to: '/login/'},
  ]
  if (user) {
    menu = [
      {name: 'Account Settings', to: '/account/'},
      {name: 'Logout', to: '/logout/'},
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
              <FontAwesomeIcon icon="user" className="mr-1" />
              Logged in as {user.name} ({user.role})
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
