import React from 'react'
import { Link } from 'react-router-dom'
import { Row, Col } from 'reactstrap'

const FOOTER_MENU = [
  {name: 'Login', to: '/login/'},
  {name: 'Logout', to: '/logout/'},
]

const Footer = () => {
  return (
    <footer className="footer">
      <div className="container">
        <Row>
          <Col>
            {process.env.REACT_APP_COPYRIGHT_STATEMENT}
          </Col>
          <Col className="text-right footer-menu">
            {FOOTER_MENU.map((item, i) => (
              <Link key={i} to={item.to}>{item.name}</Link>
            ))}
          </Col>
        </Row>
      </div>
    </footer>
  )
}

export default Footer
