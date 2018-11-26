import React from 'react'
import {Link} from 'react-router-dom'
import {FontAwesomeIcon} from '@fortawesome/react-fontawesome'
import * as Sentry from '@sentry/browser'
import {user_full_name} from '../utils'

const update_raven_user = user => {
  Sentry.configureScope((scope) => {
    if (user) {
      scope.setUser({
        email: user.email,
        username: user_full_name(user),
        role: user.role,
        status: user.status,
      })
    } else {
      scope.setUser({})
    }
  })
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
          <div className="d-flex justify-content-center my-1">
            {user &&
              <div className="mx-2">
                <FontAwesomeIcon icon="user" className="mr-1"/>
                Logged in as {user_full_name(user)} ({user.role})
              </div>
            }
            {menu.map((item, i) => (
              <div key={i} className="mx-2">
                <Link to={item.to}>{item.name}</Link>
              </div>
            ))}
          </div>
          <div className="d-flex justify-content-center my-1">
            {process.env.REACT_APP_COPYRIGHT_STATEMENT}
          </div>
          {this.props.co_footer_links && this.props.co_footer_links.length ? (
            <div className="d-flex justify-content-center my-1 custom-footer">
              {this.props.co_footer_links.map((link, i) => (
                <div key={i} className="mx-2">
                  <a href={link.url} target={link.new_tab ? '_blank' : '_self'} rel="noopener noreferrer">
                    {link.title}
                  </a>
                </div>
              ))}
            </div>
          ): null}
        </div>
      </footer>
    )
  }
}

export default Footer
