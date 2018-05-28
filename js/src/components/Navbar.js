import React from 'react'
import { Link } from 'react-router-dom'
import {
  Collapse,
  Navbar as NavbarStrap,
  NavbarToggler,
  NavbarBrand,
  Nav,
  NavItem,
  NavLink,
} from 'reactstrap'

const SWITCH_MENU_HEIGHT = 400
const STRAP_TOP_DEFAULT = 56
let STRAP_TOP = STRAP_TOP_DEFAULT

export default class Navbar extends React.Component {
  constructor (props) {
    super(props)

    this.close = this.close.bind(this)
    this.set_extra = this.set_extra.bind(this)
    this.state = {
      is_open: false,
      show_extra: false,
    }
    let y_pos = window.scrollY
    this.set_extra(y_pos)

    let busy = false
    this.on_desktop = window.innerWidth > 600

    if (this.on_desktop) {
    window.addEventListener('scroll', () => {
      y_pos = window.scrollY
      if (!busy) {
        window.requestAnimationFrame(() => {
          this.set_extra(y_pos)
          // parallax
            STRAP_TOP = Math.round(STRAP_TOP_DEFAULT + y_pos / 2) + 'px'
            document.getElementById('strap-image').style.top = STRAP_TOP
          busy = false
        })
        busy = true
      }
    })
  }
  }

  close () {
    this.state.is_open && this.setState({ is_open: false })
  }

  set_extra () {
    if (window.scrollY > SWITCH_MENU_HEIGHT && !this.state.show_extra) {
      this.setState({ show_extra: true })
    }
    if (window.scrollY < SWITCH_MENU_HEIGHT && this.state.show_extra) {
      this.setState({ show_extra: false })
    }
  }

  render () {
    const categories = this.props.company_data ? this.props.company_data.categories : []
    const company = this.props.company_data ? this.props.company_data.company : {}
    const navbar = (
      <NavbarStrap key="1" color="light" light fixed="top" expand="md">
        <div className="container">
          <NavbarBrand tag={Link} onClick={this.close} to="/">{process.env.REACT_APP_SITE_NAME}</NavbarBrand>
          <NavbarToggler onClick={() => this.setState({ is_open: !this.state.is_open })} />
          <Collapse isOpen={this.state.is_open} navbar>
            <Nav className="ml-auto" navbar>
              {categories.map((cat, i) => (
                <NavItem key={i}>
                  <NavLink tag={Link} onClick={this.close} to={`/${cat.slug}/`}>{cat.name}</NavLink>
                </NavItem>
              ))}
            </Nav>
          </Collapse>
        </div>
      </NavbarStrap>
    )
    if (!this.on_desktop) {
      return navbar
    } else {
      const image = company.image || 'https://nosht.scolvin.com/back/1.jpg'
      return [
        navbar,
        <div key="2" className={'extra-menu fixed-top' + (this.state.show_extra ? ' show' : '')}>
          <div className="container">
            <span>Book Now</span>
          </div>
        </div>,
        <div key="3" id="strap-image" style={{
          backgroundImage: `url("${image}")`,
          top: STRAP_TOP
        }}/>,
      ]
    }
  }
}
