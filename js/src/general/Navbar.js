import React from 'react'
import {Link} from 'react-router-dom'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import {
  Collapse,
  Navbar as NavbarBootstrap,
  NavbarToggler,
  NavbarBrand,
  Nav,
  NavItem,
  NavLink,
} from 'reactstrap'
import {on_mobile, watch_scroll} from '../utils'

const BACK_TOP_DEFAULT = 100
let BACK_TOP = BACK_TOP_DEFAULT

const ExtraMenu = ({message}) => (
  <div className={'extra-menu fixed-top' + (message ? ' show' : '')}>
    <div className="container">
      <div>
        {message &&
          <span className="item">
            {message.icon && <FontAwesomeIcon icon={message.icon} className="mr-2"/>}
            <span>{message.message || message.toString()}</span>
          </span>
        }
      </div>
    </div>
  </div>
)

export default class Navbar extends React.Component {
  constructor (props) {
    super(props)

    this.close = this.close.bind(this)
    this.state = {
      is_open: false,
    }

    // parallax
    watch_scroll(y_pos => {
      BACK_TOP = Math.round(BACK_TOP_DEFAULT + y_pos / 2) + 'px'
      const el = document.getElementById('background-image')
      if (el) {
        el.style.top = BACK_TOP
      }
    })
  }

  close () {
    this.state.is_open && this.setState({is_open: false})
  }

  render () {
    const categories = this.props.company ? this.props.company.categories : []
    const company = this.props.company ? this.props.company.company : {}
    const navbar = (
      <NavbarBootstrap key="1" color="light" light fixed="top" expand="md">
        <div className="container">
          <NavbarBrand tag={Link} onClick={this.close} to="/">
            <img className="d-none d-md-block" src="/logo.png" alt={company.name || process.env.REACT_APP_SITE_NAME}/>
            <span className="d-md-none">{company.name || process.env.REACT_APP_SITE_NAME}</span>
          </NavbarBrand>
          <NavbarToggler onClick={() => this.setState({is_open: !this.state.is_open})}/>
          <Collapse isOpen={this.state.is_open} navbar>
            <Nav className="ml-auto" navbar>
              {categories.map((cat, i) => (
                <NavItem key={i} active={cat.slug === this.props.active_page}>
                  <NavLink tag={Link} onClick={this.close} to={`/${cat.slug}/`}>{cat.name}</NavLink>
                </NavItem>
              ))}
              {this.props.user ? (
                this.props.user.role !== 'guest' ? (
                  <NavItem active={this.props.active_page === 'dashboard'}>
                    <NavLink tag={Link} onClick={this.close} to="/dashboard/events/">
                      {this.props.user.role === 'host' ? 'Manage Events' : 'Dashboard'}
                    </NavLink>
                  </NavItem>
                ) : (
                  <NavItem>
                    <NavLink tag={Link} onClick={this.close} to="/logout/">Logout</NavLink>
                  </NavItem>
                )
              ) : (
                <NavItem active={this.props.active_page === 'login'}>
                  <NavLink tag={Link} onClick={this.close} to="/login/">Login</NavLink>
                </NavItem>
              )}
            </Nav>
          </Collapse>
        </div>
      </NavbarBootstrap>
    )
    if (on_mobile) {
      return navbar
    } else {
      const background = this.props.background || company.image
      return [
        navbar,
        <ExtraMenu key="2" message={this.props.message}/>,
        <div key="3" id="background-image" style={{
          backgroundImage: background ? `url("${background}")` : null,
          top: BACK_TOP
        }}/>,
      ]
    }
  }
}
