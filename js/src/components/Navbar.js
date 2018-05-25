import React from 'react'
import {
  Collapse,
  Navbar as NavbarStrap,
  NavbarToggler,
  NavbarBrand,
  Nav,
  NavItem,
  NavLink,
} from 'reactstrap'

export default class Navbar extends React.Component {
  constructor (props) {
    super(props)

    this.toggle = this.toggle.bind(this)
    this.set_extra = this.set_extra.bind(this)
    this.state = {
      is_open: false,
      show_extra: false,
    }
    let y_pos = window.scrollY
    this.set_extra(y_pos)

    let busy = false
    window.addEventListener('scroll', () => {
      y_pos = window.scrollY
      if (!busy) {
        window.requestAnimationFrame(() => {
          this.set_extra(y_pos)
          // parallax
          document.getElementById('strap-image').style.top = Math.round(56 + y_pos / 2) + 'px'
          busy = false
        })
        busy = true
      }
    })
  }

  toggle () {
    this.setState({
      is_open: !this.state.is_open
    })
  }

  set_extra () {
    const switch_height = 400
    if (window.scrollY > switch_height && !this.state.show_extra) {
      this.setState({ show_extra: true })
    }
    if (window.scrollY < switch_height && this.state.show_extra) {
      this.setState({ show_extra: false })
    }
  }

  render () {
    return [
      <NavbarStrap key="1" color="light" light fixed="top" expand="md">
        <div className="container">
          <NavbarBrand href="/">{process.env.REACT_APP_SITE_NAME}</NavbarBrand>
          <NavbarToggler onClick={this.toggle} />
          <Collapse isOpen={this.state.is_open} navbar>
            <Nav className="ml-auto" navbar>
              <NavItem>
                <NavLink href="/foo/">Foo</NavLink>
              </NavItem>
              <NavItem>
                <NavLink href="/bar/">Bar</NavLink>
              </NavItem>
            </Nav>
          </Collapse>
        </div>
      </NavbarStrap>,
      <div key="2" className={'extra-menu fixed-top' + (this.state.show_extra ? ' show' : '')}>
        <div className="container">
          <span>Book Now</span>
        </div>
      </div>,
      <div key="3" id="strap-image" style={{ backgroundImage: 'url("https://nosht.scolvin.com/back/1.jpg")'}}/>,
    ]
  }
}
